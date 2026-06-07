-- Open JPN MyNumber file transfer status: transfer + manifest join.
MODEL (
  name dev.mv_open_jpn_mynumber_file_transfer_status,
  kind FULL,
  dialect postgres,
  description 'Per file transfer: requester/holder agencies, manifest hash, file count, total bytes, status.',
  grain [transfer_id],
  tags [open_jpn, mynumber, file_transfer, status]
);

SELECT
  t.vertex_id AS transfer_id,
  t.requester_agency,
  t.holder_agency,
  t.purpose_code,
  t.file_manifest_hash,
  m.vertex_id AS file_manifest_vertex_id,
  t.file_count,
  m.total_bytes,
  t.status,
  t.created_at,
  t.updated_at
FROM vertex_open_jpn_mynumber_file_transfer t
LEFT JOIN vertex_open_jpn_mynumber_file_manifest m
  ON m.file_manifest_hash = t.file_manifest_hash
