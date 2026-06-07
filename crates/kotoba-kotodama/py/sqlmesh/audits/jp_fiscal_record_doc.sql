-- SQLMesh audit: mv_jp_fiscal_record_document_coverage invariants.
-- Returns rows that FAIL the audit condition (zero rows = audit passes).

AUDIT (
  name assert_jp_fiscal_record_doc_id_consistency,
  model dev.mv_jp_fiscal_record_document_coverage,
  dialect postgres,
  description 'has_document_id=false implies document_id IS NULL; has_document_id=true implies document_id IS NOT NULL.'
);
SELECT *
FROM dev.mv_jp_fiscal_record_document_coverage
WHERE (has_document_id = TRUE AND document_id IS NULL)
   OR (has_document_id = FALSE AND document_id IS NOT NULL);

---

AUDIT (
  name assert_jp_fiscal_record_doc_vertex_implies_id,
  model dev.mv_jp_fiscal_record_document_coverage,
  dialect postgres,
  description 'has_document_vertex=true implies has_document_id=true (cannot have a doc vertex without an ID).'
);
SELECT *
FROM dev.mv_jp_fiscal_record_document_coverage
WHERE has_document_vertex = TRUE AND has_document_id = FALSE;
