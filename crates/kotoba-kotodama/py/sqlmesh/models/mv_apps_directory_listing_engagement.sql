-- Apps directory listing engagement: feature count and install intent count per listing.
MODEL (
  name dev.mv_apps_directory_listing_engagement,
  kind FULL,
  dialect postgres,
  description 'Per-listing feature count and install intent count for apps directory engagement.',
  grain [listing_id],
  tags [apps, directory, listing, engagement, features, installs]
);

SELECT
  l.listing_id,
  l.app_did,
  l.category,
  COUNT(DISTINCT f.vertex_id)::BIGINT AS feature_count,
  COUNT(DISTINCT i.vertex_id)::BIGINT AS install_intent_count
FROM vertex_apps_directory_listing l
LEFT JOIN vertex_apps_directory_feature f ON f.listing_id = l.listing_id
LEFT JOIN vertex_apps_directory_install_intent i ON i.listing_id = l.listing_id
GROUP BY l.listing_id, l.app_did, l.category
