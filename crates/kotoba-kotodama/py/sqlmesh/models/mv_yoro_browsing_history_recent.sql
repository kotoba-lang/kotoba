-- Yoro browsing history recent: all browsing history ordered by recency.
MODEL (
  name dev.mv_yoro_browsing_history_recent,
  kind FULL,
  dialect postgres,
  description 'Browsing history rows with repo, path, title, type, avatar, handle, created_at, rkey.',
  grain [rkey],
  tags [yoro, browsing, history, recent]
);

SELECT
  repo,
  path,
  title,
  history_type,
  avatar,
  handle,
  created_at,
  rkey
FROM vertex_yoro_browsing_history
ORDER BY created_at DESC
