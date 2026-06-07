-- Entity health: composite health score per entity joining financial, risk, and strategy data.
MODEL (
  name dev.mv_entity_health,
  kind FULL,
  dialect postgres,
  description 'Per entity: document count, revenue, cost, business case score, risk level, and attainment bps.',
  grain [entity_id],
  tags [entity, health, strategy, risk, finance]
);

SELECT
  e.vertex_id AS entity_id,
  e.name,
  e.entity_type,
  (SELECT COUNT(*) FROM vertex_docs_report dr WHERE dr.entity_id = e.vertex_id) AS document_count,
  rs.amount AS revenue,
  cc.amount AS cost,
  bc.score AS business_case_score,
  r.risk_level,
  g.attainment_bps
FROM vertex_entity e
LEFT JOIN vertex_revenue_stream rs ON rs.entity_id = e.vertex_id
LEFT JOIN vertex_cost_center cc ON cc.entity_id = e.vertex_id
LEFT JOIN vertex_business_case bc ON bc.entity_id = e.vertex_id
LEFT JOIN vertex_risk r ON r.entity_id = e.vertex_id
LEFT JOIN vertex_goal g ON g.entity_id = e.vertex_id
