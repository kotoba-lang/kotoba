-- OS budget balance: per-agent allocation sum.
MODEL (
  name dev.mv_os_budget_balance,
  kind FULL,
  dialect postgres,
  description 'Per agent_id: SUM(amount) from vertex_os_budget_allocation.',
  grain [agent_id],
  tags [os, budget, balance]
);

SELECT
  agent_id,
  SUM(amount) AS balance
FROM vertex_os_budget_allocation
GROUP BY agent_id
