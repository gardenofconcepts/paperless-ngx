# Multiple Custom Field Instances per Document

**Date:** October 2025
**Status:** Implemented
**Original Version:** 1.18

## Overview

This modification enables documents to have multiple instances of the same custom field, removing the previous limitation where each custom field could only appear once per document.

## Motivation

Previously, the system enforced a unique constraint on the combination of `(document, field)` in the `CustomFieldInstance` model. This prevented use cases such as:

- Multiple document links to related documents
- Multiple values for the same field type (e.g., multiple authors, multiple references)
- Repeated entries of the same field with different values
- List-like data stored as separate custom field instances

## Technical Implementation

### Database Changes

#### Model: `CustomFieldInstance`

**Before:**
```python
class Meta:
    constraints = [
        models.UniqueConstraint(
            fields=["document", "field"],
            name="documents_customfieldinstance_unique_document_field",
        ),
    ]
```

**After:**
```python
class Meta:
    indexes = [
        models.Index(
            fields=["document", "field"],
            name="docs_cfi_doc_field_idx",
        ),
    ]
```

**Changes:**
- Removed unique constraint on `(document, field)` combination
- Added composite index for query performance
- Index name: `docs_cfi_doc_field_idx`

#### Migrations

1. **Migration 1102:** Removes unique constraint and adds index
   - File: `src/documents/migrations/1102_remove_customfieldinstance_documents_customfieldinstance_unique_document_field_and_more.py`
   - Operations:
     - `RemoveConstraint`: Removes `documents_customfieldinstance_unique_document_field`
     - `AddIndex`: Adds `docs_cfi_doc_field_idx`

### Backend Changes

#### 1. Data Structure (`src/documents/data_models.py`)

**`DocumentMetadataOverrides` class:**

**Before:**
```python
custom_fields: dict | None = None  # {field_id: value}
```

**After:**
```python
custom_fields: list[dict] | None = None  # [{"field_id": int, "value": Any}, ...]
```

**Impact:**
- `from_document()`: Returns list of field instances with structure `{"field_id": field.id, "value": value}`
- `update()`: Uses `extend()` instead of `dict.update()` to merge custom fields
- Supports multiple instances of the same field ID

#### 2. Consumer (`src/documents/consumer.py`)

**Method:** `apply_overrides()`

**Changes:**
- Iterates through list of custom field entries
- Creates separate `CustomFieldInstance` for each entry in the list
- Properly handles duplicate field IDs

```python
if self.metadata.custom_fields:
    field_ids = {cf["field_id"] for cf in self.metadata.custom_fields}
    fields_by_id = {
        field.id: field
        for field in CustomField.objects.filter(id__in=field_ids)
    }
    for cf_data in self.metadata.custom_fields:
        field_id = cf_data["field_id"]
        field = fields_by_id.get(field_id)
        if field:
            # Create instance for each entry
            CustomFieldInstance.objects.create(...)
```

#### 3. Workflow System (`src/documents/signals/handlers.py`)

**Function:** `run_workflows()`

**Changes:**
- Workflow actions now use list format for custom fields
- Assignment actions append to list using `extend()`
- Removal actions filter list instead of using dict operations

```python
# Assignment
overrides.custom_fields.extend([
    {"field_id": field.pk, "value": value}
    for field in action.assign_custom_fields.all()
])

# Removal
overrides.custom_fields = [
    cf for cf in overrides.custom_fields
    if cf["field_id"] not in field_ids_to_remove
]
```

#### 4. API Serializer (`src/documents/serialisers.py`)

**`CustomFieldInstanceSerializer.create()`:**

**Before:**
```python
instance, _ = CustomFieldInstance.objects.update_or_create(
    document=document,
    field=custom_field,
    defaults={data_store_name: validated_data["value"]},
)
```

**After:**
```python
instance = CustomFieldInstance.objects.create(
    document=document,
    field=custom_field,
    **{data_store_name: validated_data["value"]},
)
```

**`DocumentSerializer.update()`:**

Added logic to delete existing custom field instances before creating new ones:

```python
if "custom_fields" in validated_data:
    incoming_custom_fields = [
        field["field"] for field in validated_data["custom_fields"]
    ]
    # Delete all existing instances for fields being updated
    if incoming_custom_fields:
        instance.custom_fields.filter(field__in=incoming_custom_fields).delete()
```

This ensures clean state during PATCH operations and prevents accumulation of old instances.

