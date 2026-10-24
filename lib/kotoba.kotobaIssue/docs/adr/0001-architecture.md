# ADR-0001 — kotoba-issue-clj architecture: a shared issue/PR gate for cloud-itonami and manimani

- Status: Accepted
- Date: 2026-07-06
- Context tags: agent-loop, approval-gate, cloud-itonami, manimani, portable-cljc
- Builds on: `cloud-itonami/src/cloud_itonami/{activity,approval}.cljc`,
  `local-manimani/src/manimani/{agent,ledger}.cljc`,
  `90-docs/adr/2606272330-cae-shared-libs-and-seeds.md` (split-by-responsibility precedent)

## Decision

Extract the propose→approve→execute→audit gate already implemented (and
already storage-agnostic) in `cloud-itonami` and the plan→act→observe agent-run
FSM already implemented (and already pure) in `manimani` into one shared
`.cljc` library, renamed to PR vocabulary: **issue → proposal → review →
merge → audit**. Both source modules were independently built to the same
shape (inject the store, keep transitions data, append an audit record on
every change) without ever being connected to each other or named this way —
this library is that connection made explicit and reusable.

## Why extract rather than build fresh

`cloud_itonami.approval/execute-approved!` and `manimani.agent/step` are
almost entirely mechanism, not business logic — the itonami-specific parts
are the `policies` table (which policy has which risk) and the `investigate`/
`reply_llm`/`arxiv_submit` plan-fn branches, both of which stay in the calling
app. Everything else (terminal-status guards, missing-handler failure,
audit-on-every-transition, the plan/act/observe/awaiting-approval/cancelled
phase shape) is identical in spirit between the two apps and was reimplemented
independently. Promoting it once removes that duplication and gives both apps
a `:request-changes` verdict and an explicit `merge!` step neither had before.

## Why two libraries, not one (`kotoba-issue-clj` + `kotoba-ledger-clj`)

`2606272330-cae-shared-libs-and-seeds.md` explicitly rejected a single
monolithic shared library across dissimilar consumers, in favor of
purpose-typed libraries with independent lifetimes. The gate (a state machine
over live entities) and the ledger (an append-only projection of the same
events for supervisors/CLIs/UIs to read) have different consumers and
different volatility — a UI can want ledger projections without ever calling
`merge!`. `kotoba-ledger-clj` shares this library's event vocabulary by
convention (same field names/shape) but has no code dependency on it, keeping
both packages independently zero-dep.

## Why namespace-parameterized, not a forced schema migration

`cloud-itonami`'s live schema (`:itonami.activity/*`, `:itonami.effect/*`,
`:itonami.decision/*`, `:itonami.audit/*`) is used throughout
`cloud_itonami.store`/`doctor.cljc`/tests. Migrating those attribute names to
match this library's own `:kotoba.issue.*` default vocabulary is not required
for correctness — the mechanism (propose/route/review/merge/audit) does not
care what an attribute is called. `cloud-itonami` therefore keeps its own
schema and adapts at the boundary (its `activity.cljc`/`approval.cljc` become
thin wrappers translating to/from this library's functions), while
`manimani` — which has no Datomic-style namespaced schema at all today — adopts
`:kotoba.issue.*` directly. `kotoba.issue.store`'s `IssueStore` protocol is
deliberately name-agnostic: `kind` is just a caller-chosen partition keyword,
so an adapter can map it onto whatever attribute namespace the host already
uses.

## Module boundaries

```
store   the IssueStore contract (get/put/list-entities, append-audit!) + mem-store default
gate    issue / proposal / review / audit constructors, propose!/review!/merge!/dry-run!
run     plan -> act -> observe -> {done|error|awaiting-approval|cancelled}, pure reducer
        + interpret-propose! (the one store-touching convenience fn, opt-in)
```

## Mapping from source apps

| kotoba-issue-clj | cloud-itonami | manimani |
|---|---|---|
| `gate/issue` | `activity.cljc` `activity` ctor | Inbox Queue item |
| `gate/proposal` | `activity.cljc` `effect` ctor | (new — manimani decisions had no separate proposal object) |
| `gate/propose!` | `agent.cljc`/`runtime.cljc` `propose-effect-tool` | `manimani.agent/plan`'s effect description |
| `gate/route`/`approval-required?` | `activity.cljc` `route-decision`/`approval-required?` | (new) |
| `gate/review!`/`approve!`/`reject!` | `approval.cljc` `set-effect-status!`/`approve!`/`reject!` | (new — manimani's `awaiting-approval` phase had no distinct review record) |
| `gate/request-changes!` | (new — itonami only had approve/reject) | `agent.cljc` `recommended-policy` re-routing (`observe`, lines 142-149) |
| `gate/merge!` | `approval.cljc` `execute-approved!` (renamed) | `processor.ts`/`runner.clj` `interpret` (previously ungated) |
| `gate/dry-run!` | `approval.cljc` `dry-run-pending!` | — |
| `run/new-run`/`plan`/`observe`/`step` | — (itonami uses a langgraph-clj ReAct agent instead) | `manimani.agent/new-run`/`plan`/`observe`/`step` |
| `run/resume-after-review`/`cancel` | — | `runner.clj` `--continue-session-edn`/`--run-cancel-edn` (CLI layer, not yet a pure fn there) |

## Consequences

- `cloud-itonami`'s `/effects`/`/effects/approve` API (previously unimplemented)
  and `manimani`'s per-decision gate (previously nonexistent — decisions
  executed immediately) can now be built on the same tested primitives instead
  of two more bespoke implementations.
- `:kotoba.issue.proposal/rationale` and `:request-changes` are genuinely new
  concepts neither app had; downstream UIs need a place to show/collect them.
- Scope explicitly excludes `manimani`'s TypeScript (`server/`) and Rust
  (`tauri/`, `mobile/`) implementations — `.cljc` cannot run there. Those
  surfaces can converge on the same *event schema* (field names) without
  sharing this library's code; manimani's own README already treats the
  babashka/`.cljc` path as canonical and TS as deprecated, so this is
  consistent with, not contrary to, that direction.
