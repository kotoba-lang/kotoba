# pharma_adverse_event — Pregel cell for patient AE intake

Per **ADR-2605250500 §Decision 3 G5 + G10** (public AE reporting + patient identity non-traceable)
+ **ADR-2605250545 §Decision 6** (AE submission + aggregation design)
+ **ADR-2605181100** (XChaCha20-Poly1305 envelope for patient identity).

Paired actor: [yakushi](../../yakushi/).

Murakumo node (proposed): **levi** (audit/witness leader).

Submission UI: ameno PWA (mobile-first) + non-adherent anonymous form.

Patient identity: XChaCha20-Poly1305 envelope (patient passkey-derived key,
sealed-recipient-only to yakushi Council Lv6+ DIDs).

Lot back-reference: full attestation chain CIDs available for safety signal investigation.

Resale / discrimination prohibited per G10 — recipient registry public,
external transmission requires Council Lv6+ supermajority.
