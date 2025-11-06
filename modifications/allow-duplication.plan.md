<!-- 59b460f2-02da-4893-9967-ad4f037ce2f2 d0ad845c-b9f2-4c16-baeb-173896f9c5bd -->
# Allow duplicate document uploads (global)

## Changes

- Backend: Make duplicate preflight a no-op so ingestion doesn’t block.
  - Update `src/documents/consumer.py` `ConsumerPreflightPlugin.pre_check_duplicate` to return without failing/log only.
  - Keep call sites intact; method will no-op.
- Data model: Allow non-unique checksums while preserving query performance.
  - Edit `src/documents/models.py` `Document.checksum` to remove `unique=True` and add `db_index=True`.
  - Create a Django migration to drop the unique index and add a non-unique index.

## Key snippets (for context)

- Current duplicate check that fails ingestion:
```787:809:src/documents/consumer.py
existing_doc = Document.global_objects.filter(
    Q(checksum=checksum) | Q(archive_checksum=checksum),
)
if existing_doc.exists():
    ...
    self._fail(msg, log_msg)
```

- Current unique checksum definition:
```219:225:src/documents/models.py
checksum = models.CharField(
    max_length=32,
    editable=False,
    unique=True,
)
```


## Migration

- Create a new migration in `src/documents/migrations/` that:
  - Alters `documents.Document.checksum` to `unique=False, db_index=True`.
  - Depends on the latest migration number (sequential as per repo).

## Validation

- Reset dev DB or run migrations forward.
- Upload the same file twice via API `POST /api/documents/post_document/` and verify both succeed.
- Optional: filter by `?checksum__iexact=...` still works (now returns multiple rows).

### To-dos

- [ ] No-op duplicate preflight in consumer.py to not block ingestion
- [ ] Remove unique and add db_index to Document.checksum in models.py
- [ ] Create migration to drop unique index and add non-unique index
- [ ] Run migrations locally and verify schema
- [ ] Upload same file twice via API and confirm success