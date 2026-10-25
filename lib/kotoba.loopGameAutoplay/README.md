# loop-game-autoplay

**Evolve a policy that plays a real game, then qualify the champion on a real
booted iPhone Simulator and record the frames.**

The game is not modified. Not forked, not instrumented, not reimplemented —
the driver is *injected* into the shipped page, reads the state the game
already keeps, and writes the key map the game already polls.

```bash
# 1. train (headless Chromium, seconds per generation)
kbb --backend sci --classpath src:../shinka/src -m loop-game-autoplay.train \
    --game ../../cloud-itonami/gameka/playtest/survivors-zombie.html \
    --generations 12 --population 24 --episode-ms 60000 --seeds 3

# 2. qualify the champion on the phone, and record it
xcrun simctl boot "iPhone 17"
kbb --backend sci --classpath src:../shinka/src:../hinshitsu/src -m loop-game-autoplay.qualify \
    --champion target/run-champion.edn --seed 1
```

## The split that makes this work

| | where | why |
|---|---|---|
| **search** | headless Chromium, simulated time | 24 genomes × 3 seeds × 60 s = 216,000 physics steps per generation. A phone renders every frame at real-time speed and cannot be told not to. |
| **qualification** | booted iOS Simulator, real time, recorded | real WebKit, real device envelope, real frames — the thing you can watch and publish |

Both load the **same URL from the same server with the same driver**. If they
did not, the thing qualified on the phone would not be the thing trained.

## What was missing, and what each gap cost

[ADR-2608081500](https://github.com/com-junkawasaki/root) inventoried this
path and found four planes already present and five things absent. This repo
closes three of them and states plainly which two it did not.

| gap | closed how |
|---|---|
| **input injection** — no Appium / WebDriverAgent / XCUITest anywhere in the workspace, and `simctl` has no `tap` | ✅ not needed. The agent channel is *in the page*: the driver writes `keys`, which is exactly what a keyboard would have done. |
| **video recording** — nothing called `simctl io recordVideo` | ✅ `qualify` records the run and gates on the file actually having bytes |
| **crossover** — no GA; both existing searchers are mutation-only | ✅ [`kotoba-lang/shinka`](https://github.com/kotoba-lang/shinka), written for this |
| **screen → observation** | ⛔ **not closed, and deliberately.** The observation is 12 numbers read from game state, not pixels. A pixel observation would make the policy depend on resolution, theme and device scale — and this policy has to run on a phone screen after training on a desktop viewport. |
| **live streaming** | ⛔ **not closed.** `haishin` publishes a *finished* artefact to YouTube/TikTok/X; there is no RTMP/WHIP path in this workspace. `qualify` produces an mp4, which is what `haishin` accepts. |

## Who owns what

The repository rules say a `loop-` orchestrator must not own domain scoring
truth. It does not:

- **what a policy is** — `a = W·obs + b` — is
  [`shugyo.policy`](https://github.com/kotoba-lang/com-nvidia-isaac-lab)
  (formerly `kami-shugyo`). `test/gen_parity_cases.cljk` calls `act-batch` as
  the oracle.
- **how a population moves** is [`shinka`](https://github.com/kotoba-lang/shinka).
- **what counts as evidence** is
  [`hinshitsu.core`](https://github.com/kotoba-lang/hinshitsu) — `evidence` and
  `gate`, same schema as the iOS visual-QA CLI.
- **what an observation means** is the only domain truth here, because it is a
  property of *this game*, not of policies in general.

## The driver is JavaScript, and that is checked rather than trusted

`resources/autoplay-driver.js` is plain browser JavaScript in a workspace
whose rule is "no new `.mjs`/`.cjs`, write nbb". That rule governs Node
scripts. This file is neither: it must run inside a page with no build step,
and **the same bytes must be served to Safari on the Simulator**, where there
is no ClojureScript toolchain and no remote-eval channel.

The dangerous part to duplicate — what a policy *is* — is not trusted:

```bash
./bin/parity
```

Stage 1 (JVM) has `shugyo.policy/act-batch` compute the expected actions for
200 random policies drawn from `shinka.rng`. Stage 2 (nbb) replays them
against the real driver in a real browser and requires agreement to **1e-12**.
It also pins `OBS_DIM`/`ACT_DIM`, which live in two files and would otherwise
drift silently — the driver would read past the end of a short weight vector,
return `NaN`, and the search would spend a day optimising noise.

Two stages because the oracle cannot run where the browser can:
`shugyo.policy` needs `goog.math.Long`, which nbb does not have.

There is a second, narrower check for the **device code path** — the one the
Simulator uses, which broke once by being handed a flat genome where the driver
wanted `{w,b}`:

```bash
kbb --backend sci --classpath src:../shinka/src verify_play.cljk
```

It loads the same `?mode=play&genome=…` URL headless for 45 s and asserts the
**player displaced** (4120 px when wired correctly, 0 px when not). Displacement
is the assertion that matches that bug; reaching a given level is a property of
the champion, not of the wiring.

## Fitness

```
survivedMs/1000 + 2*level + (won ? 300 : 0)
```

Survival is the objective. The level term rewards actually engaging rather
than running in circles; the win bonus is large enough that surviving to the
end always beats any amount of levelling that did not. Each genome is scored
as the **mean over several fixed seeds** — with one seed a generation's
ranking is mostly a ranking of luck.

## What one real run looked like

`evidence/` holds a complete run from 2026-08-08, including the receipt from a
booted iPhone 17 (iOS 18.7, Safari 26.5):

```
passed  played  survived 900.0s, level 3, won
        recorded 318,505,871 bytes / 904.7 s / 35,719 frames
```

`evidence/README.md` reads the training history honestly and is worth reading
before trusting the search: **the best genome was already present in generation
0**, so that run demonstrates the harness, not that the search beats random
sampling.

## Layout

```
resources/autoplay-driver.js   the agent channel — injected, never merged into the game
src/…/policy.cljc              genome <-> {:w :b}, the search space. zero deps.
src/…/oracle                   (none — the oracle is shugyo.policy, called by the gate)
src/…/server.cljs              serves the unmodified page + driver; receives the phone's report
src/…/env.cljs                 one episode = one CDP round trip
src/…/train.cljs               shinka ask → evaluate → tell
src/…/qualify.cljs             simctl boot/openurl/recordVideo/screenshot → hinshitsu receipt
test/gen_parity_cases.cljk      stage 1 of the parity gate (JVM oracle)
test/policy_parity_test.cljk   stage 2 (real browser)
verify_play.cljk               the device code path, headless, in 45 seconds
evidence/                      one real run: champion, history, receipt, frames
```

## Requirements

- **nbb**, and **clojure** for the parity gate's JVM stage
- **playwright** with Chromium (`npx playwright install chromium-headless-shell`)
- **Xcode** command-line tools for `simctl`, and **ImageMagick** for the
  blank-screen check
- sibling checkouts of `shinka`, `com-nvidia-isaac-lab` and `hinshitsu` — this
  repo is a west project and reaches them by relative path

## License

Apache License 2.0.
