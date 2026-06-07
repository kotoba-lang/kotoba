-- Open JPN MyNumber electronic application status: flat projection of electronic applications.
MODEL (
  name dev.mv_open_jpn_mynumber_electronic_application_status,
  kind FULL,
  dialect postgres,
  description 'Flat projection of vertex_open_jpn_mynumber_electronic_application for status queries.',
  grain [application_id],
  tags [open_jpn, mynumber, electronic_application, status]
);

SELECT
  vertex_id AS application_id,
  person_ref,
  requester_agency,
  procedure_code,
  purpose_code,
  application_payload_hash,
  status,
  external_reference,
  submitted_at,
  updated_at
FROM vertex_open_jpn_mynumber_electronic_application
