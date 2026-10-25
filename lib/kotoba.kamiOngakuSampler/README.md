# kami-ongaku-sampler

Sample zone/mapping, round-robin variation cycling, velocity-layer lookup,
and a streaming-lifecycle state machine for portable sample-playback
engines (the Kontakt-equivalent mapping model), per
[ADR-2607121400](https://github.com/com-junkawasaki/root/blob/main/90-docs/adr/2607121400-kami-ongaku-eizo-commercial-grade-cljs-stack.md).

Part of the `kotoba-lang` `ongaku` (music production) stack, alongside
[`kami-ongaku-notation`](https://github.com/kotoba-lang/kami-ongaku-notation),
[`kami-ongaku-sequencer`](https://github.com/kotoba-lang/kami-ongaku-sequencer),
and [`kami-ongaku-project`](https://github.com/kotoba-lang/kami-ongaku-project).

## Scope (v0)

- Zone/layer data model: key range x velocity range -> a round-robin group
  of sample variations, with per-layer pitch offset, gain, and pan.
- Deterministic round-robin cycling (trigger-count modulo group size, not
  `rand` — testable and reproducible).
- Velocity-layer + key-range lookup with correct inclusive-boundary
  handling.
- Overlap validation: a sample map with two layers overlapping in both key
  range and velocity range is rejected. Layers sharing a key range at
  disjoint velocity bands (the normal multi-velocity-layer case) are not
  an overlap.
- Streaming lifecycle state machine (`:unloaded`/`:loading`/`:ready`/
  `:streaming`/`:error`) with an explicit valid-transition table.

**Not in v0**: no audio decoding, no disk/network I/O, no playback. This is
purely the mapping/lookup data model and lifecycle state machine that a
real sampler engine would sit on top of.

## Usage

```clojure
(require '[kami.ongaku.sampler :as sampler])

(def layer
  (sampler/make-layer
   {:key-low 60 :key-high 60 :vel-low 64 :vel-high 127
    :variations [(sampler/make-variation :snare-hard-1)
                 (sampler/make-variation :snare-hard-2)]}))

(sampler/trigger-sample [layer] 60 100 0)
;; => {:sample-ref :snare-hard-1, :pitch-offset 0.0, :gain 1.0, :pan 0.0}
```

## Real-browser AudioWorklet trigger proof (`test/e2e/`)

**This is a test/proof harness, not a claim that this repo does audio
synthesis or sample-file decoding.** `test/kami/ongaku/sampler_test.cljk`
already unit-tests the trigger/lookup logic exhaustively against synthetic
sample-refs (keywords, never audio). This E2E closes the one gap that kind
of test can't: it proves `kami.ongaku.sampler/trigger-sample`'s
zone/velocity-layer/round-robin decisions actually drive correct **real**
audio output once combined with real DSP — not just that the decision data
looks right.

It builds directly on
[`kotoba-lang/org-w3-webaudio`](https://github.com/kotoba-lang/org-w3-webaudio)'s
own real-browser `AudioWorkletProcessor` proof (commit `e554d853d640`) —
same `:optimizations :advanced` + `self-polyfill.js` recipe (required
inside `AudioWorkletGlobalScope`, see that repo's README for the full
root-cause derivation, not repeated here), same `OfflineAudioContext` +
`audioWorklet.addModule` binding layer (`w3.webaudio`), same real headless
Chromium via Playwright — and on
[`kotoba-lang/audio`](https://github.com/kotoba-lang/audio)'s real
`audio.synth` oscillator + ADSR envelope for the actual DSP, since this
repo has none of its own.

Since real sample-file playback is out of scope here, `test/e2e/src/kami/ongaku/sampler/e2e/fixture.cljk`
substitutes a distinct real oscillator frequency for each sample-ref a real
engine would otherwise point at a decoded audio file — reusing this repo's
OWN `test/kami/ongaku/sampler_test.cljk` boundary values (60/61 key split,
63/64 velocity split, 1/127 range bounds), not new numbers invented for
this harness:

| zone | key | vel | variations (round-robin) | layer gain | pitch-offset |
|---|---|---|---|---|---|
| A (soft) | 60 | 1-63 | 440.0 Hz / 445.0 Hz (~1% detune, RR) | 0.7 (2nd variation ×0.95) | 0 |
| B (hard) | 60 | 64-127 | 220.0 Hz / 225.0 Hz (RR) | 1.0 (2nd variation ×0.9) | 0 |
| C (other-key) | 61 | 1-127 | 330.0 Hz (single, no RR) | 0.85 | +7 semitones |

(`:pitch-offset` is unitless in this repo's own contract; this harness
interprets it as semitones — the conventional unit — and converts via
`2^(semitones/12)`, purely a proof-harness choice, e.g. zone C's effective
frequency is `330.0 * 2^(7/12) ≈ 494.44 Hz`.)

For a sequence of 14 `(note, velocity, trigger-count)` inputs,
`test/e2e/src/kami/ongaku/sampler/e2e/worklet_dsp.cljk` (compiled into the worklet
bundle) calls `kami.ongaku.sampler.e2e.fixture/resolve-trigger` — which delegates
the actual decision entirely to this repo's real `kami.ongaku.sampler/trigger`
— **inside a real `AudioWorkletProcessor`**, then synthesizes the resolved
freq/gain via `audio.synth`'s real oscillator + ADSR, all inside the
worklet. The resolved decision is posted back to the main thread over the
`AudioWorkletNode.port` (a worklet's `process()` return value carries no
data, only a continue/stop signal) and the rendered PCM is captured via
`OfflineAudioContext`. `test/e2e/run_e2e.cljk` (nbb) then requires the
*same* `fixture.cljc` and `audio.synth` sources directly — a different
runtime, no browser involved — to independently recompute the expected
decision and waveform, and:

1. diffs the browser-resolved decision (sample-ref/freq/gain/pan/pitch-offset)
   against the offline (nbb) decision for bit-exactness;
2. diffs the captured PCM against an offline full-waveform render;
3. **actually measures** the frequency present in the captured PCM (via
   interpolated positive-going zero-crossing timing over the steady-state
   envelope window — not merely trusting the decision was followed) and
   compares it to the expected frequency;
4. checks the round-robin sequence literally alternates (`rr1 rr2 rr1`,
   not just "different each time") and that velocity-layer boundary inputs
   (63 vs. 64, 1, 127) and key-range boundary inputs (59/60/61/62) resolve
   to exactly the right zone (or no zone).

Real measured result (Chromium, Playwright-bundled, 2026-07-13):

| input | resolved (sample-ref, freq, gain) | browser == offline decision | captured-PCM max-abs-diff | measured freq | expected freq |
|---|---|---|---|---|---|
| note 60 vel 30 tc 0 | zoneA-rr1, 440.0 Hz, gain 0.7 | true | 2.97e-8 | 440.0000 Hz | 440.0000 Hz |
| note 60 vel 30 tc 1 | zoneA-rr2, 445.0 Hz, gain 0.665 | true | 2.98e-8 | 445.0000 Hz | 445.0000 Hz |
| note 60 vel 30 tc 2 | zoneA-rr1 (wraps) | true | 2.97e-8 | 440.0000 Hz | 440.0000 Hz |
| note 60 vel 100 tc 0 | zoneB-rr1, 220.0 Hz, gain 1.0 | true | 2.98e-8 | 220.0000 Hz | 220.0000 Hz |
| note 60 vel 100 tc 1 | zoneB-rr2, 225.0 Hz, gain 0.9 | true | 2.98e-8 | 225.0000 Hz | 225.0000 Hz |
| note 60 vel 100 tc 2 | zoneB-rr1 (wraps) | true | 2.98e-8 | 220.0000 Hz | 220.0000 Hz |
| vel 63 (below split) | zoneA-rr1 | true | 2.97e-8 | 440.0000 Hz | 440.0000 Hz |
| vel 64 (at split) | zoneB-rr1 | true | 2.98e-8 | 220.0000 Hz | 220.0000 Hz |
| vel 1 (zone A lower bound) | zoneA-rr1 | true | 2.97e-8 | 440.0000 Hz | 440.0000 Hz |
| vel 127 (zone B upper bound) | zoneB-rr1 | true | 2.98e-8 | 220.0000 Hz | 220.0000 Hz |
| vel 0 (no match) | nil, silence | true | peak 0 | — | — |
| key 61 (pitch-offset +7st) | zoneC-rr1, 494.44 Hz, gain 0.85 | true | 2.98e-8 | 494.4413 Hz | 494.4413 Hz |
| key 59 (no match) | nil, silence | true | peak 0 | — | — |
| key 62 (no match) | nil, silence | true | peak 0 | — | — |

Round-robin zone A sequence: `[:zoneA-rr1 :zoneA-rr2 :zoneA-rr1]` (matches).
Round-robin zone B sequence: `[:zoneB-rr1 :zoneB-rr2 :zoneB-rr1]` (matches).
All 14 browser-vs-offline decisions match exactly; all PCM diffs are ~3e-8
(the same `Float32Array`-vs-double rounding org-w3-webaudio's own E2E
found, not a correctness gap, tolerance 1e-6); all 5 distinct measured
frequencies match their expected frequency exactly to 4 decimal places.
`PASS: true`.

This is the strongest proof level currently reachable for this repo: real
zone/velocity/round-robin/pitch/gain decisions, made by this repo's own
unmodified logic, driving real oscillator DSP, inside a real
`AudioWorkletProcessor`, in a real browser — cross-verified bit-for-bit
against an independent (nbb) execution of the identical `.cljc` source.
What it does **not** prove: anything about real sample-file decoding
(still explicitly out of scope, per Scope above) or streaming lifecycle
timing under real disk/network I/O (the state machine's transitions are
unit tested, not exercised here).

Setup and run:

```bash
npm --prefix test/e2e install                    # Playwright
npx --prefix test/e2e playwright install chromium
bash scripts/build-e2e-bundles.sh                 # compiles kami.ongaku.sampler.e2e.{worklet-dsp,main-driver}
                                                   # -> test/e2e/page/{worklet-processor,main-driver-bundle}.js
                                                   # (JVM/Clojure CLI build step, not an app-runtime
                                                   # choice -- see scripts/build-e2e-bundles.sh)
AUDIO_SRC_PATH=/path/to/kotoba-lang/audio/src
kbb --backend sci -cp "src:test/e2e/src:$AUDIO_SRC_PATH" test/e2e/run_e2e.cljk
```

Exits 0 and prints the full per-input report (resolved decision, decision
cross-check, PCM diff, measured-vs-expected frequency) plus the
round-robin/overall summary on pass; exits 1 on any real failure (decision
mismatch, PCM beyond tolerance, measured frequency beyond tolerance,
round-robin sequence wrong) — no silent degradation. The `:e2e` deps.edn
alias takes `kotoba-lang/audio` and `kotoba-lang/org-w3-webaudio` as real
git dependencies (pinned by commit SHA); `test/e2e/page/*-bundle.js`,
`test/e2e/page/worklet-processor.js`, and `test/e2e/node_modules/` are
build artifacts, gitignored.

## Test

```
kbb -M:test
```

## License

Apache-2.0
