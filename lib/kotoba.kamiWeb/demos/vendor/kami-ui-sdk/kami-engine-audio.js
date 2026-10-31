/**
 * KAMI Engine Audio v0.1.0
 * Physically-modelled internal-combustion-engine synthesizer for the
 * car-sim demo (driver.etzhayyim.com). Synthesised entirely with Web Audio
 * API primitives — no audio files, per KAMI rules.
 *
 * Topology:
 *
 *   bandlimited sawtooth (engine fundamental)
 *      │
 *      ├─► harmonic stack (4 partials × falloff)
 *      │     │
 *      │     └─► biquad lowpass (RPM-driven cutoff)
 *      │            │
 *      │            └─► exhaust delay-line (~12 ms feedback,
 *      │                  models tail-pipe reflection)
 *      │
 *      └─► noise bus (combustion / induction roar)
 *            │
 *            └─► biquad bandpass (RPM-driven centre)
 *
 *   Tire bus: noise → bandpass (slip-driven Q) → masterGain
 *   Impact bus: scheduled impulse → highpass → masterGain
 *
 * Reads:
 *   window.__carsim_hud   — { rpm, throttle, gear, speed_kmh, grounded_wheels, broken_beams }
 *   window.__carsim_steer — for tire scrub modulation
 *   window.__carsim_brake — for tire chirp modulation
 *
 * Usage:
 *   await KamiEngineAudio.init();
 *   KamiEngineAudio.start();      // begins polling __carsim_hud per RAF
 *   KamiEngineAudio.stop();
 *   KamiEngineAudio.setVolume(0.5);
 *
 * @license MIT
 */
