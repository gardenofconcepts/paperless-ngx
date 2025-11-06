# Bulk Edit Multiple Custom Field Instances - Implementation Summary

## Overview
This implementation extends the bulk edit API (`/api/documents/bulk_edit/`, method `modify_custom_fields`) to support adding and removing specific custom field instances on documents, enabling users to manage multiple instances of the same custom field per document.

## Key Features
- **Multiple Instance Support**: Add/remove specific instances of custom fields identified by field ID and value
- **Backwards Compatible**: Old `add_custom_fields` and `remove_custom_fields` parameters continue to work unchanged
- **Idempotent Operations**: Repeated requests with identical parameters produce the same result
- **Type-Aware Deduplication**: Values normalized by type before comparison
- **Efficient Processing**: Uses bulk operations and in-memory lookups for performance
- **Document Link Symmetry**: Automatically maintains bidirectional links when adding/removing document links
- **Payload Protection**: 1000-item limit per parameter prevents abuse

## API Changes

### New Parameters
Two new parameters added to `modify_custom_fields` method:

- **`add_custom_field_instances`**: List of `{"field": FIELD_ID, "value": VALUE}` objects to add
- **`remove_custom_field_instances`**: List of `{"field": FIELD_ID, "value": VALUE}` objects to remove

### All Four Parameters Can Be Mixed
```json
{
  "documents": [1, 2, 3],
  "method": "modify_custom_fields",
  "parameters": {
    "add_custom_fields": {"1": "single_value"},
    "remove_custom_fields": [2],
    "add_custom_field_instances": [{"field": 3, "value": "A"}, {"field": 3, "value": "B"}],
    "remove_custom_field_instances": [{"field": 4, "value": 42}]
  }
}
```

### Processing Order
1. Remove by instance (exact field + value match)
2. Remove by field ID (removes all instances)
3. Add by classic params (single instance via create after delete)
4. Add by instances (with deduplication)

## Implementation Details

### Files Modified

#### Backend (Python)

**`src/documents/serialisers.py`**
- Extended `BulkEditSerializer._validate_parameters_modify_custom_fields()` to accept new parameters
- Added `_validate_custom_field_instances()` method for validation
- Enforces at least one of four parameters present
- Performs request-level deduplication (rejects duplicate {field, value} pairs in single request)
- 1000-item limit per parameter for payload protection

**`src/documents/bulk_edit.py`**
- Added `_normalize_value_for_comparison(field, value)` function that normalizes values by type:
  - **String/URL/Long text**: Exact match (case-sensitive)
  - **Date/Bool/Int/Float/Select**: Exact value
  - **Document link**: Sorted, unique list comparison
  - **JSON**: Structural equality with sorted dict keys
  - **Monetary**: Uppercase currency code normalization

- Extended `modify_custom_fields()` signature with kwargs:
  - `add_custom_field_instances=None`
  - `remove_custom_field_instances=None`

- Implementation flow:
  1. Fetch all affected documents and custom field definitions
  2. Build in-memory lookup of existing instances for O(1) dedup checks
  3. Execute 4-step processing order (remove instances → remove fields → add classic → add instances)
  4. For classic adds: Delete all existing instances first, then create single new one
  5. For instance adds: Skip if already exists (dedup), bulk create new ones
  6. Batch operations for efficiency
  7. Maintain document link symmetry via `reflect_doclinks()`

#### Tests

**`src/documents/tests/test_api_bulk_edit.py`**
- `test_api_modify_custom_fields_add_instances`: Tests adding multiple instances
- `test_api_modify_custom_fields_remove_instance`: Tests removing by value
- `test_api_modify_custom_fields_deduplication`: Tests request-level dedup validation
- `test_api_modify_custom_fields_requires_at_least_one_param`: Tests parameter requirements
- `test_api_modify_custom_fields_mixed_params`: Tests mixing old and new formats

**`src/documents/tests/test_bulk_edit.py`**
- `TestCustomFieldInstanceOperations` class with 11 unit tests:
  - Addition of multiple instances
  - Deduplication across add requests
  - Removal by specific value
  - Type-specific normalization (document links, JSON, monetary)
  - Processing order verification
  - Mixing old and new formats
  - Collision handling (field removal precedence)

#### Documentation

**`docs/custom_field.md`**
- Added "Bulk edit custom fields" section with:
  - Classic format examples
  - Instance-level format examples
  - Mixing formats explanation
  - Processing order and deduplication rules
  - Normalization rules by type
  - Tips about idempotency and document link symmetry

**`docs/api.md`**
- Updated `modify_custom_fields` documentation with:
  - All four parameter options described
  - Processing order explained
  - Deduplication behavior described
  - Reference to detailed custom_field.md docs

## Critical Bug Fixes Applied

### Issue 1: String Keys in Dict Format
**Problem**: When `add_custom_fields` passed as dict `{"1": "value"}`, JSON deserializes keys as strings but lookup used integer keys
**Fix**: Convert string keys to integers during normalization:
- In `bulk_edit.py` line 255-259: Convert dict keys to integers during `add_custom_fields` normalization
- In `serialisers.py` line 1634-1635: Normalize field IDs to integers in instance validation

