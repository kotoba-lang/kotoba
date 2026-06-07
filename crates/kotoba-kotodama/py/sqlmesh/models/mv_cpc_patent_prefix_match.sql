-- CPC patent prefix match: joins CPC product prefixes against patent IPC/CPC codes.
MODEL (
  name dev.mv_cpc_patent_prefix_match,
  kind FULL,
  dialect postgres,
  description 'Distinct CPC-to-patent matches via prefix join (IPC and CPC code systems) from view_cpc_product_live and vertex_patent.',
  grain [cpc_code, patent_vertex_id, code_system, class_prefix, patent_class_code],
  tags [cpc, patent, ipc, prefix_match, tsukuru]
);

WITH cpc_prefixes AS (
  SELECT
    code AS cpc_code,
    name AS cpc_name,
    subclass_code,
    tsukuru_process,
    patent_hint_csv,
    'ipc'::VARCHAR AS code_system,
    jsonb_array_elements_text(patent_ipc_prefixes::jsonb) AS class_prefix
  FROM view_cpc_product_live
  WHERE level = 'subclass'
    AND patent_ipc_prefixes <> '[]'
  UNION ALL
  SELECT
    code AS cpc_code,
    name AS cpc_name,
    subclass_code,
    tsukuru_process,
    patent_hint_csv,
    'cpc'::VARCHAR AS code_system,
    jsonb_array_elements_text(patent_cpc_prefixes::jsonb) AS class_prefix
  FROM view_cpc_product_live
  WHERE level = 'subclass'
    AND patent_cpc_prefixes <> '[]'
),
patent_codes AS (
  SELECT
    vertex_id AS patent_vertex_id,
    jurisdiction,
    app_number,
    pub_number,
    grant_number,
    title,
    filed_at,
    published_at,
    granted_at,
    'ipc'::VARCHAR AS code_system,
    jsonb_array_elements_text(ipc_codes::jsonb) AS patent_class_code
  FROM vertex_patent
  WHERE ipc_codes IS NOT NULL AND ipc_codes <> ''
  UNION ALL
  SELECT
    vertex_id AS patent_vertex_id,
    jurisdiction,
    app_number,
    pub_number,
    grant_number,
    title,
    filed_at,
    published_at,
    granted_at,
    'cpc'::VARCHAR AS code_system,
    jsonb_array_elements_text(cpc_codes::jsonb) AS patent_class_code
  FROM vertex_patent
  WHERE cpc_codes IS NOT NULL AND cpc_codes <> ''
)
SELECT DISTINCT
  c.cpc_code,
  c.cpc_name,
  c.subclass_code,
  c.tsukuru_process,
  c.patent_hint_csv,
  c.code_system,
  c.class_prefix,
  p.patent_vertex_id,
  p.jurisdiction,
  p.app_number,
  p.pub_number,
  p.grant_number,
  p.title,
  p.patent_class_code,
  p.filed_at,
  p.published_at,
  p.granted_at
FROM cpc_prefixes c
JOIN patent_codes p
  ON p.code_system = c.code_system
 AND p.patent_class_code LIKE c.class_prefix || '%'
