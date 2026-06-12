-- XLSX sheet metrics: cell, formula, and data counts per sheet.
MODEL (
  name dev.mv_xlsx_sheet_metrics,
  kind FULL,
  dialect postgres,
  description 'Per (workbook_id, sheet_name): total cells, formula count, and non-null data cells.',
  grain [workbook_id, sheet_name],
  tags [xlsx, sheet, metrics]
);

SELECT
  workbook_id,
  sheet_name,
  COUNT(*) AS total_cells,
  COUNT(CASE WHEN formula IS NOT NULL THEN 1 END) AS formula_count,
  COUNT(CASE WHEN value IS NOT NULL THEN 1 END) AS data_cells
FROM vertex_xlsx_cell
GROUP BY workbook_id, sheet_name