### Issue 2: Multiple Instances with update_or_create
**Problem**: When multiple instances of same field exist on document, `update_or_create()` fails with "get() returned more than one"
**Fix**: Replace `update_or_create()` with explicit delete-then-create pattern in `bulk_edit.py` lines 362-409:
- Delete all existing instances for field/doc combination
- Handle doclink symmetry cleanup
- Create single new instance

### Issue 3: Missing Required Parameters in Function Call
**Problem**: When only instance-level parameters provided, `add_custom_fields` and `remove_custom_fields` were missing, causing "modify_custom_fields() missing 2 required positional arguments"
**Fix**: Set default values in `serialisers.py` lines 1583-1594:
- Set `add_custom_fields` to empty dict `{}` if not provided
- Set `remove_custom_fields` to empty list `[]` if not provided
- Ensures function always receives required arguments

### Issue 4: String Field IDs in Instance Payloads
**Problem**: When JSON payload contains `{"field": "1"}` (string), it needs to be converted to integer for lookup
**Fix**: Added field ID normalization in `serialisers.py` line 1635:
- Convert string field IDs to integers: `item["field"] = field_id`
- Happens during validation before function call

## Type-Specific Normalization Examples

### Document Links
```python
# These are considered identical after normalization:
[3, 1, 2] and [1, 2, 3]  # Both normalize to (1, 2, 3)
```

### JSON
```python
# These are considered identical after normalization:
{"b": 2, "a": 1} and {"a": 1, "b": 2}  # Both normalize with sorted keys
```

### Monetary
```python
# These are considered identical after normalization:
"usd100.50" and "USD100.50"  # Both normalize with uppercase currency
```

## Performance Optimizations

1. **Single Query for Existing Instances**: Fetches all existing instances once with select_related("field")
2. **In-Memory Lookup**: O(1) deduplication checks using dictionary
3. **Bulk Operations**: Uses `bulk_create()` instead of individual creates
4. **Index Optimization**: Uses existing `(document, field)` composite index in database

## Edge Cases Handled

1. **Empty Document List**: Returns OK without processing
2. **Non-existent Field IDs**: Silently skipped (safe degradation)
3. **Self-Linking Prevention**: Document link fields can't link to themselves
4. **Collision Rules**: Field-level removal takes precedence over instance-level removal
5. **Request Deduplication**: Identical instances in single request are rejected
6. **Null Values**: Supported in all field types
7. **Mixed Operations**: All four parameters can appear together without conflict

## Testing Coverage

- **API Tests**: 5 new test methods covering basic operations, validation, mixing formats
- **Unit Tests**: 11 comprehensive tests covering normalization, deduplication, ordering, collisions
- **Coverage Areas**:
  - Classic dict format with string keys
  - Instance-level add/remove operations
  - Deduplication at request level and operation level
  - All 8 data types with type-specific normalization
  - Processing order verification
  - Field removal precedence
  - Mixed parameter formats
  - Parameter requirement validation

## Known Limitations

1. **1000-Item Limit**: Per parameter, payload protection against abuse
2. **Request-Level Dedup Only**: Duplicate {field, value} pairs in single request are rejected
3. **No Partial Field Updates**: When using instance format, all instances for a field must be included (though old format can coexist)

## Future Enhancement Opportunities

1. **Bulk Update by Query**: Support bulk operations on documents matching criteria
2. **Conditional Updates**: Support conditional logic like "if exists, then..."
3. **Batch Import**: Support CSV/JSON file upload for bulk operations
4. **Async Notifications**: Webhook notifications when bulk operations complete
5. **Operation Logging**: Track audit log entries for each bulk operation

## Backwards Compatibility

- ✅ Old `add_custom_fields` (dict) format continues to work
- ✅ Old `add_custom_fields` (list of IDs) format continues to work
- ✅ Old `remove_custom_fields` parameter continues to work
- ✅ All existing API clients can continue without modification
- ✅ New parameters are optional

## Configuration

- **Max Items Per Parameter**: 1000 (hardcoded in `_validate_custom_field_instances()`)
  - Location: `src/documents/serialisers.py` line 1614
  - To change: modify `if len(instances) > 1000:` check

## Parameter Defaults

When parameters are not provided:
- `add_custom_fields` defaults to `{}` (empty dict) if not provided (line 1585)
- `remove_custom_fields` defaults to `[]` (empty list) if not provided (line 1594)

This ensures the `modify_custom_fields()` function always receives required arguments.

## Debugging Notes

1. If payload rejected as "bad request": Check that at least one of the four parameters is provided
2. If payload rejected with validation error: Check field IDs are integers or convertible to integers
3. If instances not being found: Check normalization in `bulk_edit.py` line 282 (value comparison)
4. If unexpected behavior with instance-level params alone: Verify default empty values are set (serialisers.py lines 1583-1594)
5. If string field IDs cause issues: Check they're being converted in serialisers.py line 1635
6. Check processing order if unexpected results (order matters! See line 355-450 in bulk_edit.py)
7. Enable debug logging in Django for detailed operation tracking
8. Use API test file as reference for expected behavior

## Related Documentation

- Main custom fields docs: `docs/custom_field.md`
- API reference: `docs/api.md`
- Previous multi-instance work: `modifications/multiple-custom-field-instances.md`

