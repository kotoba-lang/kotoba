-- Repository activity by owner: per-owner commit count and latest commit.
MODEL (
  name dev.mv_repository_activity_by_owner,
  kind FULL,
  dialect postgres,
  description 'Per owner_did: commit count and latest_commit_at from vertex_repository_commit.',
  grain [owner_did],
  tags [repository, activity, owner]
);

SELECT
  owner_did,
  COUNT(*) AS commit_count,
  MAX(committer_timestamp) AS latest_commit_at
FROM vertex_repository_commit
GROUP BY owner_did
