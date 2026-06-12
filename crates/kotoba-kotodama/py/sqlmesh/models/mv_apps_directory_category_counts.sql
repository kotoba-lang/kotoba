-- Apps directory listing count grouped by category and status.
MODEL (
  name dev.mv_apps_directory_category_counts,
  kind FULL,
  dialect postgres,
  description 'Count of apps directory listings grouped by category and status.',
  grain [category, status],
  tags [apps, directory, category, count]
);

SELECT category, status, COUNT(*)::BIGINT AS listing_count
FROM vertex_apps_directory_listing
GROUP BY category, status
