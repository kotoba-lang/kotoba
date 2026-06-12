-- SQLMesh audit: mv_lawfirm_revenue_monthly invariants.
-- Returns rows that FAIL the audit condition (zero rows = audit passes).

AUDIT (
  name assert_lawfirm_revenue_amount_nonnegative,
  model dev.mv_lawfirm_revenue_monthly,
  dialect postgres,
  description 'amount_minor_total must be >= 0 (paid amounts are non-negative).'
);
SELECT *
FROM dev.mv_lawfirm_revenue_monthly
WHERE amount_minor_total < 0;

---

AUDIT (
  name assert_lawfirm_revenue_payment_count_positive,
  model dev.mv_lawfirm_revenue_monthly,
  dialect postgres,
  description 'payment_count must be > 0 (group rows imply at least one payment).'
);
SELECT *
FROM dev.mv_lawfirm_revenue_monthly
WHERE payment_count <= 0;
