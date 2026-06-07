-- SQLMesh audit: mv_telecom_roaming_settlement_balance invariants.
-- Returns rows that FAIL the audit condition (zero rows = audit passes).

AUDIT (
  name assert_telecom_roaming_net_consistent,
  model dev.mv_telecom_roaming_settlement_balance,
  dialect postgres,
  description 'net_balance must equal total_receivable - total_payable.'
);
SELECT *
FROM dev.mv_telecom_roaming_settlement_balance
WHERE ABS(net_balance - (total_receivable - total_payable)) > 0.01;

---

AUDIT (
  name assert_telecom_roaming_amounts_nonnegative,
  model dev.mv_telecom_roaming_settlement_balance,
  dialect postgres,
  description 'total_receivable and total_payable must be >= 0; invoice_count > 0.'
);
SELECT *
FROM dev.mv_telecom_roaming_settlement_balance
WHERE total_receivable < 0
   OR total_payable < 0
   OR invoice_count <= 0;
