-- SQLMesh audit: mv_jpn_invoice_tax_by_tier invariants.
-- Returns rows that FAIL the audit condition (zero rows = audit passes).

AUDIT (
  name assert_jpn_invoice_tax_amount_nonnegative,
  model dev.mv_jpn_invoice_tax_by_tier,
  dialect postgres,
  description 'total_tax_payable must be >= 0 (corporate tax is non-negative).'
);
SELECT *
FROM dev.mv_jpn_invoice_tax_by_tier
WHERE total_tax_payable < 0;

---

AUDIT (
  name assert_jpn_invoice_filing_count_positive,
  model dev.mv_jpn_invoice_tax_by_tier,
  dialect postgres,
  description 'filing_count must be > 0 (group rows imply at least one accepted filing).'
);
SELECT *
FROM dev.mv_jpn_invoice_tax_by_tier
WHERE filing_count <= 0;
