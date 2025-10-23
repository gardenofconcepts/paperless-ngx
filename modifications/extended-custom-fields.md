# Extended Custom Fields

This modification extends the custom fields functionality in Paperless-ngx with additional properties and data types to provide more flexibility and organization capabilities.

## Overview

The extended custom fields feature adds the following enhancements:

1. **Additional Field Properties**: New metadata fields for better organization and display control
2. **New Data Type**: JSON data type for storing structured data
3. **Improved UI**: Enhanced management interface with better visualization

## New Field Properties

### Label
- **Type**: Text (optional)
- **Purpose**: A user-facing label that can be different from the internal field name
- **Use Case**: Display a more descriptive or localized label in the UI while maintaining a consistent internal name

### Group
- **Type**: Text (optional)
- **Purpose**: Group related custom fields together
- **Use Case**: Organize fields by category (e.g., "Financial", "Legal", "Technical") for better visualization and management

### Hidden
- **Type**: Boolean (default: false)
- **Purpose**: Hide a field from the standard user interface
- **Use Case**: Store metadata that should not be visible to regular users but can be accessed programmatically or by administrators
- **Indicator**: Hidden fields are marked with an eye-slash icon (🚫👁) in the management interface

### Order
- **Type**: Integer (default: 0)
- **Purpose**: Control the display order of custom fields
- **Use Case**: Define a specific sequence for displaying fields, overriding the default creation-date-based ordering
- **Note**: Fields are now ordered by this property instead of creation date

## New Data Type

### JSON
- **Type**: JSON object
- **Storage**: Native JSONField in the database
- **Use Case**: Store structured data, complex objects, or nested information
- **Input**: Textarea component for entering JSON-formatted data
- **Query Support**: Basic and string operations (exact matching, contains, icontains)

## Database Changes

### Migration: 1075_alter_customfield_options_customfield_group_and_more

This migration adds:
- New fields to `CustomField` model: `label`, `group`, `hidden`, `order`
- New field to `CustomFieldInstance` model: `value_json`
- Updated `data_type` choices to include JSON
- Changed model ordering from `created` to `order`
- Updated `remark` field to allow null values

## API Changes

### CustomField Serializer

The CustomField API now includes the following additional fields in responses:

```json
{
  "id": 1,
  "name": "invoice_number",
  "label": "Invoice Number",
  "group": "Financial",
  "remark": "Invoice reference number",
  "hidden": false,
  "order": 10,
  "data_type": "string",
  "extra_data": {},
  "document_count": 42
}
```

### Supported Data Types

The following data types are now supported:
- `string`: Short text (max 128 characters)
- `url`: URL field
- `date`: Date field
- `boolean`: True/False value
- `integer`: Whole number
- `float`: Decimal number
- `monetary`: Currency value
- `documentlink`: Link to other documents
- `select`: Dropdown selection
- `longtext`: Long multiline text (existing)
- `json`: **NEW** - JSON structured data

## UI Changes

### Custom Fields Management View

The management interface now displays:
- **Name** column: The internal field name with remark icon (ℹ️) if present
- **Label** column: The user-facing label
- **Group** column: The grouping category
- **Data Type** column: The field type
- **Actions** column: Edit and Delete buttons
- **Hidden indicator**: Eye-slash icon (🚫👁) next to hidden fields

### Custom Field Edit Dialog

When creating or editing a custom field, the following new fields are available:
- **Name**: Internal field name (required)
- **Label**: Display label (optional)
- **Group**: Category group (optional)
- **Remark**: Administrative note (optional)
- **Hidden**: Checkbox to hide from UI (default: unchecked)
- **Order**: Display order number (default: 0)
- **Data Type**: Field type selector (cannot be changed after creation)

### Document Detail View

Custom fields are displayed in the order specified by the `order` property. Hidden fields are not displayed in the standard view but remain accessible through the API.

For JSON fields, a textarea input is provided for entering or editing JSON-formatted data.

## Query Support

### JSON Field Queries

JSON fields support the following query operators:
- **Basic**: `exists`, `isnull`
- **String**: `icontains` (case-insensitive contains)

Example custom field queries:
```json
{
  "operator": "AND",
  "operands": [
    {
      "field": "metadata_field",
      "operator": "exists",
      "value": true
    }
  ]
}
```

## Best Practices

### Naming Conventions
- **name**: Use lowercase with underscores (e.g., `invoice_number`, `project_code`)
- **label**: Use proper capitalization and spaces (e.g., "Invoice Number", "Project Code")
- **group**: Use consistent category names across related fields

### Field Ordering
- Use increments of 10 for the `order` field (0, 10, 20, ...) to allow for easy insertion of fields between existing ones
- Group related fields with similar order numbers

### Hidden Fields
- Use hidden fields for:
  - System-generated metadata
  - Internal tracking fields
  - Fields that should only be modified programmatically
- Do not use hidden fields for sensitive information that should be protected by permissions

### JSON Fields
- Store valid JSON data to ensure proper querying
- Use JSON fields for:
  - Structured metadata
  - Lists or arrays
  - Nested object data
  - Complex data that doesn't fit standard field types
- Consider using Long Text fields for simple multiline text instead of JSON

## Migration from Standard Custom Fields

Existing custom fields will continue to work without modification. The new properties have sensible defaults:
- `label`: null (falls back to displaying `name`)
- `group`: null (no grouping)
- `hidden`: false (visible)
- `order`: 0 (existing fields will have default order)

To take advantage of the new features:
1. Edit existing fields to add labels and group names
2. Set order values to control display sequence
3. Mark internal/system fields as hidden if appropriate

## Compatibility Notes

### Long Text vs JSON
This implementation does **not** include the TEXT data type from the original patch because Paperless-ngx already provides a LONG_TEXT (`longtext`) data type that serves the same purpose for multiline text input. Use LONG_TEXT for simple text areas and JSON for structured data.

### Backend Ordering
The CustomField view is now ordered by the `order` field instead of `created` timestamp. This ensures consistent field ordering across the application.

### Frontend Display
The field label (if set) or name is displayed in the UI. Labels provide flexibility for internationalization and user-friendly display names while maintaining stable internal field names.

## Technical Implementation

### Backend Changes
- **models.py**: Added new fields to `CustomField` and `CustomFieldInstance` models
- **serialisers.py**: Updated `CustomFieldSerializer` to include new fields
- **filters.py**: Added JSON data type support to custom field query parser
- **views.py**: Changed ordering from `created` to `order`

### Frontend Changes
- **TypeScript**: Updated `CustomField` interface and `CustomFieldDataType` enum
- **Components**: Enhanced edit dialog, management view, and document detail components
- **Templates**: Added form controls for new properties and JSON field support
