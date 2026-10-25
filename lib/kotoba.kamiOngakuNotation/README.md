# kami-ongaku-notation

**Portable notation/score data model — the missing "what does a written
piece of music look like" layer for kotoba-lang's `ongaku` (music
production) domain.** An L3-authoring
[kotoba-lang](https://github.com/kotoba-lang) capability library per
[ADR-2607121400](https://github.com/com-junkawasaki/root/blob/main/90-docs/adr/2607121400-kami-ongaku-eizo-commercial-grade-cljs-stack.md),
analogous to what Sibelius/Dorico/MuseScore's internal score model does:
part → measure → note/chord/rest, with pitch, exact-rational duration
(no floats), time/key signature, tempo, dynamics and articulation — plus
MusicXML-subset import/export so the IR can round-trip through the
notation-software ecosystem.

Portable `.cljc` across JVM / ClojureScript, zero external dependencies
(including its own minimal XML reader/writer — no platform XML library).

**Why a hand-rolled rational type** (`kami.ongaku.notation.rational`):
ClojureScript's number tower is IEEE-754 doubles only — `(/ 1 4)` is exact
`1/4` on the JVM but `0.25` under cljs. A "no floats" duration model that
relies on native `/`/ratio literals is therefore only exact on one of the
two target platforms. Every duration/time-signature computation here goes
through `kami.ongaku.notation.rational`'s `{:rational/num :rational/den}`
records instead, so exactness holds on both.

## Scope (v0)

This is a data model + structural validator + MusicXML I/O, not a
notation *application*:

- **In scope**: pitch (MIDI ⇄ scientific pitch notation ⇄ step/alter/
  octave), exact-rational duration (base type + dots, ties), dynamics
  (ppp–fff with a velocity mapping), articulation marks, chords, multiple
  voices, time/key signature, tempo, per-measure/per-voice duration-sum
  validation, MusicXML 4.0 partwise import/export for the subset above.
- **Not in scope**: visual layout/engraving (beaming, stem direction, page
  layout), playback/audio rendering (that's `kotoba-lang/audio`'s L2
  concern per the ADR), arbitrary third-party MusicXML conformance beyond
  the subset this library itself emits, triplets/irregular tuplets,
  cross-staff notation, guitar tab, percussion clefs.

## Contract

```clojure
(require '[kami.ongaku.notation :as notation]
         '[kami.ongaku.notation.pitch :as pitch]
         '[kami.ongaku.notation.validate :as validate]
         '[kami.ongaku.notation.musicxml :as musicxml])

;; pitch: MIDI <-> scientific pitch notation <-> step/alter/octave
(pitch/pitch {:step :C :alter 1 :octave 4})        ;=> {:pitch/step :C :pitch/alter 1 :pitch/octave 4}
(pitch/pitch->midi *1)                             ;=> 61
(pitch/scientific->pitch "C#4")                    ;=> same record
(pitch/pitch->scientific *1)                       ;=> "C#4"

;; note: pitches is a vector of 1+ pitches (a chord), or empty/nil for a rest
(notation/note {:pitches [{:step :C :octave 4}] :type :quarter
                :dynamic :mf :articulations #{:staccato}})
(notation/note {:type :eighth})                    ;=> a rest

;; measure -> part -> score, each returning nil on structurally invalid input
(def m (notation/measure {:number 1 :time-sig {:beats 4 :beat-type 4}
                           :key-sig {:fifths 0} :notes [...]}))
(def score (notation/score {:parts [(notation/part {:id "P1" :name "Piano" :measures [m]})]}))

;; validate: does each voice in each measure actually sum to the time
;; signature's capacity? (carries the signature forward across measures
;; that don't restate one, per MusicXML semantics)
(validate/validate-part (first (:score/parts score)))

;; MusicXML 4.0 partwise I/O
(musicxml/score->musicxml score)                   ;=> XML string
(musicxml/musicxml->score xml-string)               ;=> score IR
```

## Naming note

`kami-ongaku-*` mirrors the `kami-engine-*`/`kami-mangaka-*` family naming
convention for domain-authority repos (ADR-2607121400 §2.1); `ongaku`
(音楽) is the music-production domain, parallel to `eizo` (映像) for video.
This library models the score itself — it is not `kotoba-lang/composer`
(the outer AI-composition request/track contract mirroring
`ai.gftd.ongakuka.*`) or `kotoba-lang/ongaku` (BGM catalog + license
gating). No network, no I/O beyond pure string parsing/emission, no model
call.

## Real-browser AudioWorklet phrase proof (`test/e2e/`)

**This is a test/proof harness, not a claim that this repo does audio
synthesis.** `test/kami/ongaku/notation*_test.cljc` already unit-tests the
pitch/duration/dynamics/MusicXML logic exhaustively in isolation. This E2E
closes the one gap that kind of test can't: it proves this repo's real
score/notation data — pitch, exact-rational duration, dynamics — **after a
genuine MusicXML export/import round trip through this repo's own
`kami.ongaku.notation.musicxml`** — actually drives correct **real** audio
output once combined with real DSP, not just that the data looks right on
paper.

It builds directly on
[`kotoba-lang/org-w3-webaudio`](https://github.com/kotoba-lang/org-w3-webaudio)'s
own real-browser `AudioWorkletProcessor` proof (commit `e554d853d640`) and
[`kotoba-lang/kami-ongaku-sampler`](https://github.com/kotoba-lang/kami-ongaku-sampler)'s
own real-browser trigger proof — same `:optimizations :advanced` +
`self-polyfill.js` recipe (required inside `AudioWorkletGlobalScope`, see
org-w3-webaudio's README for the full root-cause derivation, not repeated
here), same `OfflineAudioContext` + `audioWorklet.addModule` binding layer
(`w3.webaudio`), same real headless Chromium via Playwright, same
interpolated-zero-crossing frequency-measurement technique — and on
[`kotoba-lang/audio`](https://github.com/kotoba-lang/audio)'s real
`audio.synth` oscillator + ADSR envelope for the actual DSP, since this
repo has none of its own.

Unlike kami-ongaku-sampler's E2E (one `OfflineAudioContext` render per
trigger input), this renders a WHOLE phrase — 4 notes — into **one
continuous buffer, each note at its own sequential onset**, in a single
`AudioWorkletProcessor` pass, because the property under test is "does the
notation data drive one continuous sequential phrase," not 4 independent
notes.

### The phrase (`test/e2e/src/kami/ongaku/notation/e2e/fixture.cljk`)

One 4/4 measure at 120 BPM, built entirely with this repo's own
`notation/note` — 4 distinct pitches, 3 distinct duration values, dynamics
spanning `pp`..`ff` (durations sum to exactly 1 whole note, so
`validate/validate-part` reports the measure clean, not just "4 notes in a
list"):

| note | pitch | duration | dynamic | MIDI (`pitch/pitch->midi`) |
|---|---|---|---|---|
| 1 | C4 | quarter (1/4) | pp | 60 |
| 2 | E4 | eighth (1/8) | mf | 64 |
| 3 | G4 | eighth (1/8) | mf | 67 |
| 4 | C5 | half (1/2) | ff | 72 |

Conversions, using ONLY this repo's own functions plus the standard
formulas the proof cross-checks:

- **pitch → frequency**: standard equal-temperament, `440 * 2^((midi-69)/12)`,
  `midi` from this repo's own `pitch/pitch->midi` (cross-checked directly
  against `pitch.cljc`: A4 → 69, C4 → 60 — `(* 12 (inc octave))` `+`
  step-semitone `+` alter).
- **duration → exact sample count**: this repo's own `notation/duration-value`
  (an exact `kami.ongaku.notation.rational` fraction of a whole note),
  converted to samples via rational arithmetic ONLY — `duration-value * 4
  [quarters/whole] * rational(60/BPM) [seconds/quarter] * rational(SR)
  [samples/second]` — `rational/->int` is the only place a native integer
  is ever extracted (the exact reason `kami.ongaku.notation.rational`
  exists at all, per that ns's own docstring: this fixture is where that
  exactness gets used for something audible). At 120 BPM / 48 kHz, every
  note in this phrase lands on an exact integer sample count with zero
  rounding: quarter → 24000, eighth → 12000, half → 48000 samples.
- **dynamics → gain**: this repo's own `notation/dynamic->velocity`
  (`pp` → 33, `mf` → 80, `ff` → 112 of 127), linearly scaled to `[0,1]` by
  `/127.0` (the standard MIDI-velocity-to-linear-gain convention).

### What the harness does

1. Builds the score, checks `validate/validate-part` reports it valid.
2. Round-trips it through this repo's REAL `musicxml/score->musicxml` →
   `musicxml/musicxml->score` and asserts the result is structurally
   identical to the original score (`=`) — a genuine XML-codec exercise,
   not skipped.
3. Computes freq/gain/onset/duration-samples from BOTH the pre-round-trip
   notes and the post-round-trip notes and asserts they're identical —
   proving the round trip didn't corrupt the data that drives audio.
4. Computes an offline reference PCM buffer directly from
   `kotoba-lang/audio`'s `audio.synth` — same DSP, no browser, no worklet
   — as ground truth.
5. Compiles+runs a real headless Chromium (Playwright) rendering the WHOLE
   phrase in ONE `OfflineAudioContext` / `AudioWorkletProcessor` pass, and
   captures the actual PCM.
6. Diffs captured vs. offline-reference PCM over the WHOLE buffer (the
   strongest, least-forgeable signal — any wrong onset/frequency/gain
   anywhere shows up as a large diff somewhere).
7. For each note, **measures** (from the captured PCM, not merely
   asserting the inputs were correct): actual onset sample position (first
   sample, scanning forward from the note's expected onset, crossing 5% of
   that note's own expected gain — normalized per-note so louder notes
   aren't measured with a laxer effective threshold); actual frequency via
   interpolated positive-going zero-crossing timing over the note's
   steady-state window; peak `|amplitude|` in that window (to show
   numerically that `ff` is louder than `pp`, not merely that a gain
   number was computed).

### Real measured result (Chromium, Playwright-bundled, 2026-07-13)

```
phrase measure-valid? (durations sum to 4/4 capacity): true
MusicXML round trip: score -> musicxml -> score identical to original? true
MusicXML round trip: notes vector identical to original? true
playback params (freq/gain/onset/dur-samples) IDENTICAL before vs. after round trip? true
```

| note | expected onset | measured onset | expected freq | measured freq | expected gain | measured peak |
|---|---|---|---|---|---|---|
| C4 quarter pp | 0 | 20 (Δ20, tol 30) | 261.6256 Hz | 261.6256 Hz | 0.259843 | 0.259843 |
| E4 eighth mf | 24000 | 24018 (Δ18, tol 30) | 329.6276 Hz | 329.6276 Hz | 0.629921 | 0.629921 |
| G4 eighth mf | 36000 | 36017 (Δ17, tol 30) | 391.9954 Hz | 391.9954 Hz | 0.629921 | 0.629921 |
| C5 half ff | 48000 | 48015 (Δ15, tol 30) | 523.2511 Hz | 523.2511 Hz | 0.881890 | 0.881890 |

- Every measured onset lands 15–20 samples after the exact rational-derived
  onset — expected, since the ADSR attack ramps from 0 and the 5%-of-gain
  threshold is crossed partway up that ramp, not at sample 0 itself; all
  four are comfortably inside the 30-sample (0.3–0.4 ms) tolerance.
- Every measured frequency matches the equal-temperament-derived expected
  frequency to 4 decimal places, both `pp`/`mf`/`ff` (dynamics don't shift
  pitch, as expected) and across all 4 distinct pitches.
- **`ff` measured peak (0.881890) is 3.394× `pp` measured peak (0.259843)**
  — the same ratio as their expected gains (0.881890/0.259843 = 3.394),
  proving dynamics measurably affects real rendered output, not merely
  that a gain number was computed and never used.
- Whole-buffer captured-vs-offline-reference max-abs-diff: `2.98e-8`
  (tolerance `1e-6`) — the same order of magnitude as the
  `Float32Array`-vs-double rounding org-w3-webaudio's own E2E found, not a
  correctness gap.
- `PASS: true`.

**A real bug was found and fixed while building this proof** (documented
in `test/e2e/src/kami/ongaku/notation/e2e/worklet_dsp.cljk`): `kotoba-lang/audio`'s
`audio.synth/adsr` takes its `:attack`/`:decay`/`:release` keys in
**seconds** (it converts to samples internally) — only `:gate-off` is a
sample index. An earlier version of this harness pre-converted
attack/decay/release to samples before calling `adsr`, double-converting
them (samples treated as seconds → multiplied by the sample rate again),
which put every note in an effectively-infinite attack ramp — captured
peak amplitudes were ~1000x quieter than the reference at every sample,
while the zero-crossing frequency measurement still (correctly) passed,
since phase timing is unaffected by a wrong envelope scale. Caught by
comparing measured peak amplitude against the expected gain (not just
diffing PCM against an equally-buggy-if-copied reference) and confirmed to
reproduce identically calling `render-phrase` directly via `nbb` outside
any browser — i.e. a real DSP-usage bug in this E2E's own harness code,
not a browser/Closure artifact.

This is the strongest proof level currently reachable for this repo: real
pitch/duration/dynamics data, produced by this repo's own unmodified
`notation`/`musicxml` code (through a genuine MusicXML round trip), driving
real oscillator+ADSR DSP, inside a real `AudioWorkletProcessor`, in a real
browser, as one continuous sequential phrase — cross-verified against an
independent (nbb) execution of the identical `.cljc` fixture source. What
it does **not** prove: visual layout/engraving (still explicitly out of
scope, per Scope above), arbitrary third-party MusicXML conformance beyond
this repo's own emitted subset, or anything about triplets/tuplets (not
modeled by this repo at all).

Setup and run:

```bash
npm --prefix test/e2e install                    # Playwright
npx --prefix test/e2e playwright install chromium
bash scripts/build-e2e-bundles.sh                 # compiles kami.ongaku.notation.e2e.{worklet-dsp,main-driver}
                                                   # -> test/e2e/page/{worklet-processor,main-driver-bundle}.js
                                                   # (JVM/Clojure CLI build step, not an app-runtime
                                                   # choice -- see scripts/build-e2e-bundles.sh)
AUDIO_SRC_PATH=/path/to/kotoba-lang/audio/src
kbb --backend sci -cp "src:test/e2e/src:$AUDIO_SRC_PATH" test/e2e/run_e2e.cljk
```

Exits 0 and prints the full fixture-side checks (measure validity, round
trip, param preservation) plus the per-note report (expected/measured
onset, frequency, peak amplitude) and overall summary on pass; exits 1 on
any real failure (round trip mismatch, PCM beyond tolerance, onset/
frequency/dynamics check failing) — no silent degradation. The `:e2e`
deps.edn alias takes `kotoba-lang/audio` and `kotoba-lang/org-w3-webaudio`
as real git dependencies (pinned by commit SHA); `test/e2e/page/*-bundle.js`,
`test/e2e/page/worklet-processor.js`, and `test/e2e/node_modules/` are
build artifacts, gitignored.

## Test

```
kbb -M:test
```

## License

Apache-2.0
