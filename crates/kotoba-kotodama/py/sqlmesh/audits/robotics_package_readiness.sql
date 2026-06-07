-- SQLMesh audit: mv_robotics_manufacturing_package_readiness invariants.
-- Returns rows that FAIL the audit condition (zero rows = audit passes).

AUDIT (
  name assert_robotics_package_required_consistent,
  model dev.mv_robotics_manufacturing_package_readiness,
  dialect postgres,
  description 'present + missing required files must equal required_file_count.'
);
SELECT *
FROM dev.mv_robotics_manufacturing_package_readiness
WHERE present_required_file_count + missing_required_file_count <> required_file_count;

---

AUDIT (
  name assert_robotics_package_required_le_total,
  model dev.mv_robotics_manufacturing_package_readiness,
  dialect postgres,
  description 'required_file_count must not exceed file_count.'
);
SELECT *
FROM dev.mv_robotics_manufacturing_package_readiness
WHERE required_file_count > file_count;
