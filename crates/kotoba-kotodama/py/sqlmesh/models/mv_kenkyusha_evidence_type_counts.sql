-- Kenkyusha evidence type counts: evidence counts per frontier, hypothesis, and source/evidence type.
MODEL (
  name dev.mv_kenkyusha_evidence_type_counts,
  kind FULL,
  dialect postgres,
  description 'Per (frontier_id, hypothesis_id, source_type, evidence_type): evidence count.',
  grain [frontier_id, hypothesis_id, source_type, evidence_type],
  tags [kenkyusha, evidence, counts]
);

SELECT
  frontier_id,
  hypothesis_id,
  source_type,
  evidence_type,
  COUNT(*)::BIGINT AS evidence_count
FROM vertex_kenkyusha_evidence
GROUP BY frontier_id, hypothesis_id, source_type, evidence_type
