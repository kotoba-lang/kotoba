-- Intel building owner LEI: dependency edges for building ownership with LEI.
MODEL (
  name dev.mv_intel_building_owner_lei,
  kind FULL,
  dialect postgres,
  description 'Building ownership edges (owned_by/constructed_by/operated_by) joined with owner LEI and label.',
  grain [edge_id],
  tags [intel, building, owner, lei]
);

SELECT
  d.edge_id,
  d.src_vid AS building_vid,
  d.dst_vid AS owner_vid,
  s.lei,
  s.label AS owner_label,
  d.confidence,
  d.status
FROM edge_intel_dependency d
LEFT JOIN vertex_intel_subject s ON s.vertex_id = d.dst_vid
WHERE d.predicate IN ('owned_by', 'constructed_by', 'operated_by')
