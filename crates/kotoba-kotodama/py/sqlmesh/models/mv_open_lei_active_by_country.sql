-- Open LEI active by country: active entity count per country and registration status.
MODEL (
  name dev.mv_open_lei_active_by_country,
  kind FULL,
  dialect postgres,
  description 'Per (country, registration_status): active LEI entity count and latest issued timestamp.',
  grain [country, registration_status],
  tags [open_lei, entity, country, registration]
);

SELECT
  country,
  registration_status,
  COUNT(*) AS entity_count,
  MAX(issued_at) AS latest_issued_at
FROM vertex_open_lei_entity
WHERE status = 'active'
GROUP BY country, registration_status
