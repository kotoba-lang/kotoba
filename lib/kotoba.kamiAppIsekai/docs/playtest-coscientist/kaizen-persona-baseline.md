# Playtest Co-Scientist — iteration 01 (スライムハント / Slime Hunt)

> Driver: scripts/playtest/driver.mjs (real headless-Chromium playthrough, kotoba-lang/webgpu PR #9's `chromium.executablePath()` technique) · Scorer: kami-app-isekai.playtest.vision-score (3 candidate round(s) + 1 baseline round) · Judge: kotoba-lang/qa-governor (rubric + governor + append-only ledger) · following the ai-gftd-animeka coscientist pattern (generate -> score -> keep-winner) and isekai.ux.coscientist's propose/evaluate/iterate CLI shape.

Generated 2026-07-09T10:43:26.054298Z by `scripts/playtest_coscientist.cljk`.

Scoring backend: **murakumo vision critic** (api.murakumo.cloud / qwen3.6-35b-a3b — confirmed vision-capable as of 2026-07-09, sent the actual screenshot as an image content block, with pixel-stats + captured game state as fallback-only text if the vision reply failed to parse; see `kami-app-isekai.playtest.vision-score/murakumo-critique`)

## ★ Measured baseline

- total=20.4 grade=d verdict=approved
- scores: juice=9.6, feel=18.8, bugs=20.4, clarity=34.8
- driver: victory phase=victory, lose phase=gameover

## Roadmap (rounds tried)

| round | total | grade | verdict | scores | victory | lose |
|---|---|---|---|---|---|---|
| gen-1 | 29.5 | d | approved | juice=6.2, feel=21.4, bugs=40.6, clarity=53.0 | victory | gameover |
| gen-2 | 21.5 | d | approved | juice=10.6, feel=20.4, bugs=21.2, clarity=35.8 | victory | gameover |
| gen-3 | 22.3 | d | approved | juice=8.2, feel=19.6, bugs=23.8, clarity=40.0 | victory | gameover |

## Params tried per round

### gen-1

```
fx shake amp: 13 -> 19
fx shake frames: 13 -> 12
fx burst pick n: 11 -> 8
fx burst pick spd: 1.6408090591640627 -> 1.324831730662356
fx burst pick grav: 0.12435160151651226 -> 0.03811360906384248
fx burst pick life: 25 -> 34
fx burst pick size: 5 -> 2
fx burst hit n: 6 -> 9
fx burst hit spd: 3.1124458378259967 -> 3.02484556923652
fx burst hit grav: 0.1505988454605255 -> 0.21081763132030173
fx burst hit life: 14 -> 25
fx burst hit size: 7 -> 5
audio pick freq: 669 -> 789
audio pick dur: 0.05 -> 0.15665043681076563
audio pick gain: 0.17587883824968834 -> 0.09334149011971146
audio hit freq: 538 -> 671
audio hit dur: 0.3976241986318142 -> 0.38782170577214753
audio hit gain: 0.1427837408936326 -> 0.09697110771519954
audio victory freq: 538 -> 915
audio victory dur: 0.6583787256902423 -> 0.6706546417180242
audio victory gain: 0.1450890239667152 -> 0.23972834270668725
audio gameover freq: 80 -> 297
audio gameover dur: 0.46850303705715374 -> 0.5889209901801354
audio gameover gain: 0.10441160186022216 -> 0.0774003690624869
```

### gen-2

```
fx shake amp: 13 -> 12
fx shake frames: 13 -> 14
fx burst pick n: 11 -> 5
fx burst pick spd: 1.6408090591640627 -> 2.2453664488391327
fx burst pick grav: 0.12435160151651226 -> 0.16085422244893208
fx burst pick life: 25 -> 27
fx burst pick size: 5 -> 3
fx burst hit n: 6 -> 8
fx burst hit spd: 3.1124458378259967 -> 3.53686841070566
fx burst hit grav: 0.1505988454605255 -> 0.0627866362003065
fx burst hit life: 14 -> 8
fx burst hit size: 7 -> 10
audio pick freq: 669 -> 190
audio pick gain: 0.17587883824968834 -> 0.1337755504944249
audio hit freq: 538 -> 959
audio hit dur: 0.3976241986318142 -> 0.595598739818127
audio hit gain: 0.1427837408936326 -> 0.25112252598771895
audio victory freq: 538 -> 211
audio victory dur: 0.6583787256902423 -> 0.424154065971044
audio victory gain: 0.1450890239667152 -> 0.0961234361648364
audio gameover dur: 0.46850303705715374 -> 0.6231611009810223
audio gameover gain: 0.10441160186022216 -> 0.21186726576360443
```

### gen-3

```
fx shake amp: 13 -> 11
fx burst pick n: 11 -> 6
fx burst pick spd: 1.6408090591640627 -> 1.8659797240099014
fx burst pick grav: 0.12435160151651226 -> 0.10408380131955337
fx burst pick life: 25 -> 26
fx burst pick size: 5 -> 8
fx burst hit n: 6 -> 3
fx burst hit spd: 3.1124458378259967 -> 2.0140899699842967
fx burst hit grav: 0.1505988454605255 -> 0.13912923434027186
fx burst hit life: 14 -> 22
fx burst hit size: 7 -> 8
audio pick freq: 669 -> 800
audio pick dur: 0.05 -> 0.12978621072702692
audio pick gain: 0.17587883824968834 -> 0.11724802486358266
audio hit freq: 538 -> 657
audio hit dur: 0.3976241986318142 -> 0.6342254591104819
audio hit gain: 0.1427837408936326 -> 0.07406470265441098
audio victory freq: 538 -> 554
audio victory dur: 0.6583787256902423 -> 0.7097945965217227
audio victory gain: 0.1450890239667152 -> 0.05074346880699053
audio gameover dur: 0.46850303705715374 -> 0.6553572648121919
audio gameover gain: 0.10441160186022216 -> 0.06384635664744864
```

## ✅ Verdict — BUILD gen-1

**gen-1** beat the baseline (20.4 -> 29.5, +9.1) and was governor-approved — `scene.edn` was left set to this candidate's params.

## Screenshots (not published — local-only PNGs, see --out-dir)

- baseline: title, pickup, victory, hit, gameover
- gen-1: title, pickup, victory, hit, gameover
- gen-2: title, pickup, victory, hit, gameover
- gen-3: title, pickup, victory, hit, gameover

## → Seed for next iteration

This pass only tunes :fx/:audio params (kami-app-isekai.playtest.tuning/tunable-paths) — logic.cljc gameplay speeds/ranges/layout are explicitly out of scope (documented follow-up, not built now). A follow-up iteration could: (1) extend tunable-paths to :render/sky or particle :colors as a small categorical choice set (deliberately excluded from this pass's numeric random-walk, see tuning.cljc), (2) raise --rounds once round latency is validated in CI, (3) wire the live Claude vision path into a scheduled run once ANTHROPIC_API_KEY is available in that environment.
