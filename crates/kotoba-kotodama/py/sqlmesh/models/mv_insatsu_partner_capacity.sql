-- Insatsu partner capacity: latest profile version aggregates per print partner.
MODEL (
  name dev.mv_insatsu_partner_capacity,
  kind FULL,
  dialect postgres,
  description 'Per partner_did: latest display name, capacity, cost metrics across profile versions.',
  grain [partner_did],
  tags [insatsu, partner, capacity, print]
);

SELECT
  partner_did,
  MAX(slug) AS slug,
  MAX(display_name) AS display_name,
  MAX(country) AS country,
  MAX(region) AS region,
  MAX(downstream_actor_did) AS downstream_actor_did,
  MAX(daily_capacity_pages) AS daily_capacity_pages,
  MIN(base_cost_usd) AS base_cost_usd,
  MIN(per_page_usd) AS per_page_usd,
  COUNT(*) AS profile_versions
FROM vertex_insatsu_print_partner
GROUP BY partner_did
