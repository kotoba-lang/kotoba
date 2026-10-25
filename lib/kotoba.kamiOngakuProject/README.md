# kami-ongaku-project

Portable `.cljc` DAW-session data model — the L3 SSoT of the `ongaku`
(music production) engine stack defined in
[ADR-2607121400](https://github.com/com-junkawasaki/root/blob/main/90-docs/adr/2607121400-kami-ongaku-eizo-commercial-grade-cljs-stack.md).
This is the layer that actually ties
[`kami-ongaku-notation`](https://github.com/kotoba-lang/kami-ongaku-notation)
(score IR) and
[`kami-ongaku-sequencer`](https://github.com/kotoba-lang/kami-ongaku-sequencer)
(MIDI-equivalent event IR) into one session, the way a Logic Pro/Cubase/
Ableton project file actually does — tracks, a real bus **graph** (buses
can feed other buses, not just a flat list), tick-placed clips, parameter
automation, and a tick-keyed tempo map.

## Model

- **Track** — `:midi` / `:audio` / `:notation`, with mute/solo/armed
  flags and an `:output-bus` reference.
- **Bus** — name, `:inputs` (a set of track-or-bus ids — a real signal
  graph), `:gain` (linear multiplier, default `1.0`), and an ordered
  `:plugin-chain` of opaque plugin-instance refs (bypass + wet/dry). The
  plugin *contract* itself is out of scope here — that's
  `kami-ongaku-plugin-host`, Wave 3 of the ADR. `:gain` is the bus's own
  render-time gain, applied to the SUM of its `:inputs` — see "Real
  bus-graph mixing proof" below for where that math actually gets exercised
  end to end.
- **Clip placement** — a `{:track-id :start-tick :length-ticks :content}`
  reference on the project's tick timeline (matching
  `kami-ongaku-sequencer`'s integer-tick convention, no floats). Content
  shape depends on the referenced track's type: a `kami.ongaku.sequencer`
  pattern for `:midi`, a `kami.ongaku.notation` part for `:notation`, an
  opaque `{:audio/uri ...}` ref for `:audio`.
- **Automation** — tick-keyed breakpoint lanes targeting a
  `(track-or-bus-id, param)` pair, with per-segment interpolation
  (`:linear`/`:hold`/`:curve`).
- **Tempo map** — a tick-keyed sequence of `{:bpm :time-sig}` points
  (tempo/time-signature can change mid-project, not just a single global
  BPM), mirroring what `kami-ongaku-sequencer`'s SMF meta events already
  capture.

## Validation

`validate-project` checks referential integrity across the whole graph,
not just per-record shape (the constructors only check their own record's
shape and return `nil` on invalid input, same convention as
`kami-ongaku-notation`):

- dangling `track/output-bus` / `bus/inputs` / automation-lane target
  references
- **bus-graph cycles** — a real DFS cycle detector over the `bus/inputs`
  edges, since a bus receiving (directly or transitively) from itself is
  a genuine signal-flow bug
- clip content shape vs. the referenced track's declared type
- tempo-map / automation-lane tick ordering

```clojure
(require '[kami.ongaku.project :as project])

(def proj
  (project/project
   {:tempo-map [(project/tempo-point {:tick 0 :bpm 120 :time-sig [4 4]})]
    :tracks [(project/track {:id "t1" :type :midi :name "Lead" :output-bus "b1"})]
    :buses [(project/bus {:id "b1" :name "Instruments"})]
    :clips [(project/clip-placement
             {:id "c1" :track-id "t1" :start-tick 0 :length-ticks 960
              :content {:name "verse" :length-ticks 960 :loop? false :events []}})]}))

(project/valid-project? proj)     ;=> true
(project/validate-project proj)   ;=> []
```

## Not in v0

- No audio rendering, no plugin execution as part of this repo's *public
  API* — `src/` remains a pure session/graph data model. (`:bus/gain` +
  the actual gain-scaled bus-graph summation math ARE now proven correct
  end-to-end by the real-browser E2E below, but that mixing function lives
  in the E2E proof harness, `test/e2e/`, not as a shipped `src/` render/mixer
  entrypoint — promoting it to `src/` is a follow-up, not done here.)
- Automation *targets* a param key (e.g. `:gain`); the automation-lane
  breakpoint-interpolation math itself is not applied by anything in this
  repo (constant per-bus `:gain`, not automation-driven, is what the E2E
  below exercises).
- `kami-ongaku-plugin-host` (Wave 3) owns the actual plugin contract;
  `:bus/plugin-chain` here only holds opaque instance refs.
- No `:audio` clip content validation beyond "has a URI" — decoding/probing
  audio files is out of scope for a pure data-model repo.

## Real bus-graph mixing proof (`test/e2e/`)

**This is a test/proof harness, not a claim that `src/` renders audio.**
`test/kami/ongaku/project_test.cljk` already unit-tests the track/bus/
clip-placement/automation/tempo-map constructors and `validate-project`
(referential integrity, bus-graph cycle detection, clip-content-vs-track-type
matching) exhaustively, using real `kami-ongaku-notation` and
`kami-ongaku-sequencer` content as clip content. This E2E closes the gap
that kind of test can't: it proves a real, `validate-project`-clean,
**two-track, three-bus** session actually renders to correct audio — real
per-track content from two different domains (a `kami-ongaku-notation`
phrase, a `kami-ongaku-sequencer` pattern), combined through *this repo's
own* bus graph, with *this repo's own* per-bus `:gain` correctly scaling
each bus's contribution to the mix — not just that each track plays back on
its own.

It builds on all four sibling proofs in the `ongaku` stack:
[`kotoba-lang/org-w3-webaudio`](https://github.com/kotoba-lang/org-w3-webaudio)'s
real-browser `AudioWorkletProcessor` recipe (commit
`e554d853d6403c35b1ffe1c4adb37d2a1d557451`, `:optimizations :advanced` +
`self-polyfill.js` inside `AudioWorkletGlobalScope`),
[`kotoba-lang/kami-ongaku-sequencer`](https://github.com/kotoba-lang/kami-ongaku-sequencer)'s
and
[`kotoba-lang/kami-ongaku-notation`](https://github.com/kotoba-lang/kami-ongaku-notation)'s
own real-browser phrase/pattern-to-playback proofs (commits
`17c0ec4607b121e71cc7f16fc66abb40e442f8b8` /
`0a61b700a331876c9693a022ad469c671b42f44e`, this repo's own `deps.edn` pins
bumped to match), and
[`kotoba-lang/audio`](https://github.com/kotoba-lang/audio)'s real
`audio.synth` oscillator + ADSR envelope for the actual DSP, since this repo
has none of its own.

### The session

`test/e2e/src/kami/ongaku/project/e2e/fixture.cljk` (shared, portable,
required unmodified by the worklet bundle, the main-driver bundle, AND the
offline nbb reference) builds this project using ONLY this repo's own
`track`/`bus`/`clip-placement`/`tempo-point`/`project` constructors:

| track | type | content | output bus |
|---|---|---|---|
| `t-notation` | `:notation` | a real `kami-ongaku-notation` part: one 4/4 measure at 120 BPM, C4 quarter (mf), E4 quarter (mf), G4 half (ff) — durations sum to exactly 1 whole note | `b-inst` |
| `t-midi` | `:midi` | a real `kami-ongaku-sequencer` pattern: 3 note events, quarter-note spacing, D4/F4/A4 (62/65/69), velocities 90/100/110 | `b-drums` |

| bus | inputs | gain |
|---|---|---|
| `b-inst` | `#{t-notation}` | `1.0` (fixed, both renders) |
| `b-drums` | `#{t-midi}` | **`0.5` or `1.0`, the ONE thing this E2E varies** |
| `b-master` | `#{b-inst b-drums}` | `1.0` |

The `t-midi` clip is placed (via its own real `:clip/start-tick`, 2400
ticks = one quarter-note gap after the `t-notation` clip's 1920-tick/
1-whole-note length) so the two tracks' audible content never overlaps in
time — a deliberate fixture design choice so that measuring amplitude/onset
on the MIXED master output is unambiguous about which track's bus contributed
it. This repo's own `validate-project` is run on the constructed project (at
both `:gain` values) and confirmed empty — no dangling refs, no bus-graph
cycles — both offline and live from inside the worklet (the session that
plays IS the one `validate-project` accepts, not a hand-waved shape).

### The proof

`test/e2e/src/kami/ongaku/project/e2e/worklet_dsp.cljk` (compiled into the
worklet bundle) builds the project, synthesizes both tracks' real audio
content independently via `audio.synth` (each domain's own pitch/duration/
dynamics-or-velocity → freq/samples/gain conversion, same formulas the
notation/sequencer E2Es use), then **mixes them through the project's own
bus graph** — `fixture/mix-master`, a pure function that recursively sums
each bus's `:inputs` (tracks and/or other buses) and scales by that bus's
own `:gain` — all inside a real `AudioWorkletProcessor`, producing ONE
continuous master-bus output buffer. `test/e2e/run_e2e.cljk` (nbb) then:

1. checks `validate-project` is empty for both `:gain` values (no browser);
2. synthesizes both tracks' content **once** (gain-independent) and mixes
   through the real bus graph **offline**, at both `drums-gain` values, then
   checks — with NO tolerance, exact floating-point scalar-multiply
   arithmetic — that the `b-drums` bus's own output equals the raw `t-midi`
   buffer exactly at gain `1.0` and exactly half of it at gain `0.5`, and
   that `b-inst`'s output is bit-identical across both renders (the bus-graph
   gain math itself, proven independent of any browser measurement);
3. diffs the captured (browser) master PCM against the offline reference,
   at both gains;
4. diffs the browser-computed per-track note schedule against the offline
   one, bit-for-bit (same role as every sibling repo's own plan cross-check);
5. **measures**, from the captured PCM, each note's onset sample position
   and frequency (small-window threshold search / interpolated positive-going
   zero-crossing timing over the steady-state envelope window — same
   technique every sibling E2E uses), for both tracks, at both gains;
6. **the key measurement**: each note's peak amplitude in its own
   `onset..onset+local-length` window of the captured master PCM, compared
   between the `drums-gain 0.5` and `drums-gain 1.0` renders.

Real measured result (Chromium, Playwright-bundled, 2026-07-13):

| track | bus | note | freq | onset diff (samples) | freq match |
|---|---|---|---|---|---|
| t-notation | b-inst (gain 1.0, fixed) | C4 quarter mf | 261.6256 Hz | 11 | exact |
| t-notation | b-inst (gain 1.0, fixed) | E4 quarter mf | 329.6276 Hz | 5 | exact |
| t-notation | b-inst (gain 1.0, fixed) | G4 half ff | 391.9954 Hz | 5 | exact |
| t-midi | b-drums (gain varies) | D4 vel 90 | 293.6648 Hz | 14 / 10 | exact |
| t-midi | b-drums (gain varies) | F4 vel 100 | 349.2282 Hz | 12 / 9 | exact |
| t-midi | b-drums (gain varies) | A4 vel 110 | 440.0000 Hz | 11 / 8 | exact |

(onset diff tolerance: 200 samples ≈ 4.2ms; all onset diffs above are
single/low-double digits.) **Peak amplitude, drums-gain 1.0 vs. 0.5, per
`t-midi` note: `2.0000x`, `2.0000x`, `2.0000x`** (expected ratio: exactly 2.0
— `1.0/0.5`). **Peak amplitude, same comparison, per `t-notation` note:
`1.0000x`, `1.0000x`, `1.0000x`** (expected: exactly 1.0 — `b-inst`'s gain
never changes, proving the gain change is scoped to the `b-drums` bus, not
a global scale). Captured-PCM max-abs-diff vs. the offline reference:
`5.79e-8` at both gains (the same `Float32Array`-vs-double rounding every
sibling E2E finds, tolerance `1e-6`). Browser plan == offline plan: exact
match, both tracks. `validate-project`: empty, both gains, offline and
browser. `PASS: true`.

This is the strongest proof level currently reachable for this repo: two
real tracks from two different upstream domains, combined through THIS
repo's own bus graph, with THIS repo's own per-bus gain correctly scaling
each bus's contribution — not merely rendering side by side — inside a real
`AudioWorkletProcessor`, in a real browser, cross-verified bit-for-bit
(and, for the gain math itself, bit-EXACTLY) against an independent (nbb)
execution of the identical `.cljc` source. What it does **not** prove:
automation-lane-driven (time-varying) gain (this E2E uses a constant
per-bus `:gain`, not automation playback), `:plugin-chain` processing
(opaque refs only, `kami-ongaku-plugin-host`'s job), `:audio`-type track
content, or more than a 2-level bus graph (b-inst/b-drums → b-master) — a
deeper graph is architecturally supported by `mix-master`'s recursion but
not exercised by this fixture.

Setup and run:

```bash
npm --prefix test/e2e install                    # Playwright
npx --prefix test/e2e playwright install chromium
bash scripts/build-e2e-bundles.sh                 # compiles kami.ongaku.project.e2e.{worklet-dsp,main-driver}
                                                   # -> test/e2e/page/{worklet-processor,main-driver-bundle}.js
                                                   # (JVM/Clojure CLI build step, not an app-runtime
                                                   # choice -- see scripts/build-e2e-bundles.sh)
AUDIO_SRC_PATH=/path/to/kotoba-lang/audio/src
WEBAUDIO_SRC_PATH=/path/to/kotoba-lang/org-w3-webaudio/src
NOTATION_SRC_PATH=/path/to/kotoba-lang/kami-ongaku-notation/src
SEQUENCER_SRC_PATH=/path/to/kotoba-lang/kami-ongaku-sequencer/src
kbb --backend sci -cp "src:test/e2e/src:$AUDIO_SRC_PATH:$WEBAUDIO_SRC_PATH:$NOTATION_SRC_PATH:$SEQUENCER_SRC_PATH" test/e2e/run_e2e.cljk
```

Exits 0 and prints the full report (validate-project check, offline
exact-gain-math check, PCM/plan cross-checks, per-note onset/frequency
measurements, and the drums-gain 0.5-vs-1.0 peak-ratio comparison) plus the
overall summary on pass; exits 1 on any real failure — no silent
degradation. The `:e2e` deps.edn alias takes `kotoba-lang/audio` and
`kotoba-lang/org-w3-webaudio` as real git dependencies (pinned by commit
SHA), on top of this repo's existing (now-bumped) pins on
`kami-ongaku-notation`/`kami-ongaku-sequencer`; `test/e2e/page/*-bundle.js`,
`test/e2e/page/worklet-processor.js`, and `test/e2e/node_modules/` are build
artifacts, gitignored.

## Test

```bash
kbb -M:test
kbb -M:lint
```
