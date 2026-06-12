-- Insatsu print mail job status: job counts and cost totals per status, country, partner.
MODEL (
  name dev.mv_insatsu_print_mail_job_status,
  kind FULL,
  dialect postgres,
  description 'Per (status, destination_country, partner_did): job count, total pages, and estimated cost.',
  grain [status, destination_country, partner_did],
  tags [insatsu, job, status, print]
);

SELECT
  status,
  destination_country,
  partner_did,
  COUNT(*) AS job_count,
  SUM(page_count * quantity) AS total_pages,
  SUM(estimated_cost_usd) AS estimated_cost_usd,
  MAX(created_at) AS latest_created_at
FROM vertex_insatsu_print_mail_job
GROUP BY status, destination_country, partner_did
