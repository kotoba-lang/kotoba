-- Telecom TMF active offerings: TMF product offerings in Active or Launched lifecycle.
MODEL (
  name dev.mv_telecom_tmf_active_offerings,
  kind FULL,
  dialect postgres,
  description 'TMF product offerings with lifecycle Active or Launched: id, name, validity window, org.',
  grain [offering_id],
  tags [telecom, tmf, offering, active]
);

SELECT
  offering_id,
  name,
  lifecycle_status,
  valid_from_at,
  valid_to_at,
  org_id
FROM vertex_telecom_tmf_product_offering
WHERE lifecycle_status IN ('Active', 'Launched')
