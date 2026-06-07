-- Open banking balance: running balance per account and currency.
MODEL (
  name dev.mv_open_banking_balance,
  kind FULL,
  dialect postgres,
  description 'Per (account_vid, currency): net balance (credits minus debits), entry count, last executed.',
  grain [account_vid, currency],
  tags [open_banking, balance, ledger, finance]
);

SELECT
  account_vid,
  currency,
  SUM(CASE WHEN direction = 'credit' THEN amount ELSE 0 END) - SUM(CASE WHEN direction = 'debit' THEN amount ELSE 0 END) AS balance,
  COUNT(*) AS entry_count,
  MAX(executed_at) AS last_executed_at
FROM vertex_open_banking_ledger_entry
GROUP BY account_vid, currency
