"""baien_federated_aggregator — Murakumo Pregel cell scaffold.

R0 scaffold per ADR-2605242600. Import-time-failing until Council
attestation activates it (same pattern as the L5 routing-around cells
from CLAUDE.md row 35: member_registry / religious_marriage /
religious_corp_taxation).

Importing this package raises RuntimeError so the cell appears in the
catalogue and the Murakumo fleet.toml can reference it, while the
real implementation stays inert.
"""

raise RuntimeError(
    "baien_federated_aggregator: R0 scaffold — Council attestation "
    "pending per ADR-2605242600 R2 activation gate. Import-time block "
    "is intentional; do not bypass."
)
