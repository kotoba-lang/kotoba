-- Audits for mv_kabi_nutrient_flow and mv_kabi_eta_gradient (ADR-2605080500)

AUDIT (
  name assert_kabi_nutrient_hypha_count_positive,
  model dev.mv_kabi_nutrient_flow
)
SELECT *
FROM dev.mv_kabi_nutrient_flow
WHERE hypha_count <= 0;

AUDIT (
  name assert_kabi_eta_gradient_inbound_count_positive,
  model dev.mv_kabi_eta_gradient
)
SELECT *
FROM dev.mv_kabi_eta_gradient
WHERE inbound_count <= 0;

AUDIT (
  name assert_kabi_eta_gradient_eta_avg_nonneg,
  model dev.mv_kabi_eta_gradient
)
SELECT *
FROM dev.mv_kabi_eta_gradient
WHERE inbound_eta_avg < 0;
