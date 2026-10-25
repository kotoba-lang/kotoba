# EV-0018 — Host-denial telemetry + metric collector (2026-07-18)

## What landed

- `src/kotoba/security/host_denial_telemetry.cljk` — pure aggregate + threshold
  evaluation over continuous-monitoring v1 alert maps.
- `scripts/aggregate-host-denial.cljk` — nbb scanner for `evidence/*/alerts`
  (or `--dir`), writes `host-denial-summary.edn`, optional spike alert emit.
- `scripts/metric-collect.cljk` — mini collector: counts by severity / name /
  signal / decision (extends heartbeat beyond stub).
- Unit tests + `test/fixtures/alerts/*` fixture EDN.

## Honest limits

- Input is **structured alert EDN already on disk** (synthetic samples from
  revoked-signer sim, pager smoke, heartbeat stub). Not a live aiueos host
  trap/denial receipt stream.
- No Slack/PagerDuty tokens invented; `--deliver` still skips webhook when
  `KOTOBA_SECURITY_ALERT_WEBHOOK` is unset.
- Default threshold: ≥1 `host-capability-denial-spike` **or** summed
  `:alert/denial-count` ≥ 50.

## Commands

```sh
kbb --backend sci --classpath src scripts/aggregate-host-denial.cljk --dir evidence/2026-07-18
kbb --backend sci --classpath src scripts/metric-collect.cljk --dir evidence/2026-07-18 --write
kbb -M:test -n kotoba.security.host-denial-telemetry-test
```
