# Multiple Custom Field Instances

## Overview
This modification enables documents to have multiple instances of the same custom field, allowing use cases like multiple document links, multiple values for the same field type, or repeated entries.

## Problem
Previously, the system enforced a unique constraint on `(document, field)` combinations in `CustomFieldInstance`, preventing multiple instances of the same custom field on a single document. Additionally, the internal data structure (`DocumentMetadataOverrides`) used a dictionary which would overwrite duplicate field IDs.

## Solution

### Bug Fix Note

⚠️ **POST Operation Bug Fixed**: The original implementation had a bug where POST operations (document upload via `/api/documents/post_document/`) didn't support multiple instances of the same custom field. The `PostDocumentSerializer.validate_custom_fields` method only accepted dict or list-of-integers formats, both of which couldn't represent multiple instances of the same field ID. This has been fixed by adding support for the list-of-dicts format (e.g., `[{"field": 1, "value": "a"}, {"field": 1, "value": "b"}]`) in both the serializer validation and the POST handler.

### Backend Changes

**1. Database Model (`src/documents/models.py`)**
- ✅ Removed unique constraint on `CustomFieldInstance.(document, field)`
- ✅ Added composite index `docs_cfi_doc_field_idx` for query performance

**2. Data Structure (`src/documents/data_models.py`)**
- ✅ Changed `DocumentMetadataOverrides.custom_fields` from `dict` to `list[dict]`
- ✅ Format: `[{"field_id": int, "value": Any}, ...]`
- ✅ Updated `update()` method to use `extend()` instead of `dict.update()`
- ✅ Updated `from_document()` to return list of field instances

**3. Consumer (`src/documents/consumer.py`)**
- ✅ Updated `apply_overrides()` to iterate through list and create multiple instances
- ✅ Properly handles multiple instances of same field

**4. Workflow System (`src/documents/signals/handlers.py`)**
- ✅ Updated workflow actions to use list format for custom fields
- ✅ Updated removal logic to filter lists instead of using dict operations

**5. API Serializer (`src/documents/serialisers.py`)**
- ✅ Changed `CustomFieldInstanceSerializer.create()` from `update_or_create()` to `create()`
- ✅ Updated `DocumentSerializer.update()` to delete existing instances before creating new ones
- ✅ Ensures clean state when patching documents with custom fields

**6. API Views (`src/documents/views.py`)**
- ✅ Updated document upload to use list format
- ✅ Added backwards compatibility for dict format

### Frontend Changes

**Custom Fields Dropdown (`src-ui/src/app/components/common/custom-fields-dropdown/`)**
- ✅ All fields now always available (no filtering of "used" fields)
- ✅ Added badge indicator showing count of existing instances
- ✅ Visual feedback: Badge displays the number of times a field is already used

### Database Migrations
- `1076_remove_customfieldinstance_documents_customfieldinstance_unique_document_field_and_more.py` - Removes unique constraint, adds composite index

## API Changes

### Request Format

**PATCH/PUT Operations** (updating existing documents):
```json
{
  "custom_fields": [
    {"field": 1, "value": "value_a"},
    {"field": 2, "value": null},
    {"field": 1, "value": "value_b"}
  ]
}
```

**POST Operations** (uploading new documents via `/api/documents/post_document/`):

The API now supports three formats for `custom_fields`:

1. **List of dicts** (for multiple instances - **NEW**):
```json
{
  "custom_fields": [
    {"field": 1, "value": "value_a"},
    {"field": 1, "value": "value_b"}
  ]
}
```

2. **Dict mapping field IDs to values** (backwards compatible - single instance per field):
```json
{
  "custom_fields": {
    "1": "value_a",
    "2": "value_b"
  }
}
```

3. **List of field IDs** (backwards compatible - creates instances with null values):
```json
{
  "custom_fields": [1, 2, 3]
}
```

**Response Format:**
Now correctly returns all instances instead of just the last one per field ID.

## Testing

**New Tests Added:**
1. `test_consumer.py::testOverrideCustomFieldsMultiple()` - Consumer with multiple instances
2. `test_api_custom_fields.py::test_multiple_custom_field_instances_same_field()` - API PATCH with duplicates
3. `test_api_documents.py::test_upload_with_multiple_custom_field_instances()` - API POST with multiple instances of the same field

**Existing Tests Updated:**
- Updated tests using old dict format to new list format
- All custom field tests pass

## Important Behavioral Changes

### PATCH Operations
When updating a document's custom fields via PATCH:
- **Partial updates**: Only custom fields included in the request are affected
- **Complete replacement**: All existing instances of included fields are deleted and replaced
- **Unchanged fields**: Custom fields not in the request remain untouched

**Example**: If a document has fields A, B, and C, and you PATCH with only field A, only field A's instances are deleted and recreated. Fields B and C remain unchanged.

### Instance Ordering
Multiple instances of the same field are ordered by their `created` timestamp (Model Meta: `ordering = ("created",)`). The order in which they appear in API responses matches the creation order.

## Breaking Changes

⚠️ **Internal API Change**: `DocumentMetadataOverrides.custom_fields` format changed from dict to list. This affects:
- Any custom consumer code directly manipulating this field
- Any workflow extensions using the override system

## Migration Path

1. Run migrations: `python manage.py migrate`
2. Existing single custom field instances continue to work
3. New documents can now have multiple instances per field
4. Frontend automatically shows count badges

## Performance Considerations

- ✅ Added composite index on `(document, field)` maintains query performance
- ✅ API PATCH operations delete and recreate instances (clean approach, minimal overhead)
- ✅ No impact on documents without duplicate custom fields

