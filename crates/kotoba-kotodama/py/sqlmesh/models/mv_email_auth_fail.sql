-- Email auth fail: messages with SPF/DKIM/DMARC failures (BEC screening).
MODEL (
  name dev.mv_email_auth_fail,
  kind FULL,
  dialect postgres,
  description 'Email messages where SPF, DKIM, or DMARC result is fail or softfail — BEC risk screening.',
  grain [vertex_id],
  tags [email, bec, auth, spf, dkim, dmarc, security]
);

SELECT
  account_did,
  from_address,
  from_domain,
  received_at,
  spf_result,
  dkim_result,
  dmarc_result,
  subject_hash
FROM vertex_email_message
WHERE
  spf_result = 'fail' OR dkim_result = 'fail' OR dmarc_result = 'fail' OR
  spf_result = 'softfail' OR dmarc_result = 'softfail'
