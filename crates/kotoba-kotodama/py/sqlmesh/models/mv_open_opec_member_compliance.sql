-- Open OPEC member compliance: published compliance reports per member country and reliability tier.
MODEL (
  name dev.mv_open_opec_member_compliance,
  kind FULL,
  dialect postgres,
  description 'Per (member_country, reliability_tier): report count, avg compliance pct, latest reported.',
  grain [member_country, reliability_tier],
  tags [open_opec, compliance, member]
);

SELECT
  member_country,
  reliability_tier,
  COUNT(*) AS report_count,
  AVG(compliance_pct) AS avg_compliance,
  MAX(reported_at) AS latest_reported
FROM vertex_open_opec_compliance_report
WHERE status = 'published'
GROUP BY member_country, reliability_tier
