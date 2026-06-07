-- Patent blob coverage: PDF, WebP, and OCR completion counts per jurisdiction.
MODEL (
  name dev.mv_patent_blob_coverage,
  kind FULL,
  dialect postgres,
  description 'Per jurisdiction: total patent blobs, PDF fetched, WebP done, OCR done, bytes totals.',
  grain [jurisdiction],
  tags [patent, blob, pdf, ocr, coverage]
);

SELECT
  jurisdiction,
  COUNT(*) AS total,
  COUNT(pdf_sha256) AS pdf_fetched,
  COUNT(webp_cid) AS webp_done,
  COUNT(ocr_text_cid) AS ocr_done,
  SUM(pdf_bytes) AS bytes_pdf,
  SUM(webp_bytes) AS bytes_webp
FROM vertex_patent_blob
GROUP BY jurisdiction
