-- ADR-0031 Phase C: B/S delta per owner × period × account_type.
-- Asset: +debit -credit. Liability/equity: +credit -debit.
MODEL (
  name dev.mv_kaikei_bs_delta,
  kind FULL,
  dialect postgres,
  description 'B/S delta per owner_did × period_ym × account_type (asset/liability/equity).',
  grain [owner_did, period_ym, account_type],
  tags [kaikei, accounting, bs, adr_0031]
);

SELECT
  owner_did,
  period_ym,
  account_type,
  SUM(net_amount) AS delta,
  COUNT(*)        AS entry_count,
  MAX(_seq)       AS _seq
FROM (
  -- asset: debit increases balance
  SELECT
    j.owner_did,
    j.period_ym,
    a.account_type,
    j.debit_amount  AS net_amount,
    j._seq
  FROM vertex_atrecord_kaikei_journal_entry j
  JOIN vertex_atrecord_kaikei_account a
    ON a.owner_did = j.owner_did
   AND a.vertex_id = j.owner_did || '|com.etzhayyim.apps.kaikei.account|'
                   || SPLIT_PART(j.debit_account_did, ':', 5)
  WHERE a.account_type IN ('asset','liability','equity')
  UNION ALL
  -- asset: credit decreases balance
  SELECT
    j.owner_did,
    j.period_ym,
    a.account_type,
    -j.credit_amount AS net_amount,
    j._seq
  FROM vertex_atrecord_kaikei_journal_entry j
  JOIN vertex_atrecord_kaikei_account a
    ON a.owner_did = j.owner_did
   AND a.vertex_id = j.owner_did || '|com.etzhayyim.apps.kaikei.account|'
                   || SPLIT_PART(j.credit_account_did, ':', 5)
  WHERE a.account_type = 'asset'
  UNION ALL
  -- liability/equity: credit increases balance
  SELECT
    j.owner_did,
    j.period_ym,
    a.account_type,
    j.credit_amount AS net_amount,
    j._seq
  FROM vertex_atrecord_kaikei_journal_entry j
  JOIN vertex_atrecord_kaikei_account a
    ON a.owner_did = j.owner_did
   AND a.vertex_id = j.owner_did || '|com.etzhayyim.apps.kaikei.account|'
                   || SPLIT_PART(j.credit_account_did, ':', 5)
  WHERE a.account_type IN ('liability','equity')
  UNION ALL
  -- liability/equity: debit decreases balance
  SELECT
    j.owner_did,
    j.period_ym,
    a.account_type,
    -j.debit_amount AS net_amount,
    j._seq
  FROM vertex_atrecord_kaikei_journal_entry j
  JOIN vertex_atrecord_kaikei_account a
    ON a.owner_did = j.owner_did
   AND a.vertex_id = j.owner_did || '|com.etzhayyim.apps.kaikei.account|'
                   || SPLIT_PART(j.debit_account_did, ':', 5)
  WHERE a.account_type IN ('liability','equity')
) x
GROUP BY owner_did, period_ym, account_type