## Querying Documents

When querying documents with multiple custom field instances:
- **Any match**: Queries match if ANY instance satisfies the condition
- **Filtering**: Use `document.custom_fields.filter(field=cf1)` to get all instances of a specific field
- **Performance**: The composite index `(document, field)` optimizes these queries
- **Counting**: Use `.count()` to get the number of instances for a field

**Example**:
```python
# Get all instances of a specific field on a document
instances = document.custom_fields.filter(field=my_custom_field)

# Check if a document has any instance of a field
has_field = document.custom_fields.filter(field=my_custom_field).exists()

# Get count of instances
count = document.custom_fields.filter(field=my_custom_field).count()
```

## Use Cases

This feature enables several powerful use cases:

### Multiple Document Links
Link a document to multiple related documents using the same document link field:
```json
{
  "custom_fields": [
    {"field": 5, "value": [101, 102]},
    {"field": 5, "value": [103, 104]},
    {"field": 5, "value": [105]}
  ]
}
```

### Multiple Values for Classification
Add multiple values for the same classification field:
```json
{
  "custom_fields": [
    {"field": 3, "value": "Category A"},
    {"field": 3, "value": "Category B"},
    {"field": 3, "value": "Category C"}
  ]
}
```

### Multiple URLs/References
Store multiple external references or URLs:
```json
{
  "custom_fields": [
    {"field": 7, "value": "https://example.com/ref1"},
    {"field": 7, "value": "https://example.com/ref2"}
  ]
}
```

## UI/UX Enhancements

### Custom Fields Dropdown
- All custom fields remain available in the dropdown after being added
- A badge shows the count of existing instances (e.g., "2" if the field is used twice)
- Users can add the same field multiple times
- Clear visual feedback helps users understand field usage

## Edge Cases

The system handles various edge cases gracefully:

- **Empty list**: Sending `"custom_fields": []` in a PATCH request removes all custom field instances from the document
- **Null values**: `{"field": 1, "value": null}` creates an instance with a null value (stored in the appropriate value field)
- **Deletion via UI**: Users can delete individual instances from the document detail view
- **Duplicate values**: The system allows multiple instances with identical values (e.g., two instances of "Category A")
- **Mixed operations**: You can PATCH some fields while leaving others unchanged by only including the fields you want to modify

## Best Practices

1. **Use Descriptive Field Names**: When a field can have multiple instances, name it appropriately (e.g., "Related Document" instead of "Related Documents")

2. **Document Your Usage**: Add remarks to custom fields explaining that they support multiple instances

3. **Consider Field Types**:
   - Document links work well with multiple instances
   - String fields can represent multiple categories or tags
   - URL fields can reference multiple external systems

4. **Workflow Integration**: When using workflows to assign custom fields, be aware that multiple instances will be added rather than replaced

5. **API Usage**: When updating documents via API, always send the complete list of instances you want for each field (partial updates are not supported per field)

## Technical Details

### Database Schema
The migration removes the unique constraint and adds a composite index:
```python
indexes = [
    models.Index(
        fields=["document", "field"],
        name="docs_cfi_doc_field_idx",
    ),
]
```

This maintains query performance while allowing duplicates.

### Serializer Behavior
When updating a document with custom fields via PATCH:
1. Existing instances of fields being updated are deleted
2. New instances are created from the request payload
3. This ensures a clean state and prevents unexpected accumulation

### Backwards Compatibility
The API views maintain backwards compatibility:
- Dict format `{"field_id": value}` is converted to list format internally
- List of integers `[field_id1, field_id2]` creates instances with `None` values
- Existing API clients continue to work without modification

## Migration Number Note

**Important**: The original patch specified migration `1102`, but this implementation uses migration `1076` to maintain sequential numbering with the existing codebase. The migration has been renumbered and its dependencies updated to reference the correct predecessor migration (`1075` instead of `1101`).

This change was necessary because:
- The latest migration in this branch is `1075`
- Migrations must be numbered sequentially
- The dependency chain must be correct for `makemigrations` and `migrate` to work properly

If you need to merge with upstream changes that include migrations `1076`-`1101`, you may need to renumber this migration again.

## Files Modified

### Backend (Python)
- `src/documents/models.py` - Model changes (removed unique constraint, added composite index)
- `src/documents/data_models.py` - Data structure changes (dict to list format)
- `src/documents/consumer.py` - Consumer logic (iterate through list, create multiple instances)
- `src/documents/serialisers.py` - API serializers (changed to create(), added delete logic, **added list-of-dicts validation for POST operations**)
- `src/documents/signals/handlers.py` - Workflow signals (list format handling)
- `src/documents/views.py` - API views (backwards compatibility conversion, **added list-of-dicts format handling for POST**)
- `src/documents/migrations/1076_remove_customfieldinstance_documents_customfieldinstance_unique_document_field_and_more.py` - Database migration

### Frontend (TypeScript/Angular)
- `src-ui/src/app/components/common/custom-fields-dropdown/custom-fields-dropdown.component.ts` - Added badge count logic
- `src-ui/src/app/components/common/custom-fields-dropdown/custom-fields-dropdown.component.html` - Added badge display

### Tests
- `src/documents/tests/test_consumer.py` - Updated existing test, added new multi-instance test
- `src/documents/tests/test_api_custom_fields.py` - Added comprehensive multi-instance test
- `src/documents/tests/test_api_documents.py` - Updated assertion for new format, **added test for POST with multiple custom field instances**
