# Extended Custom Fields Modification

## Overview

This modification extends the custom fields functionality in Paperless-ngx by adding new field properties and data types, providing enhanced flexibility for document metadata management.
**Date**: April 30, 2025

---

## Summary of Changes

This PR introduces significant enhancements to the custom fields system:

1. **New Custom Field Properties**: Added `label`, `group`, `hidden`, and `order` fields
2. **New Data Types**: Added `JSON` and `Text` (multiline) field types
3. **Improved UI**: Updated frontend components to support new properties and data types
4. **Enhanced Filtering**: Extended query filtering to support new data types

---

## Backend Changes

### Models (`src/documents/models.py`)

#### CustomField Model
Added new fields to the `CustomField` model:

- **`label`** (TextField, nullable): A user-facing label for the field, providing a display name separate from the internal name
- **`group`** (TextField, nullable): Groups related fields together for organizational purposes
- **`hidden`** (BooleanField, default=False): Hides the field from the user interface when set to true
- **`order`** (IntegerField, default=0): Determines the display order of custom fields

**New Data Types**:
- **`JSON`**: Stores structured JSON data
- **`TEXT`**: Stores multiline text content (different from the existing single-line string type)

#### CustomFieldInstance Model
Added new value storage fields:

- **`value_json`** (JSONField): Stores JSON data for JSON-type custom fields
- **`value_text_multiline`** (TextField): Stores multiline text for Text-type custom fields

Updated the `VALUE_TO_FIELD_MAPPING` dictionary to include:
```python
CustomField.FieldDataType.JSON: "value_json"
CustomField.FieldDataType.TEXT: "value_text_multiline"
```

#### Ordering Changes
Changed the default ordering of CustomField from `("created",)` to `("order",)` to support user-defined field ordering.

### Filters (`src/documents/filters.py`)

Extended the `ALLOWED_LOOKUPS` dictionary to include filtering support for new data types:
- JSON fields: supports "basic", "string", and "arithmetic" lookups
- Text fields: supports "basic" and "string" lookups

Added query annotation handling for both new data types in the `filter_queryset` method.

### Serializers (`src/documents/serialisers.py`)

Updated the CustomField serializer to include new fields in the Meta class:
- `label`
- `hidden`
- `group`
- `order`

### Views (`src/documents/views.py`)

Updated the CustomFieldViewSet queryset ordering from `order_by("-created")` to `order_by("order")` to respect the new ordering field.

### Database Migration

**File**: `src/documents/migrations/1101_alter_customfield_options_customfield_group_and_more.py`

The migration includes:
1. Adding the four new fields to CustomField model
2. Adding value storage fields to CustomFieldInstance
3. Updating the data_type choices to include 'json' and 'text'
4. Altering model ordering options
5. Updating the remark field to be nullable

---

## Frontend Changes

### TypeScript Models

#### Custom Field Data Types (`src-ui/src/app/data/custom-field.ts`)
Added two new enum values:
- `JSON = 'json'`
- `Text = 'text'`

#### Custom Field Interface (`src-ui/src/app/data/custom-field.ts`)
Extended the CustomField interface with:
- `label?: string`
- `group?: string`
- `hidden?: boolean`
- `order?: number`

### Components

#### Custom Field Edit Dialog (`custom-field-edit-dialog.component.ts`)

**Form Updates**:
Added new form controls:
```typescript
label: new FormControl(null)
group: new FormControl(null)
hidden: new FormControl(false)
order: new FormControl(0)
```

**Template Updates** (`custom-field-edit-dialog.component.html`):
- Added text input for `label` field
- Added text input for `group` field
- Added checkbox for `hidden` field
- Added number input for `order` field

#### Custom Fields Values Component (`custom-fields-values.component.html`)

Added UI handling for new data types:
- **JSON**: Uses textarea component for JSON input
- **Text**: Uses textarea component for multiline text input

#### Document Detail Component

**TypeScript** (`document-detail.component.ts`):
- Added `getCustomFieldLabelFromInstance()` method to retrieve the label or fall back to the name
- Imported `TextAreaComponent` for multiline text support

**Template** (`document-detail.component.html`):
- Added display cases for JSON and Text data types
- Both use textarea components for editing

#### Custom Fields Management Component (`custom-fields.component.html`)

