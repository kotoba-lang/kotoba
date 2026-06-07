-- World vertex count per app_host — drives mv_world_coverage_live vertex branch.
MODEL (
  name dev.mv_world_vertex_per_host,
  kind FULL,
  dialect postgres,
  description 'Vertex row count aggregated per app_host from all domain vertex tables.',
  grain [app_host],
  tags [coverage, world, vertex]
);

SELECT app_host, SUM(cnt) AS vertex_count
FROM (
  SELECT 'maps'                AS app_host, COUNT(*) AS cnt FROM vertex_spatial
  UNION ALL SELECT 'maps',                  COUNT(*)          FROM vertex_transport
  UNION ALL SELECT 'gov',                   COUNT(*)          FROM vertex_gov_org
  UNION ALL SELECT 'gov',                   COUNT(*)          FROM vertex_gov_municipality
  UNION ALL SELECT 'dns',                   COUNT(*)          FROM vertex_dns_observation
  UNION ALL SELECT 'dns',                   COUNT(*)          FROM vertex_domain
  UNION ALL SELECT 'blockchain',            COUNT(*)          FROM vertex_blockchain_actor
  UNION ALL SELECT 'gtin',                  COUNT(*)          FROM vertex_gtin_product
  UNION ALL SELECT 'media-gamers',          COUNT(*)          FROM vertex_game_actor
  UNION ALL SELECT 'media-gamers',          COUNT(*)          FROM vertex_game_item
  UNION ALL SELECT 'media-gamers',          COUNT(*)          FROM vertex_game_title
  UNION ALL SELECT 'bank',                  COUNT(*)          FROM vertex_finance
  UNION ALL SELECT 'patent',                COUNT(*)          FROM vertex_patent
  UNION ALL SELECT 'chizai',                COUNT(*)          FROM vertex_trademark
  UNION ALL SELECT 'chizai',                COUNT(*)          FROM vertex_work
  UNION ALL SELECT 'hospitality',           COUNT(*)          FROM vertex_accommodation
  UNION ALL SELECT 'talent',                COUNT(*)          FROM vertex_talent_cohort
  UNION ALL SELECT 'talent',                COUNT(*)          FROM vertex_skill
  UNION ALL SELECT 'talent',                COUNT(*)          FROM vertex_occupation
  UNION ALL SELECT 'talent',                COUNT(*)          FROM vertex_occupation_wikidata
  UNION ALL SELECT 'talent',                COUNT(*)          FROM vertex_occupation_bls
  UNION ALL SELECT 'talent',                COUNT(*)          FROM vertex_job_posting
  UNION ALL SELECT 'sanctions',             COUNT(*)          FROM vertex_open_ofac_sanctions_sdn
  UNION ALL SELECT 'crypto-asset-freeze',   COUNT(*)          FROM vertex_crypto_asset_freeze_incident
  UNION ALL SELECT 'bengoshi',              COUNT(*)          FROM vertex_adr_case
  UNION ALL SELECT 'bengoshi',              COUNT(*)          FROM vertex_adr_arbitrator
  UNION ALL SELECT 'bengoshi',              COUNT(*)          FROM vertex_lawyer
  UNION ALL SELECT 'npo',                   COUNT(*)          FROM vertex_legal_aid_case
  UNION ALL SELECT 'npo',                   COUNT(*)          FROM vertex_legal_aid_office
  UNION ALL SELECT 'natural-person',        COUNT(*)          FROM vertex_natural_person
  UNION ALL SELECT 'ipaddress',             COUNT(*)          FROM vertex_ip_address
  UNION ALL SELECT 'keiyaku',               COUNT(*)          FROM vertex_keiyaku_contract_canonical
  UNION ALL SELECT 'keiyaku',               COUNT(*)          FROM vertex_keiyaku_contract_observation
  UNION ALL SELECT 'kyber',                 COUNT(*)          FROM vertex_office_document
  UNION ALL SELECT 'judge',                 COUNT(*)          FROM vertex_judge
  UNION ALL SELECT 'public-fund',           COUNT(*)          FROM vertex_fund WHERE fund_kind IN ('government', 'sovereign')
  UNION ALL SELECT 'securities',            COUNT(*)          FROM vertex_fund WHERE fund_kind IN ('investor', 'mutual', 'pension', 'private')
  UNION ALL SELECT 'mine',                  COUNT(*)          FROM vertex_rare_earth_coverage
  UNION ALL SELECT 'oil-coverage',          COUNT(*)          FROM vertex_oil_company
  UNION ALL SELECT 'oil-coverage',          COUNT(*)          FROM vertex_oil_field
  UNION ALL SELECT 'oil-coverage',          COUNT(*)          FROM vertex_oil_basin
  UNION ALL SELECT 'oil-coverage',          COUNT(*)          FROM vertex_oil_pipeline
  UNION ALL SELECT 'oil-coverage',          COUNT(*)          FROM vertex_oil_terminal
  UNION ALL SELECT 'oil-coverage',          COUNT(*)          FROM vertex_crude_grade
  UNION ALL SELECT 'oil-coverage',          COUNT(*)          FROM vertex_pricing_benchmark
  UNION ALL SELECT 'oil-coverage',          COUNT(*)          FROM vertex_oil_trade
  UNION ALL SELECT 'oil-coverage',          COUNT(*)          FROM vertex_oil_cargo
  UNION ALL SELECT 'oil-coverage',          COUNT(*)          FROM vertex_oil_tanker
  UNION ALL SELECT 'webpage',               cnt               FROM mv_vertex_page_count
) AS sub
GROUP BY app_host
