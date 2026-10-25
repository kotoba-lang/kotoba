# Playtest Co-Scientist — iteration 01 (スライムハント / Slime Hunt)

> Driver: scripts/playtest/driver.mjs (real headless-Chromium playthrough, kotoba-lang/webgpu PR #9's `chromium.executablePath()` technique) · Scorer: kami-app-isekai.playtest.vision-score (3 candidate round(s) + 1 baseline round) · Judge: kotoba-lang/qa-governor (rubric + governor + append-only ledger) · following the ai-gftd-animeka coscientist pattern (generate -> score -> keep-winner) and isekai.ux.coscientist's propose/evaluate/iterate CLI shape.

Generated 2026-07-09T09:14:58.096814Z by `scripts/playtest_coscientist.cljk`.

Scoring backend: **murakumo vision critic** (api.murakumo.cloud / qwen3.6-35b-a3b — confirmed vision-capable as of 2026-07-09, sent the actual screenshot as an image content block, with pixel-stats + captured game state as fallback-only text if the vision reply failed to parse; see `kami-app-isekai.playtest.vision-score/murakumo-critique`)

## ★ Measured baseline

- total=54.6 grade=c verdict=approved
- scores: juice=34.0, feel=62.0, bugs=52.0, clarity=76.0
- driver: victory phase=victory, lose phase=gameover

## Roadmap (rounds tried)

| round | total | grade | verdict | scores | victory | lose |
|---|---|---|---|---|---|---|
| gen-1 | 57.9 | c | rejected | juice=33.6, feel=63.0, bugs=77.0, clarity=64.0 | victory | gameover |
| gen-2 | 66.6 | c | rejected | juice=49.0, feel=72.0, bugs=81.0, clarity=69.0 | victory | gameover |
| gen-3 | 56.5 | c | approved | juice=32.4, feel=61.2, bugs=71.6, clarity=66.6 | victory | gameover |

## Params tried per round

### gen-1

```
fx shake amp: 14 -> 7
fx shake frames: 12 -> 16
fx burst pick n: 10 -> 5
fx burst pick spd: 2.0 -> 2.30731638642447
fx burst pick grav: 0.1 -> 0.15336729459979795
fx burst pick life: 22 -> 26
fx burst pick size: 5 -> 6
fx burst hit n: 14 -> 17
fx burst hit spd: 2.6 -> 2.4369080162390633
fx burst hit grav: 0.16 -> 0.25444427148139936
fx burst hit life: 24 -> 33
fx burst hit size: 6 -> 4
audio pick freq: 660 -> 483
audio pick dur: 0.11 -> 0.05403345052526696
audio pick gain: 0.15 -> 0.06720019420797604
audio hit freq: 200 -> 217
audio hit dur: 0.17 -> 0.05
audio hit gain: 0.22 -> 0.10914716873727018
audio victory freq: 523 -> 480
audio victory dur: 0.5 -> 0.29055327259753533
audio victory gain: 0.18 -> 0.16463086431626703
audio gameover freq: 220 -> 523
audio gameover dur: 0.55 -> 0.5845905542469229
audio gameover gain: 0.16 -> 0.23240638333622102
```

### gen-2

```
fx shake amp: 14 -> 12
fx shake frames: 12 -> 15
fx burst pick n: 10 -> 5
fx burst pick spd: 2.0 -> 3.134568724293148
fx burst pick grav: 0.1 -> 0.07297593635320024
fx burst pick life: 22 -> 34
fx burst pick size: 5 -> 3
fx burst hit n: 14 -> 20
fx burst hit spd: 2.6 -> 1.9631721948531957
fx burst hit grav: 0.16 -> 0.1539668156122916
fx burst hit life: 24 -> 21
fx burst hit size: 6 -> 8
audio pick freq: 660 -> 261
audio pick dur: 0.11 -> 0.2894945822844442
audio pick gain: 0.15 -> 0.05
audio hit freq: 200 -> 80
audio hit dur: 0.17 -> 0.2118353000572486
audio hit gain: 0.22 -> 0.31915102551414704
audio victory freq: 523 -> 867
audio victory dur: 0.5 -> 0.34507544625013686
audio victory gain: 0.18 -> 0.10361304101696624
audio gameover freq: 220 -> 412
audio gameover dur: 0.55 -> 0.32653226685235537
audio gameover gain: 0.16 -> 0.20114855044413607
```

### gen-3

```
fx shake amp: 14 -> 13
fx shake frames: 12 -> 13
fx burst pick n: 10 -> 11
fx burst pick spd: 2.0 -> 1.6408090591640627
fx burst pick grav: 0.1 -> 0.12435160151651226
fx burst pick life: 22 -> 25
fx burst hit n: 14 -> 6
fx burst hit spd: 2.6 -> 3.1124458378259967
fx burst hit grav: 0.16 -> 0.1505988454605255
fx burst hit life: 24 -> 14
fx burst hit size: 6 -> 7
audio pick freq: 660 -> 669
audio pick dur: 0.11 -> 0.05
audio pick gain: 0.15 -> 0.17587883824968834
audio hit freq: 200 -> 538
audio hit dur: 0.17 -> 0.3976241986318142
audio hit gain: 0.22 -> 0.1427837408936326
audio victory freq: 523 -> 538
audio victory dur: 0.5 -> 0.6583787256902423
audio victory gain: 0.18 -> 0.1450890239667152
audio gameover freq: 220 -> 80
audio gameover dur: 0.55 -> 0.46850303705715374
audio gameover gain: 0.16 -> 0.10441160186022216
```

## ✅ Verdict — BUILD gen-3

**gen-3** beat the baseline (54.6 -> 56.5, +1.9) and was governor-approved — `scene.edn` was left set to this candidate's params.

## Screenshots (not published — local-only PNGs, see --out-dir)

- baseline: title, pickup, victory, hit, gameover
- gen-1: title, pickup, victory, hit, gameover
- gen-2: title, pickup, victory, hit, gameover
- gen-3: title, pickup, victory, hit, gameover

## → Seed for next iteration

This pass only tunes :fx/:audio params (kami-app-isekai.playtest.tuning/tunable-paths) — logic.cljc gameplay speeds/ranges/layout are explicitly out of scope (documented follow-up, not built now). A follow-up iteration could: (1) extend tunable-paths to :render/sky or particle :colors as a small categorical choice set (deliberately excluded from this pass's numeric random-walk, see tuning.cljc), (2) raise --rounds once round latency is validated in CI, (3) wire the live Claude vision path into a scheduled run once ANTHROPIC_API_KEY is available in that environment.
