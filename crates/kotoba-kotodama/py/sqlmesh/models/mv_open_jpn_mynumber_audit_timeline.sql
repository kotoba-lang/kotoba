-- Open JPN MyNumber audit timeline: flat projection of audit events.
MODEL (
  name dev.mv_open_jpn_mynumber_audit_timeline,
  kind FULL,
  dialect postgres,
  description 'Flat projection of vertex_open_jpn_mynumber_audit_event for timeline queries.',
  grain [audit_event_vertex_id],
  tags [open_jpn, mynumber, audit, timeline]
);

SELECT
  vertex_id AS audit_event_vertex_id,
  event_type,
  person_ref,
  requester_agency,
  holder_agency,
  purpose_code,
  dataset_code,
  result,
  created_at
FROM vertex_open_jpn_mynumber_audit_event
