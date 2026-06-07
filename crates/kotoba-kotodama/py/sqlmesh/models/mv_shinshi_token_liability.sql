-- Shinshi token liability: total outstanding balance and spent across all ledgers.
MODEL (
  name dev.mv_shinshi_token_liability,
  kind FULL,
  dialect postgres,
  description 'Aggregate: ledger count, outstanding token balance, total tokens spent.',
  grain [],
  tags [shinshi, token, ledger, liability]
);

SELECT
  COUNT(*) AS ledger_count,
  SUM(balance) AS outstanding_balance,
  SUM(spent) AS total_spent
FROM vertex_shinshi_token_ledger
