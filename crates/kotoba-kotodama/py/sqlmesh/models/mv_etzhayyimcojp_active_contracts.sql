-- Etzhayyimcojp active contracts: active contracts with clause counts.
MODEL (
  name dev.mv_etzhayyimcojp_active_contracts,
  kind FULL,
  dialect postgres,
  description 'Per active contract: parties, dates, monthly rate, and distinct clause kind count.',
  grain [contract_id],
  tags [etzhayyimcojp, contract, active]
);

SELECT
  c.contract_id,
  c.contract_kind,
  c.counterparty_did,
  c.principal_did,
  c.vendor_did,
  c.title,
  c.start_date,
  c.end_date,
  c.monthly_rate_jpy,
  c.status,
  COUNT(DISTINCT cc.clause_kind) AS clause_count
FROM vertex_etzhayyimcojp_contract c
LEFT JOIN vertex_etzhayyimcojp_contract_clause cc ON cc.contract_id = c.contract_id
WHERE c.status = 'active'
GROUP BY c.contract_id, c.contract_kind, c.counterparty_did,
         c.principal_did, c.vendor_did, c.title, c.start_date,
         c.end_date, c.monthly_rate_jpy, c.status
