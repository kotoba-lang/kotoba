-- OS window state: per-window latest event timestamp.
MODEL (
  name dev.mv_os_window_state,
  kind FULL,
  dialect postgres,
  description 'Per window_id: MAX(created_at) from vertex_os_window_event.',
  grain [window_id],
  tags [os, window, state]
);

SELECT
  window_id,
  MAX(created_at) AS updated_at
FROM vertex_os_window_event
GROUP BY window_id
