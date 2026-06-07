-- Open JPN MyNumber medical info status: flat projection of medical info requests.
MODEL (
  name dev.mv_open_jpn_mynumber_medical_info_status,
  kind FULL,
  dialect postgres,
  description 'Flat projection of vertex_open_jpn_mynumber_medical_info_request for status queries.',
  grain [medical_request_id],
  tags [open_jpn, mynumber, medical, status]
);

SELECT
  vertex_id AS medical_request_id,
  person_ref,
  requester_agency,
  purpose_code,
  dataset_code,
  consent_id,
  status,
  response_ref,
  requested_at,
  updated_at
FROM vertex_open_jpn_mynumber_medical_info_request
