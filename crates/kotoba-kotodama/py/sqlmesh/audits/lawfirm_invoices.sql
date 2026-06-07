-- SQLMesh audit: mv_lawfirm_outstanding_invoices invariants.
-- Returns rows that FAIL the audit condition (zero rows = audit passes).

AUDIT (
  name assert_lawfirm_invoice_total_positive,
  model dev.mv_lawfirm_outstanding_invoices,
  dialect postgres,
  description 'total_minor must be > 0 (open invoices have a positive amount).'
);
SELECT *
FROM dev.mv_lawfirm_outstanding_invoices
WHERE total_minor <= 0;

---

AUDIT (
  name assert_lawfirm_invoice_id_present,
  model dev.mv_lawfirm_outstanding_invoices,
  dialect postgres,
  description 'stripe_invoice_id must be NOT NULL (PK from Stripe).'
);
SELECT *
FROM dev.mv_lawfirm_outstanding_invoices
WHERE stripe_invoice_id IS NULL;
