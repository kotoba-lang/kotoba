# agent

One **bounded execution**. An agent is invoked with a request, does it, and
ends.

```
src/agent/run.cljk            AgentRun contract, state machine, event fold
src/agent/bounded_run.kotoba  the same lifecycle, as a sovereign kernel
src/agent/turn_loop.kotoba    the TURN loop inside a run: admission, budget,
                              exit reasons -- transcribed from the hermes agent
```

## The turn loop

`bounded_run` owns the run's lifecycle (queued → leased → running → …).
`turn_loop` owns what happens *inside* `running`: how many provider calls a
turn may make, what spends the iteration budget, and which of five reasons
ends it.

It is a transcription of the loop that actually drives this workspace's bot
fleet — `NousResearch/hermes-agent`, `agent/conversation_loop.py:2074..2115`
and the whole of `agent/iteration_budget.py` — as
`state + event -> next-state + one inert effect`. Provider calls, tool
execution and message building stay outside: those are sockets, SDKs and
credentials, which is mechanism, not product semantics.

```
kbb --backend sci scripts/verify-turn-loop-parity.cljk      # 0 parity holds, 1 disagrees, 2 could not measure
```

The gate compiles the module to **both** `js-browser` and `wasm32-browser`,
replays ten vectors through the js artifact, and asserts `main() = 42` on both.
The vectors come from `migration/hermes_turn_loop_oracle.py`, which *imports*
the upstream `IterationBudget` instead of reimplementing it, so half the
contract is the upstream's own code and the other half is what the gate checks.
When the upstream checkout is present the gate regenerates the vectors and
fails on drift.

Two facts the transcription surfaced that the Python prose did not:

- **`budget_exhausted` is unreachable single-threaded.** The `while` condition
  tests `remaining > 0` before the body, so `consume()` can only fail if
  another thread took the last iteration. The branch is kept because upstream
  is thread-safe; no vector reaches it, and that is a fact about the schedule
  rather than a missing case.
- **A grace call raises the call count past `max_iterations` without spending
  budget.** Measured: `max=1 budget=9`, tick/grace/tick/tick ends at
  `api_call_count=2`, `budget_used=1`, `max_iterations_reached`.

## Where it sits

```
ao        self-evolves + self-judges   → holds git write authority, needs a lease
yakuwari  self-judges                  → no lease
agent     neither                      → bounded by the request it arrives with
```

An agent does not decide *what* to do — a yakuwari or an operator already
did. Its bound therefore arrives with the invocation instead of having to be
imposed on it, which is why this layer needs no lease and no policy of its
own: goal, budget and capabilities are all fixed before it starts.

Residency is **orthogonal**. An agent kept warm on murakumo is still an
agent; it just does not pay cold start. Being resident changes latency and
cost, never authority.

## Naming

tamaki ADR-0001 calls this an **AgentRun**, not an "Agent", precisely because
"agent" is the most overloaded word in the field. The namespace keeps the
precise name (`agent.run`, `:agent.run/*`) even though the repository uses
the short one.

## The decisions worth knowing

**Refusal is a dead end.** `:rejected` and `:cancelled` have no outgoing
transitions. `:failed` can be requeued because a failure is often retryable,
but re-deriving a run from a human's *no* would launder the refusal.

**Illegal transitions throw.** A run whose history no longer explains its
state is worse than a crash.

**A run needs a stated goal.** Without one it cannot be reviewed, cannot be
judged done, and cannot be explained to the person it acted for.

**Budgets are merged, not replaced.** A caller overriding `:max-turns` keeps
every other ceiling. A run without a ceiling is an unbounded spend against
someone's money and someone's patience.

**Non-run events never materialise as runs.** Loop, role and audit events
share the durable stream; folding must skip them rather than create nil
entries.

## Test

```sh
npm test          # nbb / JS host; 10 tests, 34 assertions in this checkout
```

`kbb -M:test` uses the engine configured for this workspace; here it selected
the nbb test substitution and also ran 10 tests, 34 assertions. A direct
`clj -M:test` currently discovers zero tests because the source test namespace
is `.cljk`; its zero-test exit is not a JVM verification result.

## Agent and LLM coding evaluation

The repository includes a project-scoped Kotoba coding skill for Codex and
trusted Hermes project sessions, plus a versioned two-stage agent coding pilot
that scores exact Kotoba behavior, elapsed time, provider-reported tokens, and
session continuity. See [`eval/v1/README.md`](eval/v1/README.md).

## Kotoba source authority

`src/agent/bounded_run.kotoba` owns the deterministic AgentRun lifecycle:
creation, legal transitions, attempts, and active/terminal/resumable queries.
It is zero-capability and targets restricted browser JS and typed browser Wasm.
Identity, clock, persistence, scheduling, and execution stay outside this pure
kernel and enter through `kotoba-lang` providers. The retained CLJC/event-fold
boundary is recorded in `migration/bounded-run-v1.edn`.

## Status

Split out of `kotoba-lang/ao` on 2026-07-29, where it had been placed by
mistake: `ao` briefly held all three layers before the axes were separated.
Originally from `kotoba.tamaki.model`. Tamaki now adopts this repository
through a compatibility adapter and supplies its persisted
`:tamaki.event/*` attribute map to `agent.run/event-keys`; existing event
stores therefore require no migration.
