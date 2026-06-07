-- JP fiscal contract payment UBO: contract + payment + beneficial owner join.
MODEL (
  name dev.mv_jp_fiscal_contract_payment_ubo,
  kind FULL,
  dialect postgres,
  description 'Per contract: payment amount, fiscal year, beneficial owner, and source URL.',
  grain [contract_vertex_id, payment_vertex_id, beneficial_owner_did],
  tags [jp_fiscal, contract, payment, ubo]
);

SELECT
  c.vertex_id AS contract_vertex_id,
  c.contract_no,
  c.issuer_did,
  c.contractor_did,
  c.contractor_jcn,
  c.amount_jpy AS contract_amount_jpy,
  p.vertex_id AS payment_vertex_id,
  p.paid_jpy,
  p.fiscal_year,
  u.parent_did AS beneficial_owner_did,
  u.parent_type AS beneficial_owner_type,
  u.ownership_pct,
  u.status AS ubo_status,
  c.publication_url,
  COALESCE(p.source_url, c.publication_url) AS source_url
FROM vertex_jp_fiscal_contract c
LEFT JOIN vertex_jp_fiscal_payment_record p ON p.contract_did = c.vertex_id
LEFT JOIN vertex_jp_fiscal_beneficial_owner u ON u.child_did = c.contractor_did