(function (root) {
"use strict";

let ctx = null;
let masterGain = null;
let _running = false;
let _rafId = 0;

// graph nodes (re-used across frames; we modulate parameters, not topology).
let engineSaw = null;
let engineHarmonics = []; // { osc, gain }
let engineLowpass = null;
let engineBus = null;
let exhaustDelay = null;
let exhaustFeedback = null;
let inductionNoise = null;
let inductionBandpass = null;
let inductionGain = null;
let tireNoise = null;
let tireBandpass = null;
let tireGain = null;

// Engine character — these reasonable numbers match a small 4-cylinder.
const CYLINDERS = 4;
const FIRINGS_PER_REV = CYLINDERS / 2; // 4-stroke
const IDLE_RPM = 800;
const REDLINE_RPM = 7200;
const HARMONIC_COUNT = 5;

function _ensureCtx() {
  if (ctx) return ctx;
  ctx = new (window.AudioContext || window.webkitAudioContext)();
  masterGain = ctx.createGain();
  masterGain.gain.value = 0.25; // conservative — driver demo isn't a stereo
  masterGain.connect(ctx.destination);
  return ctx;
}

/**
 * Build a bandlimited sawtooth via additive synthesis. WebAudio's
 * `OscillatorNode('sawtooth')` aliases above the Nyquist; the explicit
 * harmonic stack below avoids that and lets us shape per-harmonic gain
 * from RPM (so the engine "opens up" with throttle).
 */
function _buildEngineGraph() {
  const c = _ensureCtx();
  // Master engine bus (post-combustion-roar, pre-master).
  engineBus = c.createGain();
  engineBus.gain.value = 0.0;

  // Lowpass — its cutoff tracks RPM so high RPM gets the bright midrange.
  engineLowpass = c.createBiquadFilter();
  engineLowpass.type = "lowpass";
  engineLowpass.frequency.value = 600;
  engineLowpass.Q.value = 0.7;

  // Exhaust delay-line (12 ms ≈ tail-pipe length / sound speed * 2).
  exhaustDelay = c.createDelay(0.05);
  exhaustDelay.delayTime.value = 0.012;
  exhaustFeedback = c.createGain();
  exhaustFeedback.gain.value = 0.45;

  // Harmonic stack: fundamental + 4 partials at integer × fundamental,
  // each running through `engineBus` so we control amplitude as one.
  engineHarmonics = [];
  for (let h = 1; h <= HARMONIC_COUNT; h++) {
    const osc = c.createOscillator();
    osc.type = "sawtooth";
    const g = c.createGain();
    // Falloff matches typical exhaust spectrum (1/h).
    g.gain.value = 1.0 / h;
    osc.connect(g);
    g.connect(engineLowpass);
    osc.start();
    engineHarmonics.push({ osc, gain: g, harmonic: h });
  }

  // Wire: lowpass → exhaust delay (with feedback) → engineBus → master.
  engineLowpass.connect(exhaustDelay);
  exhaustDelay.connect(exhaustFeedback);
  exhaustFeedback.connect(exhaustDelay); // feedback loop
  engineLowpass.connect(engineBus);
  exhaustDelay.connect(engineBus);
  engineBus.connect(masterGain);
}

function _buildInductionNoise() {
  const c = _ensureCtx();
  // 2-second white-noise buffer, looped — induction / combustion roar.
  const buf = c.createBuffer(1, c.sampleRate * 2, c.sampleRate);
  const data = buf.getChannelData(0);
  for (let i = 0; i < data.length; i++) data[i] = Math.random() * 2 - 1;
  inductionNoise = c.createBufferSource();
  inductionNoise.buffer = buf;
  inductionNoise.loop = true;
  inductionBandpass = c.createBiquadFilter();
  inductionBandpass.type = "bandpass";
  inductionBandpass.frequency.value = 220;
  inductionBandpass.Q.value = 1.5;
  inductionGain = c.createGain();
  inductionGain.gain.value = 0.0;
  inductionNoise.connect(inductionBandpass);
  inductionBandpass.connect(inductionGain);
  inductionGain.connect(masterGain);
  inductionNoise.start();
}

function _buildTireNoise() {
  const c = _ensureCtx();
  const buf = c.createBuffer(1, c.sampleRate * 2, c.sampleRate);
  const data = buf.getChannelData(0);
  for (let i = 0; i < data.length; i++) data[i] = Math.random() * 2 - 1;
  tireNoise = c.createBufferSource();
  tireNoise.buffer = buf;
  tireNoise.loop = true;
  tireBandpass = c.createBiquadFilter();
  tireBandpass.type = "bandpass";
  tireBandpass.frequency.value = 1200;
  tireBandpass.Q.value = 0.8;
  tireGain = c.createGain();
  tireGain.gain.value = 0.0;
  tireNoise.connect(tireBandpass);
  tireBandpass.connect(tireGain);
  tireGain.connect(masterGain);
  tireNoise.start();
}

/**
 * Per-frame parameter update from the car-sim HUD.
 * `rpm` drives the fundamental frequency through the firing-order math:
 *
 *   firings_per_sec = rpm / 60 × cylinders / 2     (4-stroke)
 *
 * Throttle drives engine bus volume (open throttle = louder).
 * Speed drives tire noise; brake / steer drive its bandpass.
 */
function _tick() {
  if (!_running) return;
  _rafId = requestAnimationFrame(_tick);
  const c = ctx;
  if (!c) return;
  const t = c.currentTime;

  const hud = root.__carsim_hud || {};
  const rpm = Math.max(IDLE_RPM, Math.min(REDLINE_RPM, hud.rpm ?? IDLE_RPM));
  const throttle = Math.max(0, Math.min(1, hud.throttle ?? 0));
  const speedKmh = Math.max(0, hud.speed_kmh ?? 0);
  const grounded = Math.max(0, Math.min(4, hud.grounded_wheels ?? 0));
  const brake = Math.max(0, Math.min(1, hud.brake ?? 0));
  const steer = Math.abs(root.__carsim_steer ?? 0);

  const fundamental = (rpm / 60) * FIRINGS_PER_REV;

  // Engine fundamental + harmonics.
  for (const h of engineHarmonics) {
    h.osc.frequency.setTargetAtTime(fundamental * h.harmonic, t, 0.04);
    // Higher harmonics fade with idle, bloom with throttle.
    const gainTarget = (1.0 / h.harmonic) * (0.4 + 0.6 * throttle);
    h.gain.gain.setTargetAtTime(gainTarget, t, 0.06);
  }
  // Lowpass tracks RPM linearly (idle ≈ 600 Hz, redline ≈ 4 kHz).
  const cutoff = 600 + (rpm / REDLINE_RPM) * 3400;
  engineLowpass.frequency.setTargetAtTime(cutoff, t, 0.05);

  // Engine bus volume — load-following.
  const engineLoud = 0.10 + 0.45 * (rpm / REDLINE_RPM) + 0.25 * throttle;
  engineBus.gain.setTargetAtTime(engineLoud * 0.6, t, 0.04);

  // Induction noise: louder under heavy throttle, slight RPM tracking.
  inductionBandpass.frequency.setTargetAtTime(180 + (rpm / REDLINE_RPM) * 600, t, 0.05);
  inductionGain.gain.setTargetAtTime(throttle * 0.18, t, 0.05);

  // Tire noise — louder with speed, brighter under brake / steer.
  const tireBase = grounded === 0 ? 0 : Math.min(1, speedKmh / 80);
  const tireLoud = tireBase * (0.10 + 0.35 * (brake + steer));
  tireGain.gain.setTargetAtTime(tireLoud, t, 0.05);
  tireBandpass.frequency.setTargetAtTime(800 + 1800 * (brake * 0.6 + steer * 0.4), t, 0.05);
}

/** Trigger a one-shot impact thump — call from on-collision JS. */
function impact(intensity) {
  if (!ctx || !masterGain) return;
  const c = ctx;
  const t = c.currentTime;
  const i = Math.max(0, Math.min(1, intensity ?? 0.5));
  const g = c.createGain();
  const f = c.createBiquadFilter();
  f.type = "highpass";
  f.frequency.value = 60;
  const buf = c.createBuffer(1, c.sampleRate * 0.25, c.sampleRate);
  const data = buf.getChannelData(0);
  // Decaying noise burst.
  for (let n = 0; n < data.length; n++) {
    const env = Math.exp(-n * 30 / data.length);
    data[n] = (Math.random() * 2 - 1) * env;
  }
  const src = c.createBufferSource();
  src.buffer = buf;
  src.connect(f);
  f.connect(g);
  g.connect(masterGain);
  g.gain.setValueAtTime(i * 0.6, t);
  g.gain.exponentialRampToValueAtTime(0.001, t + 0.30);
  src.start(t);
  src.stop(t + 0.35);
}

/**
 * Build the audio graph. Idempotent. Browsers require user-gesture
 * before the AudioContext can produce sound — call this from a click
 * handler.
 */
async function init() {
  _ensureCtx();
  if (ctx.state === "suspended") {
    try { await ctx.resume(); } catch (_) { /* ignore */ }
  }
  if (engineHarmonics.length === 0) {
    _buildEngineGraph();
    _buildInductionNoise();
    _buildTireNoise();
  }
}

function start() {
  if (_running) return;
  _running = true;
  _rafId = requestAnimationFrame(_tick);
}

function stop() {
  _running = false;
  if (_rafId) cancelAnimationFrame(_rafId);
  _rafId = 0;
  // Mute buses without tearing down the graph — start() resumes cleanly.
  if (engineBus) engineBus.gain.value = 0;
  if (inductionGain) inductionGain.gain.value = 0;
  if (tireGain) tireGain.gain.value = 0;
}

function setVolume(v) {
  if (!masterGain) return;
  masterGain.gain.setTargetAtTime(Math.max(0, Math.min(1, v)), ctx.currentTime, 0.05);
}

const api = { init, start, stop, impact, setVolume };
if (typeof module !== "undefined" && module.exports) module.exports = api;
root.KamiEngineAudio = api;

})(typeof window !== "undefined" ? window : this);
