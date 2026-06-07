-- ADR-0031 kaikei trial balance: debit+credit per owner×period×account.
MODEL (
  name dev.mv_kaikei_trial_balance,
  kind FULL,
  dialect postgres,
  description 'Trial balance: total debit/credit per owner_did × period_ym × account_did.',
  grain [owner_did, period_ym, account_did, side],
  tags [kaikei, accounting, trial_balance, adr_0031]
);

SELECT
  owner_did,
  period_ym,
  debit_account_did AS account_did,
  'debit'           AS side,
  SUM(amount)       AS total_amount,
  COUNT(*)          AS entry_count,
  MAX(_seq)         AS _seq
FROM vertex_atrecord_kaikei_journal_entry
GROUP BY owner_did, period_ym, debit_account_did
UNION ALL
SELECT
  owner_did,
  period_ym,
  credit_account_did,
  'credit',
  SUM(amount),
  COUNT(*),
  MAX(_seq)
FROM vertex_atrecord_kaikei_journal_entry
GROUP BY owner_did, period_ym, credit_account_did
