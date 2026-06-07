-- Telecom spectrum utilization: per-license RAN node binding count for active licenses.
MODEL (
  name dev.mv_telecom_spectrum_utilization,
  kind FULL,
  dialect postgres,
  description 'Per active spectrum license: RAN node count via spectrum_license_vid linkage.',
  grain [license_vid],
  tags [telecom, spectrum, license, utilization]
);

SELECT
  l.vertex_id AS license_vid,
  l.license_id,
  l.band,
  l.jurisdiction,
  COUNT(DISTINCT r.vertex_id) AS bound_node_count
FROM vertex_telecom_spectrum_license l
LEFT JOIN vertex_telecom_ran_node r ON r.spectrum_license_vid = l.vertex_id
WHERE l.status = 'active'
GROUP BY l.vertex_id, l.license_id, l.band, l.jurisdiction
