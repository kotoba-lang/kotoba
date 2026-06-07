-- Gov org runtime: runtime key projection for government organization records.
MODEL (
  name dev.mv_gov_org_runtime,
  kind FULL,
  dialect postgres,
  description 'Gov org runtime keys: entity_kind + entity_id concatenated as runtime_key with latest metadata.',
  grain [runtime_key],
  tags [gov, org, runtime]
);

SELECT
  entity_kind || ':' || entity_id AS runtime_key,
  entity_kind,
  entity_id,
  last_seq,
  last_ts_ms,
  record_count
FROM dev.mv_gov_record_dedup
WHERE entity_kind = 'com.etzhayyim.apps.gov.org'
