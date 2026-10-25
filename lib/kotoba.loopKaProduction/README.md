# loop-ka-production

The nightly production loop for the `-ka` publishing channels — dougaka,
minidrama, dougaka-vector, yukkuri.

It exists because that loop had **no home**. Each channel carried its own copy
(`dougaka.outer-loop`, animeka's `production-loop.cljs`, a `produce-video.bb`),
and the thing they all skipped was checking whether the episode they had just
built actually contained anything. Sixty-second videos of flat pastel cards
posted to aozora.app every night for two weeks, and nothing between "it encoded"
and "it posted" asked.

Three layers, deliberately separate:

| layer | owns | where |
|---|---|---|
| **this repo** | cadence, admission, verdict, evidence | `kotoba-lang/loop-ka-production` |
| **resident execution** | placement, slots, load, retry | `kotoba-lang/murakumo` task plane |
| **human管理** | reading runs, approving publishes | `cloud-itonami/cloud-itonami-app` |

Production itself stays in the channel's own repo. This loop never renders,
never muxes, and **holds no publishing key** — each channel publishes under its
own actor DID. The loop decides whether to *ask*.

## The five verbs

`manifest/repository-rules.edn` (workspace authority, ADR-2607299000) defines
`loop-*` as `:must [:observe :evaluate :decide :act :record-evidence]`. One
namespace each:

```
loop-ka.observe    what is due this slot, and WHY each skip was skipped
loop-ka.evaluate   grade the producer's own :legs report
loop-ka.decide     publish | hold | discard
loop-ka.task       -> a task batch (data; nothing executes here)
loop-ka.ledger     one append-only record per run
```

All pure `.cljc`. `bin/loop.cljk` is the only IO.

## Use

```bash
# what would run tonight, and why the rest would not
kbb --backend sci --classpath src:resources bin/loop.cljk observe --workspace <dir>

# emit the batch for the fleet
nbb ... bin/loop.cljk plan --workspace <dir> --out tasks.edn
kbb --backend sci ../murakumo/scripts/run-task.cljk task run --tasks tasks.edn

# a producer reports what it actually did, and learns whether it may publish
nbb ... bin/loop.cljk record --channel dougaka --episode <id> --legs legs.edn --phase 1
#   exit 0 = publish   10 = hold   11 = discard

nbb ... bin/loop.cljk report --last 20
```

**The exit code is the contract.** A producer must not have to parse prose to
learn whether it may publish.

## Grades

Read from the producer's `:legs` — dougaka.pipeline emits one per run
(per-shot `:murakumo`/`:comfy`/`:placeholder` for the image,
`:murakumo`/`:local`/`:silent` for the voice, plus bed and cues).

| grade | meaning |
|---|---|
| `:clean` | every shot generated, narration present, bed present |
| `:thin` | nothing degraded, but the bed or cues are missing |
| `:degraded` | a shot fell back to a placeholder, or narration went silent |
| `:empty` | the producer reported no shots |

**`:degraded` never auto-publishes at any phase.** A flat-colour card is not a
release. Phases mirror the -ka actors' own rollout vocabulary: 0 draft = ledger
only, 1 unlisted, 2 public (needs `:publish` sign-off or the outer loop's
`:auto-publish` standing grant).

## Seeding

An empty ledger asserts "nothing was ever produced", which is false for a
channel already publishing. Measured: the first plan against the real workspace
selected `amaoto-no-arcade` and `alarm-ai` — **both already live**. Seed once
per channel before the first real tick:

```bash
nbb ... bin/loop.cljk seed --channel dougaka --episodes amaoto-no-arcade,asaichi-no-koori
```

A seed consumes the *episode* (so the catalog advances) but not a *slot* (so
tonight still runs).

## The ledger is the app's read surface

`state/runs.ledger.edn`, one EDN map per line, append-only — the same shape as
the workspace's other event ledgers. Append-only because a run is an event:
last night's degraded run is not superseded by tonight's clean one, both are
facts. `cloud-itonami-app` needs only this shape, not this code.

Records carry `:source/dataset "loop-ka-production"`, so they query alongside
the workspace's other datasets. **If these are to join with repo-maturity /
fleet / market-intel they must live on the SAME kotobase ref** — Datalog reaches
exactly one ref (AGENTS.md), and splitting for write throughput makes that join
impossible, permanently. Decide the ref before the first write, not after.

## Why not a Worker, and why not inside the app

The assembly leg is **ffmpeg** — concat, audio-overlay mix, segment. A
Cloudflare Worker has no subprocess and no ffmpeg, so the pipeline cannot live
there; a Worker is the right shape for the cadence tick and the ledger read
surface, and nothing else.

`cloud-itonami-app` is a local-first, explicitly tenant-neutral workspace app.
Nightly GPU production inside it would couple a user-facing desktop app to a
batch job, make it hold two production credentials, and stop when the laptop
closes.

## References

- ADR-2607299960 — murakumo compute / kotobase storage, and the flat-card incident
- ADR-2607299000 — repository-rules workspace authority (`loop-*` contract)
- ADR-2607162200 — the creator cadence tick this loop replaces per-channel copies of
