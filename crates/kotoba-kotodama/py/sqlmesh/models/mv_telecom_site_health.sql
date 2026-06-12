-- Telecom site health: per-cell-site RAN node, incident, and maintenance counts.
MODEL (
  name dev.mv_telecom_site_health,
  kind FULL,
  dialect postgres,
  description 'Per (site_vid, site_id, jurisdiction): RAN node count, open incidents, planned/in-progress maintenance.',
  grain [site_vid],
  tags [telecom, site, health]
);

SELECT
  s.vertex_id AS site_vid,
  s.site_id,
  s.jurisdiction,
  COUNT(DISTINCT r.vertex_id) AS ran_node_count,
  COUNT(DISTINCT i.vertex_id) FILTER (WHERE i.status = 'open') AS open_incidents,
  COUNT(DISTINCT m.vertex_id) FILTER (WHERE m.status IN ('planned', 'in_progress')) AS open_maintenance
FROM vertex_telecom_cell_site s
LEFT JOIN vertex_telecom_ran_node r ON r.site_vid = s.vertex_id
LEFT JOIN vertex_telecom_site_incident i ON i.site_vid = s.vertex_id
LEFT JOIN vertex_telecom_maintenance_window m ON m.site_vid = s.vertex_id
GROUP BY s.vertex_id, s.site_id, s.jurisdiction
