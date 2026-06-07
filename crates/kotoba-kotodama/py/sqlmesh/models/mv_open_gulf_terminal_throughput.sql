-- Open Gulf terminal throughput: completed loading aggregates per terminal and crude grade.
MODEL (
  name dev.mv_open_gulf_terminal_throughput,
  kind FULL,
  dialect postgres,
  description 'Per (terminal_code, crude_grade): completed loading count, total tonnes, and latest BL date.',
  grain [terminal_code, crude_grade],
  tags [open_gulf, terminal, throughput, loading]
);

SELECT
  terminal_code,
  crude_grade,
  COUNT(*) AS loading_count,
  SUM(volume_tonnes) AS total_tonnes,
  MAX(bl_date) AS latest_bl
FROM vertex_open_gulf_terminal_loading
WHERE status = 'completed'
GROUP BY terminal_code, crude_grade
