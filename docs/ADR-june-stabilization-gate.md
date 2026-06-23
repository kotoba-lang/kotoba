# ADR — June stabilization gate before public launch

- **Status:** accepted (in progress — June 2026)
- **Date:** 2026-06-23
- **Topics:** ops, deploy, availability, stability, release, go-to-market
- **Canonical repo:** `github.com/com-junkawasaki/kotoba`

## Context

kotoba (the substrate), `kotobase.net` (the hosted pin & host surface), and
`etzhayyim.com` are reaching the point where a public, developer-facing launch
is plausible. The vision is articulated in
[*Kotoba: A Distributed-Persistence Substrate for Hosting Spirit*](https://junkawasaki.com/en/posts/kotoba-substrate-for-spirit/)
(2026-06-06): kotoba is the place where an artificial organism / AI agent
dwells and moves — a content-addressed, immutable, distributed home for the
information that constitutes spirit.

A go-to-market motion was scoped (developer-led growth for the overseas
web3/IPFS + AI-agent audience), with a three-layer message funnel:

```
entry   : "agent memory you can't lose / pin in 30s"      → kotobase.net (organism/spirit withheld; conversion)
body    : "a place an artificial organism lives and moves" → organism layer (habitat narrative)
spirit  : "a substrate for hosting spirit"                 → junkawasaki.com essay (depends on prior "spirit is information" work)
```

Concrete launch artifacts were drafted (README/landing hero rewrite, a 5-minute
agent-memory demo, a Show HN post, and a Bluesky thread "T" built off the
spirit essay).

## Decision

**Do not launch publicly in June. June is a stabilization gate.** Driving HN /
Bluesky / IPFS-community traffic onto an unstable service is a one-shot,
unrecoverable bad first impression. Public spread (the Bluesky thread "T" and
the rest of the go-to-market motion) is **deferred to July or later**, gated on
the three surfaces being stably up.

June scope: make **kotoba**, **kotobase.net**, and **etzhayyim.com** stable and
reliably running. Stabilization — uptime, health/restart behavior, cold-tier
durability, the canonical clone/install path — takes priority over any
spreading work this month.

Also recorded: the canonical source repository is
`github.com/com-junkawasaki/kotoba` (origin), superseding stale `etzhayyim/…`
references that remain in `README.md` (clone URL line ~41; brew tap line ~21).
Those should be reconciled as part of the stabilization pass.

## Consequences

- The go-to-market artifacts (hero rewrite, demo, Show HN, Bluesky thread "T")
  are **parked, not discarded** — they are ready to fire once the gate is met.
- The launch trigger is operational, not calendar: the three surfaces stably up
  (and the README clone/install path pointing at the canonical repo) is the
  precondition for re-opening the July spread plan.
- Keep the spirit/organism framing **out of the entry surface** (kotobase.net,
  Show HN) and reachable only in the depth layer — unchanged by this ADR, but
  reaffirmed as a launch invariant.

## Follow-ups

- [ ] Stabilize kotoba / kotobase.net / etzhayyim.com (uptime, health, restart,
      cold-tier) — June.
- [ ] Reconcile stale `etzhayyim/…` repo references in `README.md` to
      `com-junkawasaki/kotoba`.
- [ ] Re-open the July go-to-market plan (thread "T" first) once the gate is met.
