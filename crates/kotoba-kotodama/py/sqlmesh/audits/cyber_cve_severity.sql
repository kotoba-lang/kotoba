-- SQLMesh audit: mv_open_cyber_vuln_cve_severity invariants.
-- Returns rows that FAIL the audit condition (zero rows = audit passes).

AUDIT (
  name assert_cve_severity_count_positive,
  model dev.mv_open_cyber_vuln_cve_severity,
  dialect postgres,
  description 'cve_count must be > 0 (group rows imply at least one published CVE).'
);
SELECT *
FROM dev.mv_open_cyber_vuln_cve_severity
WHERE cve_count <= 0;

---

AUDIT (
  name assert_cve_severity_tier_known,
  model dev.mv_open_cyber_vuln_cve_severity,
  dialect postgres,
  description 'severity_tier must be one of critical/high/medium/low/none/unknown (CVSS standard).'
);
SELECT *
FROM dev.mv_open_cyber_vuln_cve_severity
WHERE severity_tier IS NOT NULL
  AND LOWER(severity_tier) NOT IN ('critical', 'high', 'medium', 'low', 'none', 'unknown');
