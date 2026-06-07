-- OS consent pending: pending consent requests with no response.
MODEL (
  name dev.mv_os_consent_pending,
  kind FULL,
  dialect postgres,
  description 'Pending consent requests where no response row exists in vertex_os_consent_response.',
  grain [request_id],
  tags [os, consent, pending]
);

SELECT r.*
FROM vertex_os_consent_request r
LEFT JOIN vertex_os_consent_response s ON r.request_id = s.request_id
WHERE r.status = 'pending' AND s.request_id IS NULL
