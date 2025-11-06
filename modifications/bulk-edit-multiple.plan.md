# Extend Bulk Edit To Support Multiple Custom Field Instances

## Scope

Enhance `/api/documents/bulk_edit/` (method `modify_custom_fields`) to:

- Add multiple instances using a list of `{ field, value }` items
- Remove specific instances by `{ field, value }` match
- Preserve existing `add_custom_fields` (dict or list) and `remove_custom_fields` (list) behavior
- Make adds idempotent via deduplication per `{document, field, value}`

## API Additions

- New parameters under `parameters` for `method = "modify_custom_fields"`:
  - `add_custom_field_instances`: list of objects `{ "field": int, "value": any|null }`
  - `remove_custom_field_instances`: list of objects `{ "field": int, "value": any|null }`
- Allowed to mix with existing keys: `add_custom_fields`, `remove_custom_fields` (all four may appear together)
- Processing order:

1) `remove_custom_field_instances`

2) `remove_custom_fields`

3) `add_custom_fields`

4) `add_custom_field_instances`

- Collision rules:
  - Field-level removal removes all instances of that field, regardless of instance-level removals for the same field.
  - Instance-level adds are deduped against both pre-existing instances and any single-instance created by `add_custom_fields`.
- Matching rule for removals/add dedupe: match by `document_id`, `field_id` and normalized equality of the stored value column per type. For `DOCUMENTLINK`, compare normalized list (sorted unique) equality.

### Normalization for equality/deduplication

- String/URL/Long text: exact string match (case-sensitive).
- Date/Bool/Int/Float: exact value match.
- Select: compare option id (string) exact.
- Document link: lists of integers are normalized to sorted unique before compare.
- JSON: structural equality (dict keys order-insensitive; list order-sensitive). Canonicalize dicts with sorted keys.
- Monetary: compare on normalized representation with uppercase currency code if present (stored value not altered).

### Examples

Add two instances and remove one instance:

```json
{
  "documents": [101, 102],
  "method": "modify_custom_fields",
  "parameters": {
    "add_custom_field_instances": [
      { "field": 1, "value": "A" },
      { "field": 1, "value": "B" }
    ],
    "remove_custom_field_instances": [
      { "field": 2, "value": 42 }
    ]
  }
}
```

Backwards-compatible (unchanged):

```json
{
  "documents": [123],
  "method": "modify_custom_fields",
  "parameters": {
    "add_custom_fields": { "9": "foo" },
    "remove_custom_fields": [10]
  }
}
```

Mixed keys; reset a field entirely then add specific instances:

```json
{
  "documents": [123],
  "method": "modify_custom_fields",
  "parameters": {
    "remove_custom_fields": [7],
    "add_custom_fields": { "7": "X" },
    "add_custom_field_instances": [ { "field": 7, "value": "Y" } ]
  }
}
```

## Implementation

### 1) Serializer validation: `src/documents/serialisers.py`

- In `BulkEditSerializer`:
  - Extend `_validate_parameters_modify_custom_fields` to accept and validate `add_custom_field_instances` and `remove_custom_field_instances`.
  - **Set default values for classic parameters if not provided**:
    - Set `add_custom_fields` to `{}` (empty dict) if not present
    - Set `remove_custom_fields` to `[]` (empty list) if not present
    - **Why**: These are required positional arguments to `modify_custom_fields()`, so defaults must be provided even when only instance-level params are used
  - Validation rules:
    - Must be lists of dicts with `field` (int) and optional `value`.
    - Ensure field IDs exist.
    - Validate `value` per field type by reusing `CustomFieldInstanceSerializer.validate` with `{"field": field, "value": value}`.
    - For `DOCUMENTLINK`, normalize value to sorted unique list for matching.
    - **Request-level deduplication**: Reject duplicate `{field, value}` pairs within a single parameter (e.g., two identical items in `add_custom_field_instances`).
  - Require at least one of the four keys to be present; otherwise 400.
  - **Guardrails implemented**: Reject payloads with more than 1000 items per parameter (max 1000 per `add_custom_field_instances` and `remove_custom_field_instances`).

### 2) Bulk operation behavior: `src/documents/bulk_edit.py`

- Extend existing `modify_custom_fields` signature to accept new kwargs, preserving current ones:
  ```python
  def modify_custom_fields(doc_ids, add_custom_fields, remove_custom_fields, *,
                           add_custom_field_instances=None,
                           remove_custom_field_instances=None) -> Literal["OK"]:
  ```

- Concurrency/atomicity: wrap per-document modifications in a transaction; perform bulk create/delete when possible.
- **Value Normalization**: Implement `_normalize_value_for_comparison(field, value)` to handle type-specific normalization:
  - Used both during comparison in the in-memory lookup and during deduplication checks
  - Ensures consistent matching across all field types (see Normalization section above)
- Preload for dedupe: fetch existing instances for affected `(doc_ids × field_ids)` once; build an in-memory lookup keyed by `(doc_id, field_id, normalized_value_repr)`.
- Removals by instance:
  - For each `{field, value}` and each `doc_id`, delete only matching rows where the normalized stored value equals `value`.
  - For `DOCUMENTLINK`, call `remove_doclink` for each target id present in the removed instance.