### Frontend Changes

#### Custom Fields Dropdown Component

**File:** `src-ui/src/app/components/common/custom-fields-dropdown/`

**Changes:**

1. **Removed field filtering logic:**
   ```typescript
   // Before: Filtered out used fields with +10 hack
   this.unusedFields = this.customFields.filter(
     (f) => !this.existingFields?.find((e) => e.field === f.id + 10)
   )

   // After: All fields always available
   this.unusedFields = this.customFields
   ```

2. **Added instance count indicator:**
   ```typescript
   getFieldInstanceCount(fieldId: number): number {
     return this.existingFields?.filter((e) => e.field === fieldId).length || 0
   }
   ```

3. **UI Enhancement:**
   - Badge showing number of existing instances
   - Tooltip: "Already used X time(s)"
   - All fields remain selectable regardless of usage

## API Usage

### Request Format

The API accepts a list of custom field instances:

```json
{
  "custom_fields": [
    {"field": 1, "value": "first value"},
    {"field": 2, "value": "some other field"},
    {"field": 1, "value": "second value"}
  ]
}
```

### Response Format

The API returns all instances:

```json
{
  "custom_fields": [
    {"field": 1, "value": "first value"},
    {"field": 2, "value": "some other field"},
    {"field": 1, "value": "second value"}
  ]
}
```

### PATCH Behavior

When updating custom fields via PATCH:

1. All existing instances of the specified field IDs are deleted
2. New instances are created from the request data
3. This ensures clean state and prevents orphaned instances

**Example:**

```bash
# Document initially has field 1 with values ["a", "b"]
PATCH /api/documents/123/
{
  "custom_fields": [
    {"field": 1, "value": "c"},
    {"field": 1, "value": "d"},
    {"field": 1, "value": "e"}
  ]
}

# Result: field 1 now has values ["c", "d", "e"]
# Old values ["a", "b"] are deleted
```

## Performance Considerations

### Index Performance

The composite index `docs_cfi_doc_field_idx` on `(document, field)` ensures efficient queries:

```sql
-- Efficient with index
SELECT * FROM documents_customfieldinstance
WHERE document_id = 123 AND field_id = 1;

-- Index covers this query pattern
DELETE FROM documents_customfieldinstance
WHERE document_id = 123 AND field_id IN (1, 2, 3);
```

### Query Patterns

Common queries remain efficient:

- Filtering instances by document and field
- Counting instances per field
- Deleting instances during updates
- Retrieving all instances for a document

## Migration Guide

### For Existing Installations

1. **Backup database** before running migrations
2. Run migration: `python manage.py migrate`
3. No data migration needed - existing single instances work unchanged
4. New functionality is immediately available

### For Custom Code

If you have custom code that accesses `DocumentMetadataOverrides.custom_fields`:

**Before:**
```python
overrides.custom_fields = {field.id: "value"}
overrides.custom_fields[field.id] = "new_value"
```

**After:**
```python
overrides.custom_fields = [{"field_id": field.id, "value": "value"}]
overrides.custom_fields.append({"field_id": field.id, "value": "new_value"})
```

## Testing

### New Tests

1. **Consumer Test:** `test_consumer.py::testOverrideCustomFieldsMultiple()`
   - Tests multiple instances through consumer
   - Verifies all values are stored

2. **API Test:** `test_api_custom_fields.py::test_multiple_custom_field_instances_same_field()`
   - Tests PATCH with duplicate field IDs
   - Verifies response contains all instances

### Running Tests

```bash
# Run custom field tests
python src/manage.py test documents.tests.test_api_custom_fields
python src/manage.py test documents.tests.test_consumer

# Run all document tests
python src/manage.py test documents
```

## Backward Compatibility

- ✅ Existing documents with single custom field instances work unchanged
- ✅ API format already supported list syntax
- ✅ Frontend displays correctly with count indicators
- ⚠️ Internal `DocumentMetadataOverrides` format changed (affects custom code only)

## References

- Model: `src/documents/models.py` (line 824-948)
- Serializer: `src/documents/serialisers.py` (line 737-761, 1024-1049)
- Consumer: `src/documents/consumer.py` (line 725-746)
- Workflows: `src/documents/signals/handlers.py` (line 900-914, 1078-1085)
- Frontend: `src-ui/src/app/components/common/custom-fields-dropdown/`

---

**Last Updated:** October 2025
**Maintained By:** Garden of Concepts
