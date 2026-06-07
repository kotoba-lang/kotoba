-- India e-filing submission status: flat projection of all submissions with status details.
MODEL (
  name dev.mv_ind_efiling_submission_status,
  kind FULL,
  dialect postgres,
  description 'All e-filing submissions with jurisdiction, provider, status, external reference, and adapter status.',
  grain [idempotency_key],
  tags [ind, efiling, submission, status]
);

SELECT
  jurisdiction,
  provider_key,
  provider_kind,
  source_vertex_id,
  idempotency_key,
  payload_hash,
  status,
  external_reference,
  adapter_status,
  created_at
FROM vertex_ind_efiling_submission
