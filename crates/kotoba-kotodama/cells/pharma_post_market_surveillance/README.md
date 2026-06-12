# pharma_post_market_surveillance — Pregel cell for daily AE aggregation + open published narrative

Per **ADR-2605250500 §Decision 3 G5** (adverse event public reporting) +
**ADR-2605250545 §Decision 6**.

Paired actor: [yakushi](../../yakushi/).

Murakumo node (proposed): **levi** (audit/witness leader, paired with `pharma_adverse_event`).

Trigger: daily cron (`0 8 * * *` JST default).

Aggregation logic (G10 PII isolation):
- No patient DID in aggregates — only by lot + severity + outcome
- Severity histogram (CIOMS III: mild / moderate / severe / serious / life-threatening / fatal)
- Causality histogram (WHO-UMC: certain / probable / possible / unlikely / unrelated / unassessable)
- Lot # back-reference for safety signal investigation
- Public narrative published to yakushi MST

Signal detection threshold (G3 silen-pharma-review trigger):
- Any "serious" / "life-threatening" / "fatal" → immediate Council Lv6+ escalation
- Any "severe" cluster (≥ 3 in single lot) → Council Lv6+ escalation
- Any new symptom category not in label → Council Lv6+ escalation
