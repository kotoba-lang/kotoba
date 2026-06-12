-- SQLMesh audit: mv_jp_fiscal_collection_record_coverage invariants.
-- Returns rows that FAIL the audit condition (zero rows = audit passes).

AUDIT (
  name assert_jp_fiscal_collection_record_subset_counts_le_total,
  model dev.mv_jp_fiscal_collection_record_coverage,
  dialect postgres,
  description 'record_with_*_count and evidenced_record_count must not exceed record_count.'
);
SELECT *
FROM dev.mv_jp_fiscal_collection_record_coverage
WHERE record_with_document_id_count > record_count
   OR record_with_document_vertex_count > record_count
   OR evidenced_record_count > record_count;

---

AUDIT (
  name assert_jp_fiscal_collection_record_count_positive,
  model dev.mv_jp_fiscal_collection_record_coverage,
  dialect postgres,
  description 'record_count must be > 0 (group rows imply at least one record).'
);
SELECT *
FROM dev.mv_jp_fiscal_collection_record_coverage
WHERE record_count <= 0;
