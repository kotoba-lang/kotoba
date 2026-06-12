-- Telecom MEC EAS inventory: edge application server counts per provider/slice/DNN/status.
MODEL (
  name dev.mv_telecom_mec_eas_inventory,
  kind FULL,
  dialect postgres,
  description 'Per (eas_provider_id, snssai, dnn, status): EAS count from vertex_telecom_mec_eas.',
  grain [eas_provider_id, snssai, dnn, status],
  tags [telecom, mec, eas, inventory]
);

SELECT
  eas_provider_id,
  snssai,
  dnn,
  status,
  COUNT(*) AS eas_count
FROM vertex_telecom_mec_eas
GROUP BY eas_provider_id, snssai, dnn, status
