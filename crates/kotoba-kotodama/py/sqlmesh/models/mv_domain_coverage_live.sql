-- Domain coverage live: seed vs target counts using safe_divide() UDF.
-- Rebuilt 2026-04-16 to use SQL UDF safe_divide() instead of inline CASE.
MODEL (
  name dev.mv_domain_coverage_live,
  kind FULL,
  dialect postgres,
  description 'Domain coverage ratios: live_did/record counts vs seed/target with safe_divide().',
  grain [kind, repo],
  tags [coverage, domain, actor]
);

SELECT
  t.kind,
  t.repo,
  t.app,
  t.authority_kind,
  t.authority_seed,
  t.rule_seed,
  t.scope_seed,
  t.total_seed,
  t.authority_target,
  t.rule_target,
  t.scope_target,
  t.total_target,
  COALESCE(d.did_count, 0)                                    AS did_count,
  COALESCE(a.authority_count, 0)                              AS authority_count,
  COALESCE(d.did_count, 0) + COALESCE(a.authority_count, 0)  AS live_record_count,
  safe_divide(
    COALESCE(d.did_count, 0)::double precision,
    t.total_target::double precision,
    0.0
  )                                                           AS live_coverage_did,
  safe_divide(
    (COALESCE(d.did_count, 0) + COALESCE(a.authority_count, 0))::double precision,
    t.total_target::double precision,
    0.0
  )                                                           AS live_coverage_record,
  safe_divide(
    t.total_seed::double precision,
    t.total_target::double precision,
    0.0
  )                                                           AS authority_rate,
  safe_divide(
    (t.total_seed - COALESCE(d.did_count, 0))::double precision,
    t.total_target::double precision,
    0.0
  )                                                           AS delta_did,
  safe_divide(
    (t.total_seed - (COALESCE(d.did_count, 0) + COALESCE(a.authority_count, 0)))::double precision,
    t.total_target::double precision,
    0.0
  )                                                           AS delta_record
FROM dim_domain_coverage_target t
LEFT JOIN mv_domain_repo_did_count d
  ON d.kind = t.kind AND d.repo = t.repo
LEFT JOIN mv_domain_repo_authority_count a
  ON a.authority_kind = t.authority_kind AND a.repo = t.repo
