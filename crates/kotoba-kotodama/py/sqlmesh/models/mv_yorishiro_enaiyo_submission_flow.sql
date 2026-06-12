-- Yorishiro enaiyo submission flow: draft → submit job → receipt → docx blob lifecycle.
MODEL (
  name dev.mv_yorishiro_enaiyo_submission_flow,
  kind FULL,
  dialect postgres,
  description 'Per draft: submission job, receipt, docx blob with status fields and timestamps.',
  grain [draft_id],
  tags [yorishiro, enaiyo, submission, flow]
);

SELECT
  d.draft_id,
  d.status AS draft_status,
  s.job_id,
  s.status AS submit_status,
  r.receipt_number,
  r.submitted_at,
  b.blob_key AS docx_blob_key,
  d.created_at
FROM vertex_yorishiroEnaiyo_draftNaiyo d
LEFT JOIN vertex_yorishiroEnaiyo_submitJob s ON s.draft_id = d.draft_id
LEFT JOIN vertex_yorishiroEnaiyo_receipt r ON r.job_id = s.job_id
LEFT JOIN vertex_yorishiroEnaiyo_docxBlob b ON b.draft_id = d.draft_id
