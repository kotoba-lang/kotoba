# ADR-0001 — kotoba-procedure-clj architecture: a multi-step external procedure tracker

- Status: Accepted
- Date: 2026-07-06
- Context tags: procedure, deadline, turn-taking, portable-cljc
- Builds on: `kotoba-lang/kotoba-issue-clj` (IssueStore's 4-fn contract
  shape, reused here as IProcedureStore; the `store`+`gate` module split)

## Decision

Track "procedures" -- external, multi-step processes with a deadline and a
whose-turn-is-it state (KYC resubmission, corporate account setup, contract
renewal) -- as their own state machine in a new library, rather than
folding them into `kotoba-issue-clj`'s gate.

## Why a new library rather than extending kotoba-issue-clj

`kotoba-issue-clj`'s gate models one shape: propose → approve/reject/
request-changes → merge, a single action reviewed once. A procedure is a
different shape entirely: several ordered steps, each one owned by whoever
moves it next (`:self`/`:counterparty`/`:agent`), no single "reviewer"
verdict, and a deadline the whole thing can expire past without anyone
approving or rejecting anything. Forcing a procedure through `propose!`/
`review!`/`merge!` would mean modeling each step as its own proposal with a
fake auto-approval, losing the actual "whose turn, how much time is left"
questions callers need answered. `90-docs/adr/2606272330-cae-shared-libs-and-seeds.md`
already rejected exactly this kind of grab-bag consolidation once (for the
cae-libs case); the same reasoning applies here.

## Module boundaries

```
store  IProcedureStore(get/put/list-entities, append-audit!) + mem-store default
gate   procedure/step constructors, open!/advance-step!/block!/cancel!/expire!/note!,
       pure predicates expired?/next-action (no store access -- callers can ask
       "what's next" without a round-trip)
```

## Design notes

- **`kind` is name-agnostic** (a caller-chosen partition keyword like
  `:wise/corporate-account-setup`), same policy as `IssueStore` -- a caller
  with an existing schema adapts at the boundary instead of migrating.
- **Deadlines are just `compare`-able values**, not a forced date/time type
  -- an ISO-8601 UTC string (sorts correctly lexicographically) or epoch
  millis both work, so `.cljc` callers on either JVM or JS don't need a
  shared date library dependency.
- **Partial progress doesn't auto-clear `:blocked`.** `advance-step!` only
  forces the procedure's own state to `:done` when every step is done;
  otherwise the procedure's state (including `:blocked`) is left alone even
  as individual steps complete. Blocking and step completion are
  orthogonal signals -- a step can land while the procedure is still
  waiting on something else.

## Relationship to kotoba-ledger-clj

Same call as `kotoba-issue-clj`/`kotoba-ledger-clj`: this library's audit
event shape (`:id`/`:type`/`:at`/`:procedure`/`:source-event`) is
convention-compatible with `kotoba-ledger-clj`'s JSONL projection, but there
is no code dependency -- a UI wanting ledger projections shouldn't need to
depend on the state-machine package, and vice versa.

## Consequences

- `kotoba-lang/com-gmail` (Gmail steps: "reply to this thread", "wait for
  the counterparty's Gmail reply") and `kotoba-lang/com-wise` (steps whose
  real-world state a caller wants to double check against the Wise API
  before advancing them) can both drive/observe a procedure's steps without
  either depending on this library's code -- the same "shared vocabulary,
  no shared code" relationship this org already uses between
  `kotoba-issue-clj` and `kotoba-ledger-clj`.
- Adding a `:review` concept to procedures later (e.g. someone signs off
  before a step counts as done) is possible without breaking existing
  callers -- `advance-step!` and `next-action` don't assume no review step
  exists, they just don't require one today.
