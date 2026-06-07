-- Site WET chunk total: aggregate WET chunk count.
MODEL (
  name dev.mv_site_wet_chunk_total,
  kind FULL,
  dialect postgres,
  description 'Total WET chunk count from vertex_wet_chunk.',
  grain [],
  tags [site, wet_chunk, total]
);

SELECT COUNT(*)::BIGINT AS cnt
FROM vertex_wet_chunk
