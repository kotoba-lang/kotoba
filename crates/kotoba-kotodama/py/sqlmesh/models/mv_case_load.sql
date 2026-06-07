-- Business case load: active case details with open action count.
MODEL (
  name dev.mv_case_load,
  kind FULL,
  dialect postgres,
  description 'Per business case: metadata plus count of open/in-progress actions via edge_mitigates_risk.',
  grain [vertex_id],
  tags [strategy, case, legal, action, risk]
);

SELECT
  bc.vertex_id,
  bc.case_code,
  bc.display_name,
  bc.case_type,
  bc.status,
  bc.counterparty,
  bc.estimated_impact_jpy,
  bc.document_count,
  bc.last_activity_at,
  bc.responsible_did,
  COUNT(DISTINCT a.vertex_id) FILTER (WHERE a.status IN ('planned', 'in_progress')) AS open_actions
FROM vertex_business_case bc
LEFT JOIN edge_mitigates_risk mr ON mr.dst_vid IN (
  SELECT vertex_id FROM vertex_risk WHERE risk_code LIKE '%' || bc.case_code || '%'
)
LEFT JOIN vertex_action a ON a.vertex_id = mr.src_vid
GROUP BY bc.vertex_id, bc.case_code, bc.display_name, bc.case_type, bc.status,
         bc.counterparty, bc.estimated_impact_jpy, bc.document_count,
         bc.last_activity_at, bc.responsible_did