- Removals by field IDs (existing): unchanged (removes all instances for those fields).
- Adds by classic params (existing): **Changed from update-or-create to delete-then-create** to handle multiple existing instances:
  1. Delete all existing instances for the field/doc combination
  2. Handle doclink symmetry cleanup for deleted instances
  3. Create single new instance
  - This ensures idempotent behavior when documents already have multiple instances of the same field
- Refresh lookup after classic adds for those fields to ensure dedupe against instance-level adds in the same request.
- Adds by instances:
  - For each `{field, value}` and each `doc_id`, skip if already present per lookup; otherwise create using `CustomFieldInstance.get_value_field_name`.
  - For `DOCUMENTLINK`, call `reflect_doclinks(doc, field, value)` before create.
- After any changes, call `bulk_update_documents.delay(document_ids=affected_docs)`.

### 3) Wire params through: `src/documents/serialisers.py`

- In `BulkEditSerializer.validate` for `method == modify_custom_fields`, pass the newly validated lists as keyword args to the bulk method: `bulk_edit.modify_custom_fields(doc_ids, add_custom_fields, remove_custom_fields, add_custom_field_instances=..., remove_custom_field_instances=...)`.

### 4) Tests

- `src/documents/tests/test_api_bulk_edit.py`:
  - Add: `test_api_modify_custom_fields_add_instances` → adds two instances of same field to multiple docs.
  - Add: `test_api_modify_custom_fields_remove_instance` → starts with duplicates, removes only one `{field,value}`.
  - Add: `test_api_modify_custom_fields_doclink_symmetry` → add/remove doclink instances and assert symmetry calls.
  - Add: `test_api_modify_custom_fields_deduplication` → sending identical instance twice results in one instance; repeated request is idempotent.
  - Add validation error tests for bad shapes/ids/values and payload too large.
- `src/documents/tests/test_bulk_edit.py`:
  - Add unit tests for matching/normalization across all types (STRING, URL, DATE, BOOL, INT, FLOAT, MONETARY, SELECT, LONG_TEXT, JSON, DOCUMENTLINK).

### 5) Documentation

- Update `docs/api.md` and `docs/custom_field.md`:
  - Document new `add_custom_field_instances` and `remove_custom_field_instances` with examples, type notes, matching/normalization rules, mixing/ordering/collision rules, idempotency guarantees.
  - Clarify that old parameters remain supported and their semantics.

### 6) Backwards compatibility & constraints

- No changes to `PATCH /api/documents/{id}/` semantics.
- Existing bulk edit requests remain valid.
- Performance: batched queries (`IN` filters), in-memory lookup for dedupe, index `(document, field)` already present.

## Key Snippets (illustrative)

- Validate instance payloads via existing serializer:
```python
cfi_ser = CustomFieldInstanceSerializer()
for item in add_custom_field_instances:
    field = CustomField.objects.get(id=item["field"])
    cfi_ser.validate({"field": field, "value": item.get("value")})
```

- Remove by exact stored column:
```python
value_field = CustomFieldInstance.get_value_field_name(custom_field.data_type)
qs = CustomFieldInstance.objects.filter(
    document_id=doc_id, field_id=field_id, **{value_field: normalized_value}
)
qs.hard_delete()
```

- Dedup lookup key (conceptual):
```python
key = (doc_id, field_id, normalize_value(field, value))
if key not in existing:
    # create
```


## Critical Implementation Notes

These issues were discovered during implementation and fixed:

### 1. String Keys in Dict Format
When `add_custom_fields` is passed as dict `{"1": "value"}`, JSON deserializes keys as strings, but the field lookup uses integer keys. **Solution**: Convert dict keys to integers during normalization (line 255-259 in `bulk_edit.py`) and during instance validation (line 1634-1635 in `serialisers.py`).

### 2. Multiple Instances with update_or_create
When multiple instances of the same field already exist on a document, `update_or_create()` fails with "get() returned more than one" error. **Solution**: Replace with delete-then-create pattern (lines 362-409 in `bulk_edit.py`):
- Delete all existing instances for field/doc combination
- Handle doclink symmetry cleanup
- Create single new instance

### 3. Missing Required Function Parameters
When only instance-level parameters are provided (`add_custom_field_instances` or `remove_custom_field_instances`), the function call fails because `add_custom_fields` and `remove_custom_fields` are required positional arguments. **Solution**: Set default empty values in serializer validation (lines 1583-1594 in `serialisers.py`):
- `add_custom_fields` defaults to `{}`
- `remove_custom_fields` defaults to `[]`

### 4. String Field IDs in Instance Payloads
When JSON payload contains `{"field": "1"}` (string), field lookup fails. **Solution**: Normalize field IDs to integers during validation (line 1635 in `serialisers.py`).


## Todos

- add-serializer-validation: Accept and validate instance add/remove params
- implement-bulk-logic: Extend `modify_custom_fields` for instance-level ops
- wire-serializer-to-bulk: Pass new args from serializer to bulk method
- tests-api: Add API tests for add/remove instance flows, symmetry, deduplication
- tests-unit: Add unit tests for matching/normalization across types
- docs-update: Document new bulk edit parameters, normalization, mixing and idempotency

### To-dos

- [ ] Pass new instance params from serializer to bulk method
- [ ] Accept and validate add/remove instance params in BulkEditSerializer
- [ ] Extend modify_custom_fields to add/remove specific instances
- [ ] Add API tests for instance add/remove and doclink symmetry
- [ ] Add unit tests for matching and normalization
- [ ] Update API and custom_field docs for new bulk params
