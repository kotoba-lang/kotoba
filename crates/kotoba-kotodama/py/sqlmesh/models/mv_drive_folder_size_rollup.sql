-- Drive folder size rollup: file count and total bytes per folder.
MODEL (
  name dev.mv_drive_folder_size_rollup,
  kind FULL,
  dialect postgres,
  description 'Per folder_id: file count, total size in bytes, and last seq from vertex_drive_file.',
  grain [folder_id],
  tags [drive, folder, size, files, rollup]
);

SELECT
  COALESCE(folder_id, '') AS folder_id,
  COUNT(*) AS file_count,
  COALESCE(SUM(size_bytes), 0) AS total_size_bytes,
  MAX(_seq) AS last_seq
FROM vertex_drive_file
GROUP BY COALESCE(folder_id, '')
