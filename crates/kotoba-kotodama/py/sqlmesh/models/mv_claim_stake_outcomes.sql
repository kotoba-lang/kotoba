-- Claim stake outcome counts grouped by state with bond set indicator.
MODEL (
  name dev.mv_claim_stake_outcomes,
  kind FULL,
  dialect postgres,
  description 'Per-state claim count and bond-set count from vertex_claim_stake.',
  grain [state],
  tags [claim, stake, outcome, bond, state]
);

SELECT
  state,
  COUNT(*)                                              AS claim_count,
  SUM(CASE WHEN bond IS NULL THEN 0 ELSE 1 END)         AS bond_set_count
FROM vertex_claim_stake
GROUP BY state
