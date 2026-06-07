-- Telecom NTN cell state: NTN cell counts per pattern/payload/PLMN/status.
MODEL (
  name dev.mv_telecom_ntn_cell_state,
  kind FULL,
  dialect postgres,
  description 'Per (cell_pattern, payload_kind, plmn_id, status): cell count and avg beam_count.',
  grain [cell_pattern, payload_kind, plmn_id, status],
  tags [telecom, ntn, cell, satellite]
);

SELECT
  cell_pattern,
  payload_kind,
  plmn_id,
  status,
  COUNT(*) AS cell_count,
  AVG(beam_count) AS avg_beam_count
FROM vertex_telecom_ntn_cell
GROUP BY cell_pattern, payload_kind, plmn_id, status
