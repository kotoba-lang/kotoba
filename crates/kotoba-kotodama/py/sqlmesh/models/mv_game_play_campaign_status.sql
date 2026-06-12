-- Game play campaign status: aggregate participant, upload, approval, and reward metrics.
MODEL (
  name dev.mv_game_play_campaign_status,
  kind FULL,
  dialect postgres,
  description 'Campaign-level counts: participants, uploads, approved duration, and total reward in JPY.',
  grain [],
  tags [game, play, campaign, reward]
);

SELECT
  COUNT(DISTINCT p.vertex_id)::BIGINT AS participant_count,
  COUNT(DISTINCT u.vertex_id)::BIGINT AS upload_count,
  COALESCE(SUM(CASE WHEN r.decision = 'approved' THEN u.duration_sec ELSE 0 END), 0)::BIGINT AS approved_duration_sec,
  COALESCE(SUM(rew.reward_jpy), 0)::BIGINT AS reward_jpy
FROM vertex_game_play_participant p
LEFT JOIN vertex_game_play_upload_session s ON s.participant_did = p.participant_did
LEFT JOIN vertex_game_play_upload u ON u.session_id = s.session_id
LEFT JOIN vertex_game_play_review r ON r.upload_id = u.upload_id
LEFT JOIN vertex_game_play_reward rew ON rew.upload_id = u.upload_id
