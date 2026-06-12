-- Open DOI by publisher: active DOI count per publisher and publication type.
MODEL (
  name dev.mv_open_doi_by_publisher,
  kind FULL,
  dialect postgres,
  description 'Per (publisher, publication_type): active DOI count and latest published timestamp.',
  grain [publisher, publication_type],
  tags [open_doi, publisher, research, publication]
);

SELECT
  publisher,
  publication_type,
  COUNT(*) AS doi_count,
  MAX(published_at) AS latest_published_at
FROM vertex_open_doi_doi
WHERE status = 'active'
GROUP BY publisher, publication_type
