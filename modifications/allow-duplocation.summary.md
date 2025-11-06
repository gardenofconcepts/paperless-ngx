# Allow Duplicate Document Uploads - Implementation Summary

## Overview
Paperless-ngx now allows adding the same document multiple times. Previously, the system blocked duplicate documents by checking the MD5 checksum of the original file against existing documents.

## Changes Made

### 1. Backend - Consumer Preflight (`src/documents/consumer.py`)
**File**: `/src/documents/consumer.py` (lines 787-792)

Changed the `ConsumerPreflightPlugin.pre_check_duplicate()` method from a validation check to a no-op:
- **Before**: Rejected documents if checksum matched existing document
- **After**: Method now passes without checking, allowing duplicates through

```python
def pre_check_duplicate(self):
    """
    Duplicate documents are now allowed.
    This method is kept for backwards compatibility but performs no checks.
    """
    pass
```

### 2. Data Model - Document.checksum (`src/documents/models.py`)
**File**: `/src/documents/models.py` (lines 219-226)

Modified the `checksum` field to allow non-unique values:
- **Changed**: `unique=True` → `unique=False`
- **Added**: `db_index=True` for query performance

```python
checksum = models.CharField(
    _("checksum"),
    max_length=32,
    editable=False,
    unique=False,        # Now allows duplicates
    db_index=True,       # Keep queries fast
    help_text=_("The checksum of the original document."),
)
```

### 3. Database Migration (`src/documents/migrations/1077_alter_document_checksum.py`)

Created migration #1077 to:
- Drop the unique constraint on `Document.checksum`
- Add a non-unique index for query performance

The migration properly depends on the previous migration (1076) to ensure sequential ordering.

### 4. Tests Updated (`src/documents/tests/test_consumer.py`)

Updated two tests that previously expected duplicate rejection:

**`test_delete_duplicate()` (lines 728-761)**
- Now verifies that two documents with identical checksums can be created
- Confirms they have different primary keys but same checksum

**`test_no_delete_duplicate()` (lines 763-796)**
- Updated to verify duplicate consumption succeeds
- Validates the behavior mirrors `test_delete_duplicate`

## Behavior Changes

### Before
- First document upload: ✓ Success
- Second upload of same file: ✗ Rejected with "document_already_exists" error
- Setting `CONSUMER_DELETE_DUPLICATES=True` would delete the duplicate file
- Setting `CONSUMER_DELETE_DUPLICATES=False` would keep the file but fail consumption

### After
- First document upload: ✓ Success
- Second upload of same file: ✓ Success (creates new document)
- Both documents have identical checksums
- Each document receives a unique ID and filename
- `CONSUMER_DELETE_DUPLICATES` setting is now ignored (always allows duplicates)

## API Impact

The API endpoint `/api/documents/post_document/` now:
- Accepts multiple uploads of identical files
- Each upload creates a new document with a unique ID
- Checksum queries (e.g., `?checksum__iexact=ABC123`) now return multiple results if duplicates exist

## Database Impact

The migration will:
1. Remove the unique constraint on `documents_document.checksum`
2. Add a non-unique index on `documents_document.checksum` for query performance

This is backward compatible - existing data is unaffected.

## Technical Notes

- Checksum comparison uses MD5 hash of the original file
- Archive files (`archive_checksum`) are separate and not affected
- The `pre_check_duplicate()` method remains in place for backward compatibility but performs no action
- File naming is still unique per document, preventing file system clashes

