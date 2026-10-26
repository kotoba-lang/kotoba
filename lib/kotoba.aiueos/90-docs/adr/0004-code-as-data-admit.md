# ADR-0004 — Code-as-data: the agent admission pipeline

- Status: accepted (Phase 2, in progress)
- Date: 2026-06-27

## Context

aiueos is meant to run **code an AI agent writes at runtime** — "code as data".
The unsafe pieces of that already exist: the safe-kotoba subset gate (ADR-0001),
the capability/policy reasoner, the runtime-enforced host ABI (ADR-0002), the
`:ai-generated` trust tier with its network/secrets/persist lockdown, and now
manifest authenticity (ADR-0003). What is missing is the **front door**: a single
operation an agent loop calls to *submit a component and get a structured
admit-or-reject verdict back*, with the one safety property that makes agent
codegen safe — **the agent cannot grant itself trust**.

Today `Broker::launch` runs a component, but it trusts the manifest's declared
`:aiueos/trust`. An agent emitting its own manifest could simply write
`:aiueos/trust :trusted` and escape the `:ai-generated` lockdown. That must be
impossible.

## Decision

Add `Broker::admit` — the code-as-data entry point. It is `launch` with two
changes:

1. **Forced trust floor.** The submitted manifest's trust is overridden to
   `:ai-generated` before verification, regardless of what it claims. Agent code
   can never confer trust on itself; the manifest's own trust claim is ignored.
2. **Structured verdict, not an error.** It returns an `AdmitOutcome` (admitted +
   result, or rejected + machine-readable reason) so an agent can *loop*:
   generate → admit → on reject, read the reason → regenerate.

```rust
pub struct AdmitOutcome {
    pub component: String,
    pub admitted: bool,
    pub result: Option<i64>,   // entry's return value when admitted
    pub reason: Option<String>,// why it was rejected (unsafe / denied / trap)
}

pub fn admit(&self, m: &Manifest, base: &Path, graph: &CapabilityGraph) -> AdmitOutcome;
```

### The trust floor composes with signing (ADR-0003)

The floor sets the *manifest-declared* trust to `:ai-generated`. A valid
signature can still **elevate** the component to `:verified` during verification —
because a human (or trusted signer) vouching for the bytes is a stronger statement
than the code's own claim. So:

- Unsigned agent code → `:ai-generated` (no network/secrets/persist), gated by the
  safe-subset checker and the capability reasoner. The common case.
- Signed agent code → elevated to `:verified` by the signature, not by the
  manifest's say-so. The floor stops *self*-escalation; signing allows
  *vouched* escalation. The two layers compose exactly as intended.

### Why a floor, not a hard `:ai-generated` lock

Forcing the floor (rather than rejecting any non-`:ai-generated` manifest) keeps a
single code path for "submitted code" whether or not it is later signed, and means
an agent's manifest can declare *capabilities and effects* freely — those are
still checked — while never declaring *trust*. Trust is the one field the
submitter does not control.

## Increments

1. **`admit` + `AdmitOutcome` + the trust floor** *(this increment)* — the
   pipeline and the self-escalation guard, with tests proving a manifest claiming
   `:trusted` with a `:network` effect is still rejected, and that a clean
   component is admitted with its result.
2. **`aiueos admit <manifest>`** CLI surface (human + `--edn`) returning the
   structured verdict — the shape an external agent process consumes.
3. **Reject-reason taxonomy** — stable machine-readable reason codes
   (`unsafe` / `unresolved-capability` / `forbidden-effect` / `trap` / ...) so an
   agent can branch on *why* without parsing prose, reusing the existing
   `ViolationKind` labels and `AiueosError` kinds.
4. **A worked agent-loop example** — a driver that submits successive
   (hand-stand-in for LLM-generated) components and shows admit/reject/iterate.

## Consequences

- The headline code-as-data guarantee — "an AI agent can write a component and the
  OS will run it *only* within a deny-by-default, least-trusted sandbox, and the
  agent cannot lift itself out of it" — becomes a single, tested call.
- `admit` is a thin, honest wrapper over the existing verify/safe/run pipeline; it
  adds no new trust in the TCB, only removes the submitter's ability to assert
  trust.
- The actual *agent* (the LLM that emits source) stays **outside** the library —
  aiueos provides the admission gate, not the model. The `--edn` verdict (and
  ADR-0003's authenticity field) are the contract an external agent loop speaks.
