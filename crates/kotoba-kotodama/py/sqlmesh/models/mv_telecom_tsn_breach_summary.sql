-- Telecom TSN breach summary: TSN SLA breach counts per kind/severity/status.
MODEL (
  name dev.mv_telecom_tsn_breach_summary,
  kind FULL,
  dialect postgres,
  description 'Per (breach_kind, severity, status): TSN SLA breach count.',
  grain [breach_kind, severity, status],
  tags [telecom, tsn, sla, breach]
);

SELECT
  breach_kind,
  severity,
  status,
  COUNT(*) AS breach_count
FROM vertex_telecom_tsn_sla_breach
GROUP BY breach_kind, severity, status
