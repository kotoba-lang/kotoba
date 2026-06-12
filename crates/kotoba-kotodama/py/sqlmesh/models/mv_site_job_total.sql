-- Site job total: aggregate collection job count.
MODEL (
  name dev.mv_site_job_total,
  kind FULL,
  dialect postgres,
  description 'Total collection job count from vertex_collection_job.',
  grain [],
  tags [site, job, total]
);

SELECT COUNT(*)::BIGINT AS cnt
FROM vertex_collection_job
