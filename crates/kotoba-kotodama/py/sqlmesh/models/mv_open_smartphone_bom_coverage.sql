-- Open smartphone BOM coverage: BOM lines aggregated by component type with open-source ratio.
MODEL (
  name dev.mv_open_smartphone_bom_coverage,
  kind FULL,
  dialect postgres,
  description 'Per BOM: total/open lines, per-type breakdown (soc/modem/sensor/os/ems/patent), and open_score_pct.',
  grain [bom_vid],
  tags [open_smartphone, bom, coverage]
);

SELECT
  b.vertex_id AS bom_vid,
  b.bom_id,
  b.design_name,
  COUNT(bl.vertex_id) AS total_lines,
  SUM(CASE WHEN bl.open_source THEN 1 ELSE 0 END) AS open_lines,
  SUM(CASE WHEN bl.component_type = 'soc' THEN 1 ELSE 0 END) AS soc_lines,
  SUM(CASE WHEN bl.component_type = 'modem' THEN 1 ELSE 0 END) AS modem_lines,
  SUM(CASE WHEN bl.component_type = 'sensor' THEN 1 ELSE 0 END) AS sensor_lines,
  SUM(CASE WHEN bl.component_type = 'os' THEN 1 ELSE 0 END) AS os_lines,
  SUM(CASE WHEN bl.component_type = 'ems' THEN 1 ELSE 0 END) AS ems_lines,
  SUM(CASE WHEN bl.component_type = 'patent' THEN 1 ELSE 0 END) AS patent_lines,
  CASE
    WHEN COUNT(bl.vertex_id) = 0 THEN 0.0
    ELSE (SUM(CASE WHEN bl.open_source THEN 1 ELSE 0 END)::DOUBLE PRECISION
          / COUNT(bl.vertex_id)::DOUBLE PRECISION * 100.0)
  END AS open_score_pct,
  b.open_score_pct AS llm_open_score_pct
FROM vertex_open_smartphone_bom b
LEFT JOIN vertex_open_smartphone_bom_line bl ON bl.bom_did = b.bom_id
GROUP BY b.vertex_id, b.bom_id, b.design_name, b.open_score_pct
