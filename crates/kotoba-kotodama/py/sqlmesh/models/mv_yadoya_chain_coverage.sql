-- Yadoya chain coverage: published hotel counts per chain.
MODEL (
  name dev.mv_yadoya_chain_coverage,
  kind FULL,
  dialect postgres,
  description 'Per (chain_did, country, region): published hotel count.',
  grain [chain_did, country, region],
  tags [yadoya, chain, coverage]
);

SELECT
  COALESCE(chain_did, 'independent') AS chain_did,
  country,
  region,
  COUNT(*) AS hotel_count
FROM vertex_yadoya_hotel
WHERE status = 'published'
GROUP BY COALESCE(chain_did, 'independent'), country, region
