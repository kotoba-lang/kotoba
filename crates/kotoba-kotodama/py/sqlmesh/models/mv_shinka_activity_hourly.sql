-- Shinka activity hourly: hourly post and kyumei counts unioned from evolution and knowledge tables.
MODEL (
  name dev.mv_shinka_activity_hourly,
  kind FULL,
  dialect postgres,
  description 'Per activity_hour: post_count (didPost evolution) and kyumei_count from shinka_knowledge.',
  grain [activity_hour],
  tags [shinka, activity, hourly]
);

SELECT
  activity_hour,
  SUM(post_count)::BIGINT AS post_count,
  SUM(kyumei_count)::BIGINT AS kyumei_count
FROM (
  SELECT
    date_trunc('hour', created_date) AS activity_hour,
    COUNT(*)::BIGINT AS post_count,
    0::BIGINT AS kyumei_count
  FROM vertex_shinka_evolution
  WHERE COALESCE(CAST(props AS VARCHAR), '') LIKE '%"didPost":true%'
  GROUP BY 1
  UNION ALL
  SELECT
    date_trunc('hour', created_date) AS activity_hour,
    0::BIGINT AS post_count,
    COUNT(*)::BIGINT AS kyumei_count
  FROM vertex_shinka_knowledge
  GROUP BY 1
) s
GROUP BY activity_hour
