-- Etzhayyim op log head: latest op sequence number per DID.
MODEL (
  name dev.mv_etzhayyim_op_log_head,
  kind FULL,
  dialect postgres,
  description 'Per DID: maximum op_seq (head of the op log).',
  grain [did],
  tags [etzhayyim, did, op_log, identity]
);

SELECT
  did,
  MAX(op_seq) AS head_seq
FROM vertex_etzhayyim_op_log
GROUP BY did
