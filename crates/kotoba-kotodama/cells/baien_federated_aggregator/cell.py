"""baien_federated_aggregator cell — Murakumo placement for L4 of ADR-2605242600.

R0 scaffold. The package ``__init__`` raises ``RuntimeError`` at import
time, so this module is unreachable by ordinary callers. It exists to
document the cell's eventual Pregel shape so that:

  - ``50-infra/murakumo/fleet.toml`` can name the cell for placement
    even before activation,
  - the future R2 implementation has a fixed file path + symbol surface
    to fill in,
  - reviewers can read the planned LangGraph topology in one place.

The real aggregation math (coordinate-wise median / Krum / FedAvg +
DP-Gaussian) lives in
``70-tools/baien-distill/src/baien_distill/nodes/federated_aggregate.py``.
This cell is the Murakumo-side dispatch + subscription layer that
feeds that node from the lexicon firehose.

Planned topology (R2+, NOT compiled in R0):

    START
      -> subscribe_firehose       # com.etzhayyim.baien.distributedTrainDelta
      -> filter_round              # match iter + baseModelCid (G10)
      -> verify_sbt                # Adherent SBT holder check (G7)
      -> verify_signature          # ES256 against DID-resolved key (G4)
      -> rescan_charter_rider      # re-run scan on datasetShardCid (G6)
      -> wellbecoming_gate         # lossAfter < lossBefore * 0.98 (G8)
      -> byzantine_aggregate       # median / Krum / FedAvg + DP (G9)
      -> eval_on_fleet             # e7m bench micro on merged adapter
      -> commit_or_quarantine      # accept -> distilled-models.jsonl
                                   # reject -> quarantined.jsonl
    END
"""

from __future__ import annotations

from typing import Any, TypedDict


class FederatedAggregatorState(TypedDict, total=False):
    """Planned state shape for the R2+ implementation."""

    # Round identity
    iter: int
    base_model_cid: str

    # Inputs (collected by subscribe_firehose)
    pending_deltas: list[dict[str, Any]]

    # Per-gate survivors
    sbt_verified: list[dict[str, Any]]
    sig_verified: list[dict[str, Any]]
    rescan_passed: list[dict[str, Any]]
    wellbecoming_passed: list[dict[str, Any]]

    # Aggregation
    aggregation_strategy: str  # "coordinate-median" | "krum" | "fedavg-dp"
    merged_delta_cid: str | None

    # Outcome
    decision: str  # "commit" | "quarantine" | "abort-round"
    notes: list[str]


def build_graph() -> Any:
    """Compile the cell's LangGraph state machine.

    R0 — not yet implemented. Activation gated on Council attestation
    per ADR-2605242600 R2.
    """
    raise NotImplementedError(
        "baien_federated_aggregator.build_graph: R0 scaffold. "
        "Activation gated on Council attestation per ADR-2605242600 R2."
    )


def aggregate_round(_state: FederatedAggregatorState) -> FederatedAggregatorState:
    """Single-round entry-point. R0 — not yet implemented."""
    raise NotImplementedError(
        "baien_federated_aggregator.aggregate_round: R0 scaffold. "
        "Activation gated on Council attestation per ADR-2605242600 R2."
    )
