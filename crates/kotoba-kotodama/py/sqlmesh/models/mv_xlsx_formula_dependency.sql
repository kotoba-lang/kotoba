-- XLSX formula dependency: formula cell count and reference counts per sheet.
MODEL (
  name dev.mv_xlsx_formula_dependency,
  kind FULL,
  dialect postgres,
  description 'Per (workbook_id, sheet_name, cell_ref): formula and reference metadata for formula cells.',
  grain [workbook_id, sheet_name, cell_ref],
  tags [xlsx, formula, dependency]
);

SELECT
  workbook_id,
  sheet_name,
  cell_ref,
  formula,
  COUNT(*) AS occurrence_count
FROM vertex_xlsx_cell
WHERE formula IS NOT NULL
GROUP BY workbook_id, sheet_name, cell_ref, formula
