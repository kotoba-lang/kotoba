-- ISBN book by jurisdiction: book count per jurisdiction and copyright status.
MODEL (
  name dev.mv_isbn_book_by_jurisdiction,
  kind FULL,
  dialect postgres,
  description 'Per (jurisdiction, status): book count from isbn copyright table.',
  grain [jurisdiction, status],
  tags [isbn, book, jurisdiction, copyright]
);

SELECT
  c.jurisdiction,
  c.status,
  COUNT(*) AS book_count
FROM vertex_isbn_book_copyright c
GROUP BY c.jurisdiction, c.status
