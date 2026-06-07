-- Chat artifact count and total bytes per owner and kind.
MODEL (
  name dev.mv_chat_artifact_size_per_owner,
  kind FULL,
  dialect postgres,
  description 'Per owner_did and kind: active artifact count and total byte size from vertex_chat_artifact.',
  grain [owner_did, kind],
  tags [chat, artifact, size, owner, storage]
);

SELECT
  owner_did,
  kind,
  COUNT(*) AS artifact_count,
  SUM(byte_size) AS total_bytes
FROM vertex_chat_artifact
WHERE status = 'active'
GROUP BY owner_did, kind
