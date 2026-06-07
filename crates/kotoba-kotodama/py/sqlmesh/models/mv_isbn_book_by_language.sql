-- ISBN book by language: book and public domain counts per language.
MODEL (
  name dev.mv_isbn_book_by_language,
  kind FULL,
  dialect postgres,
  description 'Per language: total books and public domain (pd/cc0/cc_by/cc_by_sa) count.',
  grain [language],
  tags [isbn, book, language, pd]
);

SELECT
  b.language,
  COUNT(*) AS book_count,
  COUNT(c.vertex_id) AS pd_count
FROM vertex_isbn_book b
LEFT JOIN vertex_isbn_book_copyright c
  ON c.isbn13 = b.isbn13
  AND c.status IN ('pd', 'cc0', 'cc_by', 'cc_by_sa')
GROUP BY b.language
