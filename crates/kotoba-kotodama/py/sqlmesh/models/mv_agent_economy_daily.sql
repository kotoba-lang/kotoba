-- Daily agent economy rollup: income count and GCC wei totals per agent.
MODEL (
  name dev.mv_agent_economy_daily,
  kind FULL,
  dialect postgres,
  description 'Per-agent daily income aggregates (gross_income, public_fund, parent_royalty in GCC wei).',
  grain [agent_did, economy_date],
  tags [agent, economy, daily, income, gcc]
);

SELECT
  agent_did,
  DATE_TRUNC('day', occurred_at) AS economy_date,
  COUNT(*) AS income_count,
  SUM(CAST(amount_gcc_wei AS DOUBLE PRECISION)) AS gross_income_wei,
  SUM(CAST(public_fund_wei AS DOUBLE PRECISION)) AS public_fund_wei,
  SUM(CAST(parent_royalty_wei AS DOUBLE PRECISION)) AS parent_royalty_wei
FROM vertex_agent_income_event
GROUP BY agent_did, DATE_TRUNC('day', occurred_at)
