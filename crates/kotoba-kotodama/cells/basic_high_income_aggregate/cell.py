"""BasicHighIncomeAggregateCell — liberation R0 Pregel cell.

Per ADR-2605301020 (Basic High Income doctrine) §5/§8 + ADR-2605261000 (Labor
Liberation ladder L0..L6, §4 Liberation Metric).

Purpose: assemble the aggregate ``basicHighIncome`` block of the quarterly
``com.etzhayyim.liberation.metricReport`` from the toritate per-adherent outputs
(``toritate_imputed_income_compute`` FLOW + ``toritate_commons_asset_value`` STOCK)
— emitting only median/percentile figures, never per-adherent identity. Computes
``highIncomeBenchmarkRatioPermille`` against the OECD upper-income-decile basket
and asserts the ``cashStipendUsdMicros == 0`` invariant on every report.

Constitutional ceiling (CRITICAL — IMMUTABLE):
  - cashStipendUsdMicros ≡ 0 (ADR-2605261000 §5 N1): asserted on every emitted
    report — its presence-and-zero IS the on-chain proof N1 holds. A nonzero value
    is refused (constitutional violation).
  - AGGREGATE-ONLY, NO PII (ADR-2605301020 §7 + ADR-2605261000 §4 + N6): structural
    no-leaderboard; inputs are ADR-2605181100-encrypted; output carries no
    per-adherent identity (cf. ADR-2605260215 aggregation pattern).
  - Wellbecoming guard (ADR-2605301020 §6): a rise in imputed income that coincides
    with a Wellbecoming decline flags `holdStage` review, not celebration.
Output Lexicon(s): com.etzhayyim.liberation.metricReport (basicHighIncome block).
Murakumo node: levi (liberation metric tribe, per ADR-2605301020 §8).

R0 scaffold — import-time RuntimeError until R1.
"""

from __future__ import annotations

# ─────────────────────────────────────────────────────────────────────────────
# R1 activation gate (ADR-2605301020 / ADR-2605261000)
# ─────────────────────────────────────────────────────────────────────────────
#
# Scaffold-only until ALL hold:
#   1. Council Lv6+ ≥3 attested the Basic High Income doctrine (ADR-2605301020)
#      AND the Liberation Ladder master (ADR-2605261000).
#   2. the toritate compute cells (toritate_imputed_income_compute +
#      toritate_commons_asset_value) are themselves R1-active (their Council +
#      valuation gate removed) — this aggregate has no inputs otherwise.
#
# Any None below → import-time RuntimeError.

COUNCIL_DOCTRINE_ATTESTATION_TX_HASH: str | None = None
TORITATE_COMPUTE_CELLS_ACTIVE: bool = False

if (
    COUNCIL_DOCTRINE_ATTESTATION_TX_HASH is None
    or not TORITATE_COMPUTE_CELLS_ACTIVE
):
    raise RuntimeError(
        "liberation R0 scaffold: activate via Council ADR-2605301020 + "
        "ADR-2605261000 post-ratification — Council has not attested the Basic "
        "High Income doctrine and/or the Liberation Ladder (Lv6+ ≥3), and/or the "
        "toritate compute cells (imputed_income_compute + commons_asset_value) are "
        "not yet R1-active. Do not deploy. cashStipendUsdMicros≡0 (N1) / "
        "AGGREGATE-ONLY-NO-PII (N6) ceiling is constitutional."
    )


# ─────────────────────────────────────────────────────────────────────────────
# Pregel super-step skeleton (only reached after the Council gate is removed)
# ─────────────────────────────────────────────────────────────────────────────
#
# from kotodama.organism import PregelCell
#
# class BasicHighIncomeAggregateCell(PregelCell):
#     process_step = "basic_high_income_aggregate"
#     pregel_tier = "B"
#     murakumo_node = "levi"   # proposed; liberation metric tribe
#
#     def super_step(self, msg, prior):
#         raise NotImplementedError("basic-high-income aggregate R1")


__all__ = ["BasicHighIncomeAggregateCell"]
