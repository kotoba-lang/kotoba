-- SQLMesh audit: mv_robotics_ems_company_readiness invariants.
-- Returns rows that FAIL the audit condition (zero rows = audit passes).

AUDIT (
  name assert_robotics_ems_verified_le_certification,
  model dev.mv_robotics_ems_company_readiness,
  dialect postgres,
  description 'verified_certification_count must not exceed certification_count.'
);
SELECT *
FROM dev.mv_robotics_ems_company_readiness
WHERE verified_certification_count > certification_count;

---

AUDIT (
  name assert_robotics_ems_counts_nonnegative,
  model dev.mv_robotics_ems_company_readiness,
  dialect postgres,
  description 'capability_count, certification_count, verified_certification_count must be >= 0.'
);
SELECT *
FROM dev.mv_robotics_ems_company_readiness
WHERE capability_count < 0
   OR certification_count < 0
   OR verified_certification_count < 0;
