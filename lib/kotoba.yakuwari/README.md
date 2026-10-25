# yakuwari (役割)

A durable organizational **role**: objective, scope, capacity bounds, runner
pool, and human-in-the-loop policy.

```
src/yakuwari/spec.cljk       the role definition and its validation
src/yakuwari/policy.cljk     which capability needs which human
src/yakuwari/reconcile.cljk  desired capacity → spawn / cancel / reap
```

## Where it sits

```
ao        self-evolves + self-judges   → holds git write authority, needs a lease
yakuwari  self-judges                  → no lease
agent     neither                      → bounded by the request it arrives with
```

Residency is **orthogonal**. All three can be resident on murakumo; being
resident changes latency and cost, never authority. A warm agent is still an
agent.

## Why a role needs no lifespan

A yakuwari decides *what to do* but cannot rewrite *what it is*. That single
asymmetry is the whole reason it needs no lease: a human who reviewed this
spec once stays correct, because the thing they approved cannot change
underneath them.

Only the AO above it — which does rewrite its own definition and can push to
its own repository — has nothing fixed above it, and so needs a bound that
survives self-modification. A temporal one is the only kind there is.

## Why not `actor`

The word is already taken three times over:

1. the Hewitt concurrency primitive — `kotoba-lang/actor-ipc`, whose own
   README says it is "specifically an Actor model";
2. the wasmCloud-style deployment unit on murakumo;
3. this — a durable organizational role.

Three collisions is not a naming preference. `yakuwari` names the third one
without borrowing the other two.

The same reasoning rules out Actor-Network Theory as a reference: ANT is a
sociology of translation, not an engineering model, and "a network of
yakuwari" should not borrow its authority. **System of systems** does apply
— but to the *fleet* of AOs, which satisfies Maier's operational and
managerial independence, emergent behaviour and evolutionary development.
Never to one role.

## Identity is responsibility

`issue-scout`, `independent-reviewer`, `panel-steward`. **Never** a runner
name: `codex`, `claude` and `grok` are execution attributes, and collapsing
them into role identity is exactly what tamaki ADR-0001 was written to stop.

## The decisions worth knowing

**Validation reports every problem at once.** One error per round trip turns
a ten-field spec into a ten-step form.

**A role with no runner is refused at definition time.** It is a role nobody
can fill; better to say so than to discover it at reconcile.

**An unlisted capability is `:blocked`.** Permission must not arrive by
omission. Unparseable decisions fail closed the same way.

**Two spellings of a policy, both honoured, strictest winning.** A flat
`:yakuwari/policy` `{cap decision}` map is what the policy functions want, but
a reviewer needs the *reason* a grant exists — so a role file may instead
author `:yakuwari/capabilities`, a vector of `{:capability :decision :note}`
that keeps the justification next to the grant. `spec/effective-policy` joins
them; on overlap `policy/strictest-of` decides, so a careless second entry
cannot widen a reviewed grant.

Nothing joined them until 2026-07-30, and the consequence was a reviewed
policy with no effect: `person-awai-ryo` declared `:mail.inbound :autonomous`
and `decide` answered `:blocked` for every capability it had, because an
absent `:yakuwari/policy` is a valid empty map and validation had no reason to
complain. It failed closed, so nothing was over-permitted — but the file a
human approved was not the file the model read. That repo's README already
printed the correct table; only the code disagreed.

**Validation reads the raw policy, `decide` reads the normalized one.**
Checking the normalized policy would defeat the check — `normalize-decision`
maps an unknown value to `:blocked`, so a role whose author typed
`:autonomus` would report a clean bill of health.

**Running work is never cancelled to shed capacity.** Only `:queued` and
`:held` runs are eligible — cancelling a running execution discards work
already paid for.

**Held runs raise capacity.** A role whose workers are all waiting on a human
is making no progress; refusing to add capacity there lets the backlog and
the HIL queue starve each other.

**A stale lease is reaped, not counted.** A run nobody is executing still
holds a slot, and leaving it there starves the role it was meant to fill.

## Legacy spellings

`yakuwari.policy` accepts `:self-executing` / `:propose` / `:forbidden` and
maps them onto `:autonomous` / `:approval-required` / `:blocked`.
`deprecated-spellings` reports them, because a fleet that never reports them
keeps two vocabularies alive forever.

## Test

```sh
npm test          # nbb / JS host
kbb -M:test   # JVM host — must agree exactly
```

24 tests, 61 assertions, both hosts.

## Status

Extracted 2026-07-29 from `kotoba.tamaki.actor`. Tamaki adopts this repository
through a compatibility adapter: persisted `:actor/*` and
`:agent.run/actor` attributes stay stable while validation, runner-pool
expansion, HIL vocabulary, and desired-state reconciliation are defined here.
Host-specific topology prompts, visibility checks, and AgentRun construction
remain Tamaki orchestration concerns.
