# seigyo_interlock_attestation — Pregel cell for safety-interlock verification

Per **ADR-2606111000 §3.5** (safety-path invariant) + **§6** row 2.

Murakumo node (proposed): **benjamin**. §2(a)(c) risk: **HIGH**
(safety-of-life adjacency; the cell itself is attestation-only).

Records `seigyo.interlockVerificationRecord` at commissioning and on each
annual re-verification: a qualified engineer physically verifies each
hardwired interlock (E-stop, over-pressure, over-temperature, gas detection,
light curtains, lockout-tagout) and the cell anchors engineer DID +
photo/measurement evidence CIDs.

**The cell attests the safety layer; it is never in it** (ADR §3):
safety functions are hardwired / safety-relay (L1S) and must complete
with the site network cable cut. IEC 61508 / 61511 followed as design
reference (no certification claim at R0/R1 scale).

Scaffold-only until Council fleet.toml attestation + silen-seigyo baseline
review (import raises `RuntimeError`).
