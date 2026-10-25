# On-call / Pager Runbook

Status: operational baseline (local sinks proven; vendor adapters unit-tested; live Slack/PD optional)  
Date: 2026-07-18

## Purpose

Wire continuous-monitoring alerts (`kotoba.security.continuous-monitoring/v1`)
to human responders without inventing secrets or claiming a live roster when
none is provisioned.

Executable delivery:

- `src/kotoba/security/alert_adapters.cljk` — Slack / PagerDuty / generic payload shapes
- `src/kotoba/security/alert_delivery.cljk` — file / webhook / stdout sinks
- `scripts/emit-alert.cljk` — CLI smoke + EDN replay
- `scripts/monitoring-heartbeat.cljk` — collector-stub heartbeat sample
- `scripts/simulate-revoked-signer.cljk --write --deliver` — SEV-1 technical path
- `scripts/mock-webhook-sink.cljk` — local HTTP 200 fixture

Machine-readable roster (example contacts only):
[`registers/on-call-roster.edn`](../registers/on-call-roster.edn).

Evidence: `EV-0012` (pager wiring), `EV-0017` (heartbeat stub + vendor adapters).

## Severity → channel / escalation

| Severity | Channel (example) | Page? | Ack | Escalate |
|---|---|---|---|---|
| SEV-1 | `#security-oncall-example` | yes | 5m | 15m → secondary → security-owner |
| SEV-2 | `#security-oncall-example` | yes | 15m | 30m |
| SEV-3 | `#security-notify-example` | no | 4h | 24h |
| SEV-4 | `#security-notify-example` | no | 7d | — |

See [Incident Response](incident-response.md) for full playbooks.

## Roster (example only — not live humans)

Contacts use RFC 2606 `@example.invalid`. **Do not** treat as real coverage.

| Role | Contact | Timezone | Escalation path |
|---|---|---|---|
| Primary | `security-primary@example.invalid` | UTC | secondary |
| Secondary | `security-secondary@example.invalid` | UTC | security-owner |
| Security owner | `security-owner@example.invalid` | UTC | (terminal) |
| Package owner | `package-owner@example.invalid` | UTC | — |
| Crypto owner | `crypto-owner@example.invalid` | UTC | — |
| Operations owner | `operations-owner@example.invalid` | UTC | — |

Escalation minutes (from roster):

- primary unack → 15m
- secondary unack → 30m
- security-owner unack → 45m
- SEV-1 → freeze releases per IR playbook

## Environment template

Copy [`.env.pager.example`](../.env.pager.example) to a **gitignored** local file
or export in the shell. Never commit real webhook URLs or routing keys.

```sh
# Optional live webhook (file sink always works without this)
export KOTOBA_SECURITY_ALERT_WEBHOOK='https://hooks.slack.com/services/XXX/YYY/ZZZ'
# or PagerDuty Events API v2 enqueue URL:
# export KOTOBA_SECURITY_ALERT_WEBHOOK='https://events.pagerduty.com/v2/enqueue'
# export KOTOBA_SECURITY_PAGERDUTY_ROUTING_KEY='…from kagi/Keychain only…'

# Force vendor shape (optional; else URL heuristics)
export KOTOBA_SECURITY_ALERT_SINK=slack   # slack | pagerduty | generic

# Documentation / future routing
# export KOTOBA_SECURITY_ALERT_CHANNEL='#security-oncall'
```

### Vendor selection

| Source | Result |
|---|---|
| `KOTOBA_SECURITY_ALERT_SINK=slack\|pagerduty\|generic` | forced |
| URL host `hooks.slack.com` | Slack Incoming Webhook body (`text` + `blocks`) |
| URL host `events.pagerduty.com` | PagerDuty Events API v2 (`event_action` + `payload`) |
| else | generic continuous-monitoring v1 JSON |

File sink is **always** the canonical alert map (not vendor-shaped).

Honest behavior when webhook unset:

```text
webhook skipped (KOTOBA_SECURITY_ALERT_WEBHOOK unset)
```

## Local webhook fixture (mock HTTP 200)

```sh
# Terminal A — mock receiver
kbb --backend sci --classpath src scripts/mock-webhook-sink.cljk --port 9876

# Terminal B — smoke (generic body to mock)
export KOTOBA_SECURITY_ALERT_WEBHOOK='http://127.0.0.1:9876/alert'
kbb --backend sci --classpath src scripts/emit-alert.cljk --smoke --dir /tmp/kotoba-security-pager-smoke

# Force Slack shape against mock (still no secrets)
export KOTOBA_SECURITY_ALERT_SINK=slack
kbb --backend sci --classpath src scripts/emit-alert.cljk --smoke
```

## Heartbeat / collector stub

```sh
kbb --backend sci --classpath src scripts/monitoring-heartbeat.cljk
kbb --backend sci --classpath src scripts/monitoring-heartbeat.cljk --deliver
```

Writes `evidence/<date>/monitoring-heartbeat.edn` + `collector-stub-note.md`.
Does **not** scrape live hosts — residual until real collectors exist.

## Live Slack / PagerDuty (credentials required)

1. Create vendor webhook / Events API integration; store URL (+ PD routing key)
   only in kagi / OS Keychain / 1Password — **not** in git.
2. Export env vars for the session.
3. Run smoke / heartbeat with `--deliver`.
4. Confirm channel/incident; record evidence without pasting secrets.

As of 2026-07-18: secrets-location-map has **no** Slack/PagerDuty webhook item
for this repo. Live vendor delivery remains residual until an owner provisions
credentials.

## Alert routing (policy)

| Alert name | Severity | Route |
|---|---|---|
| `trusted-signer-verification-failure` | SEV-1 | primary + package + security-owner |
| `host-capability-denial-spike` | SEV-2 | primary + operations |
| `monitoring-heartbeat` | SEV-4 | ops notify only (stub) |
| `pager-wiring-smoke` | SEV-3 | channel only (test) |

## Residual (R-005)

- File sink + local mock webhook: **proven** (EV-0012).
- Vendor payload adapters (Slack/PD/generic) + unit tests: **landed** (EV-0017).
- Example on-call roster (`@example.invalid`): **landed** (not live humans).
- Heartbeat collector stub: **landed** (not live metrics).
- Production Slack/PagerDuty credentials: **unset**.
- Live human rotation with real contacts: **not filled**.
