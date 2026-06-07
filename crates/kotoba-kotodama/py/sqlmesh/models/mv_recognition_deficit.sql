-- Recognition deficit: per-actor recognition seeking and avg frustration.
MODEL (
  name dev.mv_recognition_deficit,
  kind FULL,
  dialect postgres,
  description 'Per actor_vid: distinct recognition targets count and avg frustration from emotional valence.',
  grain [actor_vid],
  tags [recognition, deficit, emotion]
);

SELECT
  seek.src_vid AS actor_vid,
  COUNT(DISTINCT seek.dst_vid) AS recognition_sought,
  AVG(CASE seek.emotional_valence
    WHEN 'seeking' THEN 0.5
    WHEN 'resentment' THEN 0.8
    WHEN 'rejection' THEN 1.0
    WHEN 'affirming' THEN 0.0
    ELSE 0.3
  END) AS avg_frustration
FROM edge_seeks_recognition_from seek
GROUP BY seek.src_vid
