-- Telecom TSN stream state: TSN stream counts and avg max latency per reservation/class/status.
MODEL (
  name dev.mv_telecom_tsn_stream_state,
  kind FULL,
  dialect postgres,
  description 'Per (reservation_kind, traffic_class, status): stream count and avg max_latency_ns.',
  grain [reservation_kind, traffic_class, status],
  tags [telecom, tsn, stream]
);

SELECT
  reservation_kind,
  traffic_class,
  status,
  COUNT(*) AS stream_count,
  AVG(max_latency_ns) AS avg_max_latency_ns
FROM vertex_telecom_tsn_stream
GROUP BY reservation_kind, traffic_class, status
