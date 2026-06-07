-- Intel inference chain flow: cohort and evidence counts per inference chain.
MODEL (
  name dev.mv_intel_inference_chain_flow,
  kind FULL,
  dialect postgres,
  description 'Per chain: subject, industry, status, cohort count, avg confidence, evidence count.',
  grain [chain_id],
  tags [intel, inference, chain, flow]
);

SELECT
  c.chain_id,
  c.subject_did,
  c.subject_name,
  c.industry,
  c.status,
  COUNT(DISTINCT h.vertex_id) AS cohort_count,
  AVG(h.confidence) AS avg_confidence,
  COUNT(DISTINCT e.dst_vid) AS evidence_count,
  MAX(COALESCE(h.created_at, c.created_at)) AS latest_at
FROM vertex_intel_inference_chain c
LEFT JOIN vertex_intel_inferred_cohort h ON h.chain_id = c.chain_id
LEFT JOIN edge_intel_chain_evidence e ON e.src_vid = c.vertex_id
GROUP BY c.chain_id, c.subject_did, c.subject_name, c.industry, c.status
