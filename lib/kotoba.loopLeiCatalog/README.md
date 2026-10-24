# loop-lei-catalog

Continuous orchestrator for the **cloud-itonami-lei** corporate catalog:
`observe → evaluate → decide → act → record-evidence`.

## Role boundary

A `loop-*` repo under `kotoba-lang`'s repository-role taxonomy. It runs cycles
and **does not own domain scoring truth** — the rubric lives in
[`catalog-maturity`](https://github.com/kotoba-lang/catalog-maturity) and is
tested there. This repo observes real state, asks that library what is weakest,
runs a bounded amount of work, and writes down what actually happened.

## Run

    LEI_LOOP_ROOT=<superproject root> kbb --backend sci bin/run.cljk [--dry-run] [--contact-limit N]

A dry run still observes live and still writes a ledger entry — labelled
`:event/dry-run true`. It is not omitted: the ledger is a record of every time
this loop ran, including the times it was only being checked.

## Schedule

`deploy/` holds the runner. It is one file, checked out, not a copy under
`~/.gftd` — two copies of a scheduler drift, and the one that drifts is always
the one actually firing.

    cp deploy/com.kotoba-lang.lei-catalog-tick.plist ~/Library/LaunchAgents/
    launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.kotoba-lang.lei-catalog-tick.plist
    launchctl kickstart gui/$(id -u)/com.kotoba-lang.lei-catalog-tick   # run one now

Every 6h, bounded to 40 contact fetches per cycle. The runner syncs this repo to
`origin/main` *before* the cycle and commits + pushes the appended ledger line
after — a cycle whose evidence never leaves the machine cannot be told apart
from one that never ran. If a previous push was rejected the next tick reports
it and skips, rather than resolving an append-only conflict on its own.

Log: `~/.gftd/lei-catalog-tick.stdout.log`. Each firing is also a `tamaki`
AgentRun (`:mode :external`) with the real argv and exit code.

## Design decisions that are easy to get wrong

**Observation is live, never carried over.** An unreachable database fails the
cycle rather than producing a plan from stale numbers — a plan built on last
week's coverage looks identical to one built on today's.

**The after-score is measured, not predicted.** The cycle observes a second time
after acting. What a script reports and what actually landed have already
diverged once in this project's history: a `transact` returned `ok` for rows
that never became readable, and only a separate completeness check caught it.

**One bounded step per cycle.** A cycle that tried to close the whole gap would
run for hours and its ledger entry could not say which change moved which
number.

**Actions shell out to the existing scripts.** `scripts/lei-acquire.cljs`,
`scripts/lei-contact-discover.cljs` and `scripts/d1-ingest-cloud-itonami-lei.cljs`
are the tested path; they already refuse to fabricate data or bypass bot checks.
Reimplementing them inside a scheduler is how two implementations start to drift.

**An action with no runner is reported, not ranked into the plan.** Ranking
something the loop cannot execute produces a plan that looks like progress and
never moves.

## Evidence

`ledger/lei-catalog-ledger.edn` — append-only, one EDN map per line, recording
the measured **before and after** of every cycle. A score with nothing to
compare against cannot show whether the cycle helped, and a cycle that made
things worse must be as visible as one that helped.
