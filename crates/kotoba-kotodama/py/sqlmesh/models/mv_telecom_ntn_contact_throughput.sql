-- Telecom NTN contact throughput: per-station/contact ingress/egress aggregates.
MODEL (
  name dev.mv_telecom_ntn_contact_throughput,
  kind FULL,
  dialect postgres,
  description 'Per (station_vid, contact_kind): contact count, total duration, total ingress/egress bytes.',
  grain [station_vid, contact_kind],
  tags [telecom, ntn, contact, throughput]
);

SELECT
  station_vid,
  contact_kind,
  COUNT(*) AS contact_count,
  SUM(duration_seconds) AS total_duration_seconds,
  SUM(ingress_bytes) AS total_ingress_bytes,
  SUM(egress_bytes) AS total_egress_bytes
FROM vertex_telecom_ntn_contact
GROUP BY station_vid, contact_kind
