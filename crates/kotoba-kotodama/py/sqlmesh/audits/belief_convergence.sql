-- Audits for mv_belief_convergence (ADR-2605080500)

AUDIT (
  name assert_no_null_convergence_status,
  model dev.mv_belief_convergence
)
SELECT *
FROM dev.mv_belief_convergence
WHERE convergence_status IS NULL;

AUDIT (
  name assert_abs_deviation_nonneg,
  model dev.mv_belief_convergence
)
SELECT *
FROM dev.mv_belief_convergence
WHERE abs_deviation < 0;
