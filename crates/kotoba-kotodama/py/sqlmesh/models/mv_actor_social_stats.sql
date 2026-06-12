-- SQLMesh model: mv_actor_social_stats
-- Canonical SQL source for the RisingWave streaming MV of the same name.
--
-- This file is the SQL source of truth (ADR-2605080500).
-- The deployed RisingWave MV is created via:
--
--   CREATE MATERIALIZED VIEW mv_actor_social_stats AS <this SELECT>;
--
-- To update: edit this file → run `sqlmesh plan` → review generated diff →
-- apply via rw-health-gate.sh + psql DDL.
--
-- Lineage:  graphar.vertex_repo_record → mv_actor_social_stats

MODEL (
  name dev.mv_actor_social_stats,
  kind FULL,
  dialect postgres,
  description 'Per-actor social stats: post count derived from vertex_repo_record.',
  grain [actor_did],
  tags [social, actor, materialized_view]
);

SELECT
  normalize_actor_did(repo)                                            AS actor_did,
  COUNT(*) FILTER (
    WHERE collection = 'app.bsky.feed.post'
  )                                                                    AS posts_count,
  COUNT(*) FILTER (
    WHERE collection = 'app.bsky.graph.follow'
  )                                                                    AS following_count,
  MAX(ts_ms)                                                           AS last_activity_ms
FROM graphar.vertex_repo_record
GROUP BY 1
