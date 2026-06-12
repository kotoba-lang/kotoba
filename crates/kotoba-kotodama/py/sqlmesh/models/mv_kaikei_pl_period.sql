-- ADR-0031 Phase C: P/L flow per owner × period × account_type.
-- Expense side = debit_amount; revenue side = credit_amount.
MODEL (
  name dev.mv_kaikei_pl_period,
  kind FULL,
  dialect postgres,
  description 'P/L flow per owner_did × period_ym × account_type (expense=debit, revenue=credit).',
  grain [owner_did, period_ym, account_type],
  tags [kaikei, accounting, pl, adr_0031]
);

SELECT
  owner_did,
  period_ym,
  account_type,
  SUM(amount)  AS total,
  COUNT(*)     AS entry_count,
  MAX(_seq)    AS _seq
FROM (
  SELECT
    j.owner_did,
    j.period_ym,
    a.account_type,
    j.debit_amount  AS amount,
    j._seq
  FROM vertex_atrecord_kaikei_journal_entry j
  JOIN vertex_atrecord_kaikei_account a
    ON a.owner_did = j.owner_did
   AND a.vertex_id = j.owner_did || '|com.etzhayyim.apps.kaikei.account|'
                   || SPLIT_PART(j.debit_account_did, ':', 5)
  WHERE a.account_type = 'expense'
  UNION ALL
  SELECT
    j.owner_did,
    j.period_ym,
    a.account_type,
    j.credit_amount AS amount,
    j._seq
  FROM vertex_atrecord_kaikei_journal_entry j
  JOIN vertex_atrecord_kaikei_account a
    ON a.owner_did = j.owner_did
   AND a.vertex_id = j.owner_did || '|com.etzhayyim.apps.kaikei.account|'
                   || SPLIT_PART(j.credit_account_did, ':', 5)
  WHERE a.account_type = 'revenue'
) x
GROUP BY owner_did, period_ym, account_type
