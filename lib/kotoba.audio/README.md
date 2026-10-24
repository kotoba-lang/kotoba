# kotoba-lang/audio

KAMI Audio — zero-dep portable `.cljc`, restored from the legacy
`kami-engine/kami-audio` Rust crate (537 lines across `src/lib.rs`,
`src/binaural.rs`, `src/wav.rs`; deleted in kami-engine PR #82 "Remove
Rust workspace from kami-engine") as part of the **clj-wgsl migration**
(ADR-2607010930, `com-junkawasaki/root`).

Ledger class `:port-to-WGSL-compute` ("mixer loop + voice alloc + SR
buffer mgmt; emit :native stays for real-time latency"). Per owner
decision this is restored as a plain interim CLJC port of the pure
mixer / voice-allocation / binaural-spatialization data and math — not
actual WGSL compute code, and not real-time audio-hardware-callback
code. The original crate had no literal hardware-callback code to
exclude: `AudioMixer::spatialize` / `active_voices`, the binaural DSP,
and the WAV encoder are all pure functions over plain data/buffers, so
the port is complete (nothing was intentionally left out).

## Modules

- **`src/audio.cljk`** (from `src/lib.rs`) — `AudioSource` / `Listener`
  / `AudioMixer`: 3D positional audio sources, distance attenuation
  (`:linear` / `:inverse` / `:exponential` rolloff), a simplified
  stereo pan (dot product against the listener's right vector), a
  per-channel + master volume mix, and priority-based voice limiting
  (`active-voices`).
- **`src/audio/binaural.cljk`** (from `src/binaural.rs`) — physically
  grounded spherical-head binaural spatialization: Woodworth ITD
  (`itd = (a/c)(theta + sin theta)`), frequency-independent ILD
  head-shadow, distance rolloff (`:none` / `:inverse` / `:linear` /
  `:exponential`), and `mix-stereo` — pure software mixing of
  per-source mono buffers into an interleaved stereo buffer with
  per-ear ITD sample delay and gain.
- **`src/audio/wav.cljk`** (from `src/wav.rs`) — dependency-free 16-bit
  PCM stereo WAV encoding (`encode-pcm16-stereo`) of an interleaved
  stereo float buffer, e.g. the output of `audio.binaural/mix-stereo`.
  JVM implementation via `java.nio.ByteBuffer` (matching the
  JVM-binary-export pattern already used in `kotoba-lang/engineer-io`'s
  `engineer-io.stl/export-binary` and `kotoba-lang/pnr`'s
  `pnr.gdsii`); CLJS implementation via `js/ArrayBuffer` + `js/DataView`.
- **`src/audio/runtime.cljk`** — provider-neutral game-audio control
  plane: master/music/SFX/voice/ambient/UI buses, gain and mute,
  voice/UI ducking, deterministic scene crossfade action plans,
  listener/source state and stable priority voice admission. Web Audio
  and native hosts execute these pure actions rather than reimplement policy.
- **`resources/audio/runtime.edn`** — machine-readable runtime contract
  for host adapters and game manifests.

## Relationship to `kotoba-lang/rtc`

The sibling restoration `kotoba-lang/rtc`'s `rtc.spatial` namespace
implements its own self-contained, simpler stereo-pan calculation
(equal-power pan + inverse-distance rolloff) because `kami-audio` had
not yet been restored to CLJC when `rtc` was restored. The two
implementations are intentionally independent and are not unified by
this restoration — `rtc.spatial` documents its own relationship to
this crate in its namespace docstring.

## Wave 2 — synthesis / filter / effects / mixer (ADR-2607121400)

Adds the DSP layer this repo's role as the `ongaku` domain's L2
executor was missing (pure functions over plain sample buffers, no
device/callback code, same discipline as the modules above):

- **`src/audio/synth.cljk`** — sine/square/saw/triangle oscillators
  (non band-limited — plain waveform generators, aliasing not
  mitigated in v0) and an ADSR envelope generator
  (`adsr` + `apply-envelope`), with `seconds->samples` converting
  time to an exact integer sample count once, at the boundary.
- **`src/audio/filter.cljk`** — one-pole (6 dB/octave) low-pass and
  high-pass filters, derived from the analog RC low-pass discretized
  via backward difference. Not a substitute for a biquad/SVF when
  steeper slopes are needed.
- **`src/audio/effects.cljk`** — a feedback delay line (circular
  buffer, exact integer delay length, wet/dry mix) and a feed-forward
  compressor (one-pole envelope follower, threshold/ratio/attack/release).
- **`src/audio/mixer.cljk`** — an offline mixer bus graph: tracks
  (mono buffer + gain + equal-power pan) route into buses, buses can
  route into other buses (a real graph), `find-cycle` detects bus-to-bus
  cycles before `render-bus-graph` sums everything to a stereo buffer.
  Shape intentionally close to `kami-ongaku-project`'s bus/track model
  (no hard dependency).

Not in scope for v0: realtime/AudioWorklet playback (this is an
offline/batch renderer), band-limited oscillators, biquad filters,
sidechain compression, automation curves (that's `kami-ongaku-project`'s
job — this repo just renders a static mix).

## Tests

All 11 original Rust `#[test]`s (1 from `lib.rs`, 8 from `binaural.rs`,
2 from `wav.rs`) ported 1:1 to `test/audio_test.cljk`, plus the
pre-existing scaffold smoke test, 18 Wave 2 DSP tests and three
game-runtime contract tests — **33 tests / 196 assertions, 0 failures,
0 errors**.

## Develop

```bash
kbb -M:test
```
