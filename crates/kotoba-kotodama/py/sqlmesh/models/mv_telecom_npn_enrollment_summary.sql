-- Telecom NPN enrollment summary: NPN subscriber enrollments per enterprise/class/status.
MODEL (
  name dev.mv_telecom_npn_enrollment_summary,
  kind FULL,
  dialect postgres,
  description 'Per (sponsored_by_enterprise_org_id, allowed_device_class, status): enrollment count and total devices.',
  grain [sponsored_by_enterprise_org_id, allowed_device_class, status],
  tags [telecom, npn, enrollment]
);

SELECT
  sponsored_by_enterprise_org_id,
  allowed_device_class,
  status,
  COUNT(*) AS enrollment_count,
  SUM(device_count) AS total_devices
FROM vertex_telecom_npn_subscriber_enrollment
GROUP BY sponsored_by_enterprise_org_id, allowed_device_class, status
