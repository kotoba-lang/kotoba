-- ISBN book image coverage: image count and total bytes per source and role.
MODEL (
  name dev.mv_isbn_book_image_coverage,
  kind FULL,
  dialect postgres,
  description 'Per (source, role): active image count and total byte size.',
  grain [source, role],
  tags [isbn, book, image, coverage]
);

SELECT
  source,
  role,
  COUNT(*) AS image_count,
  SUM(byte_size) AS total_bytes
FROM vertex_isbn_book_image
WHERE status = 'active'
GROUP BY source, role
