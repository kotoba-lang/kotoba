-- Telecom emergency routing: emergency call counts per jurisdiction/service/PSAP.
MODEL (
  name dev.mv_telecom_emergency_routing,
  kind FULL,
  dialect postgres,
  description 'Per (jurisdiction, emergency_service, psap_id): emergency call count.',
  grain [jurisdiction, emergency_service, psap_id],
  tags [telecom, emergency, routing]
);

SELECT
  jurisdiction,
  emergency_service,
  psap_id,
  COUNT(*) AS call_count
FROM vertex_telecom_emergency_call
GROUP BY jurisdiction, emergency_service, psap_id
