# seigyo_scada_gateway — Pregel cell for L2 SCADA config + alarms

Per **ADR-2606111000 §1** (L2) + **§6** row 3.

Murakumo node (proposed): **judah**. §2(a)(c) risk: **MEDIUM**.

- SCADA project files (FUXA / Rapid SCADA / OpenSCADA — per-site choice)
  are CID-attested via `seigyo.scadaProjectAttestation` after Charter
  Rider §2 audit, then deployed; a site running an unattested project is
  flagged like a runtime-hash mismatch.
- Alarm/event ingestion: full-fidelity `seigyo.alarmEventRecord`
  northbound (alarms are operational facts, exempt from the §5 aggregate
  bucketing that applies to process waveforms).
- Commercial SCADA/HMI runtimes prohibited per ADR §2.

Scaffold-only until Council fleet.toml attestation + silen-seigyo baseline
review (import raises `RuntimeError`).
