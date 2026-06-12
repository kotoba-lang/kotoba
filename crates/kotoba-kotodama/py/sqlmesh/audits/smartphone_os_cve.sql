-- SQLMesh audit: mv_open_smartphone_os_cve_exposure invariants.
-- Returns rows that FAIL the audit condition (zero rows = audit passes).

AUDIT (
  name assert_smartphone_os_open_blobs_bounded,
  model dev.mv_open_smartphone_os_cve_exposure,
  dialect postgres,
  description 'open_blobs_pct must be in [0, 100] when present.'
);
SELECT *
FROM dev.mv_open_smartphone_os_cve_exposure
WHERE open_blobs_pct IS NOT NULL
  AND (open_blobs_pct < 0 OR open_blobs_pct > 100);

---

AUDIT (
  name assert_smartphone_os_build_id_present,
  model dev.mv_open_smartphone_os_cve_exposure,
  dialect postgres,
  description 'os_build_id must be NOT NULL (PK).'
);
SELECT *
FROM dev.mv_open_smartphone_os_cve_exposure
WHERE os_build_id IS NULL;
