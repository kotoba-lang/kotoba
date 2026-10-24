# kami-ongaku-sequencer

Portable `.cljc` MIDI-equivalent event/pattern/track data model — the L3
sequencing/piano-roll layer of the `ongaku` (music production) engine stack
defined in [ADR-2607121400](https://github.com/com-junkawasaki/root/blob/main/90-docs/adr/2607121400-kami-ongaku-eizo-commercial-grade-cljs-stack.md).

Note/CC/pitch-bend/aftertouch events live on an integer-tick timeline (fixed
PPQ, no floating-point beat math — same discipline real DAW/MIDI internals
use to avoid drift), grouped into loopable patterns/clips and placed on
tracks. Includes:

- `kami.ongaku.sequencer` — event/pattern/track IR, validation, `quantize-events`
  (partial-strength + swing), `apply-groove` (repeating per-slot
  timing/velocity offset templates, i.e. "groove quantize"), and
  `flatten-track` (clip-placed track → absolute-tick event stream).
- `kami.ongaku.sequencer.smf` — Standard MIDI File (SMF, `.mid`) Format 1
  encode/decode: VLQ delta-times, running status, note-on/off pairing,
  tempo/time-signature meta. Operates on plain int vectors (0-255), not
  platform byte types, so it has **zero** reader-conditional branches.

## Not in v0

- No audio rendering/playback — pure event/timing data model + SMF I/O.
- No plugin/instrument routing or mixing — that's `kami-ongaku-project`'s job.
- SMF export flattens clip structure into per-track absolute-tick streams;
  clip/loop boundaries do not survive a round-trip (matching real-world MIDI
  file semantics — SMF itself has no concept of DAW clips).
- Program-change and sysex events are safely skipped on import, not modeled.
- `.cljc` byte-level helpers in `smf.cljc` are written portably for `:cljs`
  but were only exercised under `:clj` (`kbb -M:test`) in this repo's own
  CI so far — no `:cljs` unit-test runner has been wired up yet (the
  real-browser E2E below now DOES exercise `sequencer.cljc`/`smf.cljc` under
  `:cljs`, compiled with `:optimizations :advanced`, but that's a one-off
  proof harness, not a `:cljs` CI test suite).

## Usage

```clojure
(require '[kami.ongaku.sequencer :as sq]
         '[kami.ongaku.sequencer.smf :as smf])

(def track
  {:name "piano" :channel 0
   :clips [{:start-tick 0
            :clip {:name "verse" :length-ticks 960 :loop? true
                   :events [{:type :note :pitch 60 :velocity 100 :tick 0 :duration-ticks 240 :channel 0}
                            {:type :note :pitch 64 :velocity 90 :tick 240 :duration-ticks 240 :channel 0}]}}]})

(def flat (sq/flatten-track track))
(def bytes (smf/export-smf {:ppq 480 :bpm 120 :time-signature [4 4] :tracks [flat]}))
(smf/import-smf bytes)
```

## Real-browser AudioWorklet SMF round-trip proof (`test/e2e/`)

**This is a test/proof harness, not a claim that this repo does audio
synthesis.** `test/kami/ongaku/sequencer_test.cljk` and
`test/kami/ongaku/sequencer/smf_test.cljk` already unit-test the event/
quantize/groove logic and the SMF codec exhaustively. This E2E closes the
one gap that kind of test can't: it proves this repo's real tick/pitch/
velocity event data, **after a genuine `export-smf` → `import-smf` round
trip through the real VLQ/running-status SMF codec** (not skipped, not a
reimplementation), correctly drives real audio TIMING and PITCH once
combined with real DSP — not just that the decoded event data looks right.

It builds directly on
[`kotoba-lang/org-w3-webaudio`](https://github.com/kotoba-lang/org-w3-webaudio)'s
own real-browser `AudioWorkletProcessor` proof (commit
`e554d853d6403c35b1ffe1c4adb37d2a1d557451`) and
[`kotoba-lang/kami-ongaku-sampler`](https://github.com/kotoba-lang/kami-ongaku-sampler)'s
own real-browser trigger proof — same `:optimizations :advanced` +
`self-polyfill.js` recipe (required inside `AudioWorkletGlobalScope`, see
org-w3-webaudio's README for the full root-cause derivation, not repeated
here), same `OfflineAudioContext` + `audioWorklet.addModule` binding layer
(`w3.webaudio`), same real headless Chromium via Playwright, and on
[`kotoba-lang/audio`](https://github.com/kotoba-lang/audio)'s real
`audio.synth` oscillator + ADSR envelope for the actual DSP, since this repo
has none of its own.

`test/e2e/src/kami/ongaku/sequencer/e2e/fixture.cljk` (shared, portable, required
unmodified by the worklet bundle, the main-driver bundle, AND the offline
nbb reference) defines the proof pattern: **5 real `kami.ongaku.sequencer`
note events**, quarter-note spacing (480 ticks at PPQ 480, i.e. one quarter
note per event) at 120 BPM, distinct MIDI pitches (60/64/67/72/76) and
distinct velocities (40/70/100/110/127):

| tick | pitch | velocity | expected freq (`440·2^((pitch-69)/12)`) | expected onset sample @ 48kHz |
|---|---|---|---|---|
| 0 | 60 (C4) | 40 | 261.6256 Hz | 0 |
| 480 | 64 (E4) | 70 | 329.6276 Hz | 24000 |
| 960 | 67 (G4) | 100 | 391.9954 Hz | 48000 |
| 1440 | 72 (C5) | 110 | 523.2511 Hz | 72000 |
| 1920 | 76 (E5) | 127 | 659.2551 Hz | 96000 |

`fixture.cljc` flattens this pattern's track (`kami.ongaku.sequencer/
flatten-track`), calls this repo's REAL `export-smf` to get real SMF Format
1 bytes, then calls this repo's REAL `import-smf` on those bytes to recover
the event stream — a genuine round trip through the VLQ delta-time codec and
running-status-aware parser, not skipped. It then converts the (recovered)
tick/pitch/velocity data to a render plan: tick → seconds (constant
120 BPM/480 PPQ tempo map) → sample position via `Math.round(seconds · sr)`,
and MIDI note → frequency via the standard equal-tempered formula. Velocity
→ gain (`velocity/127`) is this harness's own convention (the event schema
itself leaves gain to the consuming engine, same stance kami-ongaku-
sampler's own fixture takes for its `:pitch-offset` unit).

`test/e2e/src/kami/ongaku/sequencer/e2e/worklet_dsp.cljk` (compiled into the worklet
bundle) calls `fixture/render-plan` on the **post-round-trip** event data
— inside a real `AudioWorkletProcessor` — then synthesizes all 5 notes via
`audio.synth`'s real oscillator + ADSR and places each one at its own
onset-sample offset in **one continuous output buffer** (not 5 separate
renders — this is what actually exercises the tick→sample scheduling math,
not just per-note pitch). `test/e2e/run_e2e.cljk` (nbb) then requires the
*same* `fixture.cljc` and `audio.synth` sources directly — a different
runtime, no browser involved — and:

1. checks the real SMF round trip preserved every note's tick/pitch/
   velocity/duration-ticks/channel exactly (pre vs. post, byte codec in the
   middle);
2. diffs the browser-computed render plan (onset-sample/freq/gain per note)
   against its own offline computation, bit-for-bit;
3. diffs the render plan computed from the **pre**-round-trip data against
   the plan computed from the **post**-round-trip data, bit-for-bit — proof
   the SMF round trip changed nothing about the derived audio schedule;
4. diffs the captured PCM against an offline full multi-note-buffer render;
5. **actually measures**, from the captured PCM, each note's onset sample
   position (first sample whose absolute value crosses a small threshold,
   searched in a window around the tick-derived expected onset — not merely
   trusting the schedule was honored) and its frequency (interpolated
   positive-going zero-crossing timing over the steady-state envelope
   window, the same technique kami-ongaku-sampler's own E2E uses) — and
   compares both to the tick/pitch-derived expected values;
6. repeats step 5's measurement against the offline reference PCM computed
   from both the pre- and the post-round-trip event data, to show the
   before/after numbers match (they do — the round trip is bit-exact, so
   there is nothing for the SMF codec to have corrupted).

Real measured result (Chromium, Playwright-bundled, 2026-07-13):

| tick | pitch | expected onset | detected onset (browser PCM) | diff | expected freq | measured freq (browser PCM) |
|---|---|---|---|---|---|---|
| 0 | 60 | 0 | 16 | 16 | 261.6256 Hz | 261.6256 Hz |
| 480 | 64 | 24000 | 24011 | 11 | 329.6276 Hz | 329.6276 Hz |
| 960 | 67 | 48000 | 48008 | 8 | 391.9954 Hz | 391.9954 Hz |
| 1440 | 72 | 72000 | 72007 | 7 | 523.2511 Hz | 523.2511 Hz |
| 1920 | 76 | 96000 | 96006 | 6 | 659.2551 Hz | 659.2551 Hz |

(onset diff tolerance: 200 samples ≈ 4.2ms — generous vs. attack-ramp/
threshold-detection variance, but far tighter than the 24000-sample/0.5s
note spacing, so a wrong tick→sample conversion or wrong note ordering would
miss by thousands of samples, not single digits; all 5 diffs above are 6-16
samples, i.e. genuinely tight.) Captured-PCM max-abs-diff vs. the offline
reference: `2.98e-8` (the same `Float32Array`-vs-double rounding org-w3-
webaudio's and kami-ongaku-sampler's own E2Es found, not a correctness gap,
tolerance `1e-6`). Browser-computed plan == offline (nbb) plan: exact match,
all 5 notes. Offline plan from pre-round-trip data == offline plan from
post-round-trip data: exact match, all 5 notes (i.e. the SMF round trip is
provably a no-op on the derived audio schedule). Measuring the offline
reference PCM built from the *pre*-round-trip event data reproduces the
identical onset/frequency numbers as the table above, note for note.
`PASS: true`.

This is the strongest proof level currently reachable for this repo: real
tick/pitch/velocity event data, taken through this repo's own unmodified
`export-smf`/`import-smf` codec, driving real oscillator DSP at the correct
sample positions for multiple simultaneously-scheduled notes, inside a real
`AudioWorkletProcessor`, in a real browser — cross-verified bit-for-bit
against an independent (nbb) execution of the identical `.cljc` source, both
before and after the SMF round trip. What it does **not** prove: anything
about CC/pitch-bend/aftertouch playback (this harness only renders `:note`
events; those event types have no fixed real-DSP analogue to demonstrate),
quantize/groove timing under real audio (unit tested, not exercised here),
or tempo-change events (this fixture uses one constant tempo throughout).

Setup and run:

```bash
npm --prefix test/e2e install                    # Playwright
npx --prefix test/e2e playwright install chromium
bash scripts/build-e2e-bundles.sh                 # compiles kami.ongaku.sequencer.e2e.{worklet-dsp,main-driver}
                                                   # -> test/e2e/page/{worklet-processor,main-driver-bundle}.js
                                                   # (JVM/Clojure CLI build step, not an app-runtime
                                                   # choice -- see scripts/build-e2e-bundles.sh)
AUDIO_SRC_PATH=/path/to/kotoba-lang/audio/src
kbb --backend sci -cp "src:test/e2e/src:$AUDIO_SRC_PATH" test/e2e/run_e2e.cljk
```

Exits 0 and prints the full report (round-trip check, plan cross-checks,
per-note onset/frequency measurements against both the browser-captured and
offline-reference PCM, before and after the SMF round trip) plus the overall
summary on pass; exits 1 on any real failure (round-trip mismatch, plan
mismatch, PCM beyond tolerance, onset or frequency beyond tolerance) — no
silent degradation. The `:e2e` deps.edn alias takes `kotoba-lang/audio` and
`kotoba-lang/org-w3-webaudio` as real git dependencies (pinned by commit
SHA); `test/e2e/page/*-bundle.js`, `test/e2e/page/worklet-processor.js`, and
`test/e2e/node_modules/` are build artifacts, gitignored.

## Test

```bash
kbb -M:test
```
