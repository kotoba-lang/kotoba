-- Cowork graph draft pending: mail drafts awaiting approval or send.
MODEL (
  name dev.mv_cowork_graph_draft_pending,
  kind FULL,
  dialect postgres,
  description 'Pending mail drafts: approved_at IS NULL AND sent_at IS NULL.',
  grain [draft_id],
  tags [cowork, mail, draft, pending, approval]
);

SELECT
  draft_id,
  user_id,
  subject,
  to_addrs,
  importance,
  web_link,
  created_at
FROM vertex_cowork_graph_mail_draft
WHERE approved_at IS NULL AND sent_at IS NULL
