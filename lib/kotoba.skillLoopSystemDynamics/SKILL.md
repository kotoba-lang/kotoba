---
name: loop-system-dynamics
description: Run kotoba-lang/loop-system-dynamics's observe-evaluate-decide-act-record-evidence cycle (Meadows leverage scoring, real XMILE stock-flow backlog simulation, DataScript/arrangement.datalog query, SysML v2 structural models) against real entity data, and read its findings. Use when asked to run a system-dynamics cycle, check a registration/growth backlog's real observed rate, query the loop's ingested facts, or when working inside kotoba-lang/loop-system-dynamics itself.
---

# loop-system-dynamics agent procedure

This is the agent-instruction package for
[`kotoba-lang/loop-system-dynamics`](https://github.com/kotoba-lang/loop-system-dynamics)
(role `:agent-instruction-package` per `kotoba-lang/loop-ux-kaizen`'s
`resources/repository-rules.edn` taxonomy). It teaches an agent HOW to run
that loop's real commands and interpret their real output. It does not
duplicate the loop's own domain logic (all backlog/rate/leverage scoring
truth lives in `loop-system-dynamics` and the `kotoba-lang/dynamics`
library it depends on) and it is never itself a running process — every
procedure below is a one-shot `nbb` invocation an agent runs on demand.

## Inputs this skill needs declared before running anything

1. A local checkout of `kotoba-lang/loop-system-dynamics` (west-managed:
   `orgs/kotoba-lang/loop-system-dynamics` in a `com-junkawasaki/root`
   checkout, or any plain clone).
2. Sibling checkouts on the classpath, depending on which cycle is being
   run — check the specific `bin/*.cljs` script's own header comment for
   the exact `--classpath` string, since different cycles need different
   subsets:
   - `kotoba-lang/dynamics` (Meadows leverage scoring — almost every cycle)
   - `kotoba-lang/org-oasis-open-xmile` + `kotoba-lang/dsl-core` (any
     `*_xmile.cljs` stock-flow simulation)
   - `kotoba-lang/org-omg-sysmlv2` (any `*_sysml.cljs` structural model)
   - `kotoba-lang/arrangement` + `kotoba-lang/prolly-tree` +
     `kotoba-lang/io-ipld` + `kotoba-lang/io-multiformats` +
     `kotoba-lang/org-ietf-cbor` (`arrangement_query.cljs` only)
3. `npm install` once inside `loop-system-dynamics` (pulls in `datascript`
   and `@noble/hashes`).
4. For any `refresh_from_github.cljs`/`refresh_and_run.cljs` cycle: network
   access (real `gh api`/GitHub REST calls) — optionally a `GITHUB_TOKEN`
   env var for a higher rate limit.

## Procedure

1. **Pick the right cycle for the question being asked**, don't default to
   the first one found — `loop-system-dynamics`'s own README enumerates
   every real entry point under headings like "Simulate it", "Query it",
   "Model it, one code at a time". Read that README section before running
   anything; the exact `--classpath` and default seed path for each command
   live there, not here (this skill does not re-describe them, per
   `repository-rules.edn`'s own `:must-not [:own-domain-scoring-truth]` for
   `loop-*` — a `skill-*` adapter must not fork a second copy of that either).
2. **Run the real cycle** with `kbb --backend sci --classpath "<the README's classpath
   for this command>" bin/<the README's script>.cljs [args]` from inside
   the `loop-system-dynamics` checkout root.
3. **Read the real output, don't paraphrase from memory**: every cycle
   prints where its report (`target/*.md`) and ledger append
   (`ledger/*.edn`) landed. Open the report for the human-readable finding;
   the ledger line is the append-only evidence record (never overwritten,
   never a source to hand-edit).
4. **Never fabricate a number a cycle didn't produce.** If a fact isn't in
   the seed a cycle reads, or a query returns empty, report "not measured"
   / "no result" — the same never-fabricate discipline `loop-system-
   dynamics` itself is built around (see its own FINDINGS.md, throughout).
5. **A cycle that finds something worth keeping permanently** (a real,
   durable observation, not a one-off run) gets folded back into the
   relevant `resources/*-seed.edn` by hand, with `:source` and `:as-of` —
   the loop's own "Extending coverage" README section describes exactly
   how. This skill does not automate that step; it stays a deliberate,
   reviewed edit every time.

## Outputs

- `target/<cycle>-report.md` — overwritten each run, the current
  human-readable finding.
- `ledger/<cycle>-ledger.edn` — append-only, one EDN map per line, one line
  per cycle run, never rewritten.
- Query-layer results (`query.cljs`/`arrangement_query.cljs`) are returned
  in-process to the caller, not written to disk — read them directly from
  the `kbb --backend sci -e`/`bin/*_demo.cljs` output.

## What this skill deliberately does NOT do

- Does not run on a schedule or own any CI/pass-fail state of its own —
  that is [`kotoba-lang/action-loop-system-dynamics`](https://github.com/kotoba-lang/action-loop-system-dynamics)'s
  job (`repository-rules.edn`'s `:must-not [:require-resident-runner
  :own-ci-state]` for `skill-*`).
- Does not re-derive or re-score anything `dynamics.core`/
  `fleet_registration_xmile.cljs`/`query.cljs` already compute — this
  package is instructions for invoking those, not a parallel
  implementation.
