-- Open cyber CVE severity: published CVE counts per severity tier and vendor.
MODEL (
  name dev.mv_open_cyber_vuln_cve_severity,
  kind FULL,
  dialect postgres,
  description 'Per (severity_tier, vendor): published CVE count and last_cve_at.',
  grain [severity_tier, vendor],
  tags [open_cyber, vuln, cve, severity]
);

SELECT
  severity_tier,
  vendor,
  COUNT(*) AS cve_count,
  MAX(created_at) AS last_cve_at
FROM vertex_open_cyber_vuln_cve
WHERE status = 'published'
GROUP BY severity_tier, vendor
