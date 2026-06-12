-- Lawfirm outstanding invoices: open Stripe invoices.
MODEL (
  name dev.mv_lawfirm_outstanding_invoices,
  kind FULL,
  dialect postgres,
  description 'Per Stripe invoice (status=open): matter, client, currency, amount, due date, hosted URL.',
  grain [stripe_invoice_id],
  tags [lawfirm, invoice, outstanding]
);

SELECT
  stripe_invoice_id,
  matter_uri,
  client_did,
  currency,
  total_minor,
  due_date,
  issued_at,
  hosted_invoice_url
FROM vertex_lawfirm_invoice
WHERE status = 'open'
