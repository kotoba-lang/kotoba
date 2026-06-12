-- Email first contact senders: first/last seen and message count per sender per account.
MODEL (
  name dev.mv_email_first_contact_senders,
  kind FULL,
  dialect postgres,
  description 'Per (account_did, from_address, from_domain): first seen, last seen, and message count.',
  grain [account_did, from_address, from_domain],
  tags [email, bec, sender, first_contact, security]
);

SELECT
  account_did,
  from_address,
  from_domain,
  MIN(received_at) AS first_seen,
  MAX(received_at) AS last_seen,
  COUNT(*) AS msg_count
FROM vertex_email_message
WHERE account_did IS NOT NULL AND from_address IS NOT NULL
GROUP BY account_did, from_address, from_domain
