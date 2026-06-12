# seigyo_plc_program_lifecycle — Pregel cell for IEC 61131-3 program lifecycle

Per **ADR-2606111000 §4** (PLC-program-as-attested-record lifecycle) + **§6** row 1.

Murakumo node (proposed): **judah**. §2(a)(c) risk: **HIGH**.

Lifecycle owned by this cell:

```
author (ST) → static checks + OpenPLC simulation → engineer review
  → attestation (seigyo.plcProgramAttestation: program CID + envelope table)
  → deploy to OpenPLC runtime
  → runtime hash watch (seigyo.runtimeAttestation heartbeat;
    mismatch ⇒ L3 cells refuse recipe dispatch to that controller)
```

Setpoint envelopes (`seigyo.setpointEnvelope`, ADR §3.4) are compiled into
the attested program: Murakumo optimization proposals outside the envelope
are clamped at L1 regardless of upstream request.

**Never in the safety path** (ADR §3): L1S interlocks are hardwired and
only *attested* via [`seigyo_interlock_attestation`](../seigyo_interlock_attestation/).

Scaffold-only until Council fleet.toml attestation + silen-seigyo baseline
review (import raises `RuntimeError`).
