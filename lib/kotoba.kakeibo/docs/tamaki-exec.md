# Running an ingest as a tamaki exec tick

`kotoba-lang/tamaki` gives every unit of work one durable identity, an
append-only event history and a lifecycle. A kakeibo ingest belongs under
`tamaki exec`, **not** `tamaki submit`:

- `submit` / `local` hands a goal to `kotoba-code`, i.e. to a model. Recording a
  data ingest that way would claim an agent did work it did not do.
- `exec` runs the caller's own argv in `--project`, records the same lifecycle
  every other run emits (`submitted -> leased -> started -> succeeded|failed`)
  carrying the real `:agent.run/command` and exit code, and its mode is
  `:external` — which `tamaki doctor` gates on the event store alone, so a
  deterministic tick needs neither `kotoba-code` nor a fleet node.

That fit is the reason `kakeibo.core/ingest` is pure and the CLI has a strict
exit-code contract: a receipt is only worth keeping if a failure cannot look
like a success.

## The invocation

```sh
cd orgs/kotoba-lang/tamaki

bin/tamaki exec "kakeibo ingest tick — statement window 2026-07" \
  --project /abs/path/to/orgs/kotoba-lang/kakeibo \
  -- kbb --backend sci --classpath "src:bin:resources:../banking/src" bin/kakeibo.cljk ingest \
     --mapping resources/mappings/jp-rakuten-bank.transaction-detail-ja.edn \
     --rules   resources/rules/example-categories.edn \
     --rows    data/2026-07.rows.edn \
     --existing out/ledgered.result.edn \
     --out     out/2026-07.result.edn
```

Everything after `--` is kakeibo's own argv. `--existing` accepts the previous
run's `--out` file directly, so a scheduled tick is idempotent: re-fetching an
overlapping window adds nothing and posts nothing.

## Verified behaviour

Measured 2026-07-26 against this repository, `tamaki` at `cfcacc4`:

| case | kakeibo exit | recorded run | `tamaki exec` exit |
|---|---|---|---|
| clean ingest (4 rows, 4 postings) | 0 | `:mode :external :status :succeeded :exit 0` | 0 |
| one unreadable date among the rows | 1 | `:mode :external :status :failed :exit 1` | 1 |

The receipt carries the full argv, so what ran is recoverable from the event
store rather than from a shell history. And because `exec`'s exit code is the
subprocess's, launchd or cron sees the truth without parsing output — which is
what makes a scheduled tick trustworthy.

## Scheduling

Schedule the `tamaki exec` line, not the bare CLI: the point is that every tick
lands in the same run tree as everything else tamaki runs, so a silently broken
ingest shows up in `tamaki status` instead of only in a log nobody reads.

Retrieval stays a separate, earlier step. `kotoba-lang/statement-fetch` drives a
browser to download the document and its authentication is a `:handoff` step
that compiles to no argv — a human authenticates, the agent never holds a
credential. Nothing in this repository or this tick has any access to one.
