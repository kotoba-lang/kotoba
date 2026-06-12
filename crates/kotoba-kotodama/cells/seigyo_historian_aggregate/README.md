# seigyo_historian_aggregate — Pregel cell for N7 telemetry aggregation

Per **ADR-2606111000 §5** (telemetry + historian) + **§6** row 5.

Murakumo node (proposed): **simeon**. §2(a)(c) risk: **LOW**.

- Full-rate process data (ms–s sampling) stays in the **on-site
  historian** (TimescaleDB / InfluxDB OSS on religious-corp hardware).
- Northbound past the site boundary: `seigyo.telemetryAggregateRecord`
  only — ≥1-minute buckets for process variables, ≥1-hour buckets for
  person-attributable signals (hikari N7 inheritance, same rule as
  ADR-2605265000 §1.3).
- Feeds the Murakumo optimizer (ADR-2605215000: Murakumo-only inference);
  optimizer output is advisory and lands only through attested setpoint
  envelopes (ADR §3.4) via [`seigyo_opcua_bridge`](../seigyo_opcua_bridge/).

Scaffold-only until Council fleet.toml attestation + silen-seigyo baseline
review (import raises `RuntimeError`).
