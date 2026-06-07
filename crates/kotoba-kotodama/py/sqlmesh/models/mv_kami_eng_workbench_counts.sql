-- Kami eng workbench counts: record counts per workbench kind and status across 6 engineering tables.
MODEL (
  name dev.mv_kami_eng_workbench_counts,
  kind FULL,
  dialect postgres,
  description 'Per (workbench_kind, status): record count across EDA/CAD/CAM/RTL/CAE workbenches.',
  grain [workbench_kind, status],
  tags [kami, engineering, workbench, counts]
);

SELECT 'eda_schematic' AS workbench_kind, status, COUNT(*)::BIGINT AS record_count FROM vertex_kami_eng_eda_schematic GROUP BY status
UNION ALL
SELECT 'cad_model', status, COUNT(*)::BIGINT FROM vertex_kami_eng_cad_model GROUP BY status
UNION ALL
SELECT 'cad_feature', status, COUNT(*)::BIGINT FROM vertex_kami_eng_cad_feature GROUP BY status
UNION ALL
SELECT 'cam_job', status, COUNT(*)::BIGINT FROM vertex_kami_eng_cam_job GROUP BY status
UNION ALL
SELECT 'rtl_simulation', status, COUNT(*)::BIGINT FROM vertex_kami_eng_rtl_simulation GROUP BY status
UNION ALL
SELECT 'cae_analysis', status, COUNT(*)::BIGINT FROM vertex_kami_eng_cae_analysis GROUP BY status
