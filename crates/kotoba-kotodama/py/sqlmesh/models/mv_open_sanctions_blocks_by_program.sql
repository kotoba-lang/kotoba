-- Open sanctions blocks by program: screening counts per program and decision.
MODEL (
  name dev.mv_open_sanctions_blocks_by_program,
  kind FULL,
  dialect postgres,
  description 'Per (program, decision): screening count and latest screened_at for block/manual-review.',
  grain [program, decision],
  tags [open_sanctions, screening, block]
);

SELECT
  best_match_program AS program,
  decision,
  COUNT(*) AS screening_count,
  MAX(screened_at) AS latest_screened_at
FROM vertex_open_sanctions_screening
WHERE decision IN ('block', 'manual-review')
GROUP BY best_match_program, decision