Updated the table view to display:
- **Label** column (with eye-slash icon for hidden fields)
- **Group** column
- Displays the new properties in the management interface

### Query Support (`src-ui/src/app/data/custom-field-query.ts`)

Extended `CUSTOM_FIELD_QUERY_TYPES` to include lookup support for:
- JSON: basic, string, arithmetic
- Text: basic, string

---

## Use Cases

### 1. Grouping Related Fields
Use the `group` property to organize related custom fields together, e.g., all invoice-related fields in an "Invoice" group.

### 2. User-Friendly Labels
Use the `label` property to provide clear, user-facing names while maintaining technical internal names.

### 3. Hidden Technical Fields
Set `hidden: true` for fields that should be populated programmatically but not displayed in the UI.

### 4. Custom Display Order
Use the `order` field to control the sequence in which custom fields appear in the interface.

### 5. Structured Data Storage
Use the JSON data type to store complex, structured metadata (e.g., nested address information, configuration objects).

### 6. Long-Form Text
Use the Text data type for fields requiring multiline input (e.g., notes, descriptions, comments).

---

## Database Schema Impact

The migration adds the following columns:

**CustomField table**:
- `label` (TEXT, nullable)
- `group` (TEXT, nullable)
- `hidden` (BOOLEAN, default=False)
- `order` (INTEGER, default=0)

**CustomFieldInstance table**:
- `value_json` (JSONFIELD, nullable)
- `value_text_multiline` (TEXT, nullable)

---

## Breaking Changes

### Ordering Change
The default ordering of custom fields has changed from creation date (`created`) to the `order` field. Existing custom fields will have `order=0` by default, so their relative ordering should be maintained by their creation date until explicitly changed.

### Remark Field
The `remark` field is now nullable, allowing it to be omitted entirely rather than requiring an empty string.

---

## Testing Considerations

When testing this modification, verify:

1. **New field creation** with all new properties
2. **JSON data type** validation and storage
3. **Text data type** multiline input and display
4. **Field ordering** in the UI respects the `order` property
5. **Hidden fields** do not appear in the UI but are still queryable
6. **Grouping** displays correctly in management views
7. **Label fallback** to name when label is not provided
8. **Query filtering** works correctly for JSON and Text types
9. **Migration** runs successfully on existing databases
10. **Backward compatibility** with existing custom fields

---

## API Changes

### CustomField Endpoint

**New fields returned** in GET requests:
```json
{
  "id": 1,
  "name": "invoice_number",
  "label": "Invoice Number",
  "group": "Invoice Details",
  "hidden": false,
  "order": 10,
  "remark": "Internal invoice tracking",
  "data_type": "string",
  "extra_data": {}
}
```

**New fields accepted** in POST/PATCH requests:
- `label` (string, optional)
- `group` (string, optional)
- `hidden` (boolean, default: false)
- `order` (integer, default: 0)

### New Data Types

When creating fields with new data types:

**JSON field**:
```json
{
  "name": "metadata",
  "label": "Additional Metadata",
  "data_type": "json"
}
```

**Text field**:
```json
{
  "name": "notes",
  "label": "Document Notes",
  "data_type": "text"
}
```

---

## Migration Path

For existing Paperless-ngx installations:

1. **Backup your database** before applying this modification
2. Run migrations: `python manage.py migrate`
3. Existing custom fields will have:
   - `label`: NULL (will display the `name` as fallback)
   - `group`: NULL (ungrouped)
   - `hidden`: False (visible)
   - `order`: 0 (maintains relative order by creation date)
4. Update existing custom fields as needed through the admin interface

---

## Related Files

### Backend
- `src/documents/models.py`
- `src/documents/filters.py`
- `src/documents/serialisers.py`
- `src/documents/views.py`
- `src/documents/migrations/1101_alter_customfield_options_customfield_group_and_more.py`

### Frontend
- `src-ui/src/app/data/custom-field.ts`
- `src-ui/src/app/data/custom-field-query.ts`
- `src-ui/src/app/components/common/edit-dialog/custom-field-edit-dialog/`
- `src-ui/src/app/components/common/input/custom-fields-values/`
- `src-ui/src/app/components/document-detail/`
- `src-ui/src/app/components/manage/custom-fields/`
