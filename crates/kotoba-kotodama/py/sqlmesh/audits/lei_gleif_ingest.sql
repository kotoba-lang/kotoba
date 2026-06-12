-- SQLMesh audit: mv_open_lei_gleif_ingest_status invariants.
-- Returns rows that FAIL the audit condition (zero rows = audit passes).

AUDIT (
  name assert_gleif_written_le_read,
  model dev.mv_open_lei_gleif_ingest_status,
  dialect postgres,
  description 'records_written must not exceed records_read.'
);
SELECT *
FROM dev.mv_open_lei_gleif_ingest_status
WHERE records_written IS NOT NULL
  AND records_read IS NOT NULL
  AND records_written > records_read;

---

AUDIT (
  name assert_gleif_errors_le_read,
  model dev.mv_open_lei_gleif_ingest_status,
  dialect postgres,
  description 'error_count must not exceed records_read.'
);
SELECT *
FROM dev.mv_open_lei_gleif_ingest_status
WHERE error_count IS NOT NULL
  AND records_read IS NOT NULL
  AND error_count > records_read;
