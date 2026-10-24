# tedai (手代) — member-computer-operation actor

Tier-B R0 actor (`did:web:etzhayyim.com:actor:tedai`, ADR-2606101400): the charter-clean inverse of
commercial computer-use, and karakuri's OS-layer sibling. Gives a member a uniform, auditable
command vocabulary (**DesktopOp**) over their **own computer**, driving the safest adapter —
**T1 scripting/accessibility-API > T2 stance-permitted vision-pointer (on-device vision only) >
T3 file-level** — with every op a kotoba Datom and all actuation gated behind member signature +
Council.

Defining invariants: own-device-only (G1, not a RAT) · stance-honest / no detection-evasion (G2) ·
no-server-key (G3) · a screenshot never leaves the device (G4) · `:outward` ops held at the Council
gate even with a member signature (G5) · no-surveillance, never bossware (G8) · hash-only evidence
(G9). Browser surfaces route to **karakuri** (N7).

See `AGENTS.md` for the full gate/non-goal table and build/test commands, `manifest.edn` for the
machine-readable manifest, and ADR-2606101400 for the decision record.

Canonical contracts are EDN: `manifest.edn`, `schema/schema.edn`, `cells/*.edn`, and
`lex/*.edn`. Runtime code lives under `src/tedai`; tests live under `test/tedai`.
Run the standalone suite with `kbb -M:test`.
