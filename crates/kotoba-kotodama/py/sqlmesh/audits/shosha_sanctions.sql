-- Audits for mv_shosha_sanctions_count_by_source (ADR-2605080500)

AUDIT (
  name assert_sanctions_active_count_positive,
  model dev.mv_shosha_sanctions_count_by_source
)
SELECT *
FROM dev.mv_shosha_sanctions_count_by_source
WHERE active_count <= 0;

AUDIT (
  name assert_sanctions_list_source_not_null,
  model dev.mv_shosha_sanctions_count_by_source
)
SELECT *
FROM dev.mv_shosha_sanctions_count_by_source
WHERE list_source IS NULL;
