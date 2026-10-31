/**
 * KAMI Sound SDK v1.0.0
 * Nintendo-inspired procedural sound effects via Web Audio API.
 * Zero-dependency. No audio files needed — all sounds synthesized.
 *
 * Usage:
 *   KamiSound.init();
 *   KamiSound.play('click');
 *   KamiSound.play('success');
 *
 * @license MIT
 * @see https://kami.etzhayyim.com/sound-sdk
 */
(function(root) {
"use strict";

let ctx = null;
let masterGain = null;
let _enabled = true;
let _volume = 0.3;

function _ensureCtx() {
  if (ctx) return ctx;
  ctx = new (window.AudioContext || window.webkitAudioContext)();
  masterGain = ctx.createGain();
  masterGain.gain.value = _volume;
  masterGain.connect(ctx.destination);
  return ctx;
}

function _osc(type, freq, duration, opts) {
  opts = opts || {};
  const c = _ensureCtx();
  const t = c.currentTime + (opts.delay || 0);

  const osc = c.createOscillator();
  const gain = c.createGain();

  osc.type = type;
  osc.frequency.setValueAtTime(freq, t);

  // Frequency sweep
  if (opts.freqTo) {
    osc.frequency.exponentialRampToValueAtTime(Math.max(opts.freqTo, 20), t + duration);
  }

  // Envelope: attack → sustain → release
  const attack = opts.attack || 0.01;
  const release = opts.release || duration * 0.3;
  const vol = opts.volume || 0.5;
  gain.gain.setValueAtTime(0, t);
  gain.gain.linearRampToValueAtTime(vol, t + attack);
  gain.gain.setValueAtTime(vol, t + duration - release);
  gain.gain.exponentialRampToValueAtTime(0.001, t + duration);

  osc.connect(gain);
  gain.connect(masterGain);
  osc.start(t);
  osc.stop(t + duration + 0.05);
}

function _noise(duration, opts) {
  opts = opts || {};
  const c = _ensureCtx();
  const t = c.currentTime + (opts.delay || 0);

  const bufferSize = c.sampleRate * duration;
  const buffer = c.createBuffer(1, bufferSize, c.sampleRate);
  const data = buffer.getChannelData(0);
  for (let i = 0; i < bufferSize; i++) data[i] = Math.random() * 2 - 1;

  const source = c.createBufferSource();
  source.buffer = buffer;

  const gain = c.createGain();
  const vol = opts.volume || 0.15;
  gain.gain.setValueAtTime(vol, t);
  gain.gain.exponentialRampToValueAtTime(0.001, t + duration);

  // Optional filter
  if (opts.filter) {
    const filter = c.createBiquadFilter();
    filter.type = opts.filter.type || 'lowpass';
    filter.frequency.value = opts.filter.freq || 2000;
    filter.Q.value = opts.filter.Q || 1;
    source.connect(filter);
    filter.connect(gain);
  } else {
    source.connect(gain);
  }
  gain.connect(masterGain);
  source.start(t);
}

// ━━━ Sound Presets ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

const presets = {
  /** UI click — short sine pip (Switch button tap) */
  click() {
    _osc('sine', 800, 0.08, { volume: 0.3, release: 0.04 });
  },

  /** Hover — soft high tone */
  hover() {
    _osc('sine', 1200, 0.05, { volume: 0.12, release: 0.03 });
  },

  /** Select — two-tone confirm (Mario menu select) */
  select() {
    _osc('sine', 660, 0.1, { volume: 0.25, release: 0.05 });
    _osc('sine', 880, 0.12, { volume: 0.25, delay: 0.08, release: 0.06 });
  },

  /** Success — ascending triad (1-UP / star get) */
  success() {
    _osc('sine', 523, 0.12, { volume: 0.25 });         // C5
    _osc('sine', 659, 0.12, { volume: 0.25, delay: 0.1 }); // E5
    _osc('sine', 784, 0.18, { volume: 0.3, delay: 0.2 });  // G5
  },

  /** Error — descending buzz (wrong answer) */
  error() {
    _osc('square', 300, 0.15, { volume: 0.2, freqTo: 200 });
    _osc('square', 250, 0.2, { volume: 0.15, delay: 0.12, freqTo: 150 });
  },

  /** Warning — two low tones */
  warning() {
    _osc('triangle', 400, 0.15, { volume: 0.2 });
    _osc('triangle', 350, 0.15, { volume: 0.2, delay: 0.15 });
  },

  /** Pop — bubble pop (Animal Crossing speech) */
  pop() {
    _osc('sine', 600, 0.06, { volume: 0.3, freqTo: 1200, release: 0.03 });
  },

  /** Whoosh — sweep for transitions (Splatoon ink) */
  whoosh() {
    _noise(0.2, { volume: 0.1, filter: { type: 'bandpass', freq: 3000, Q: 2 } });
    _osc('sine', 400, 0.15, { volume: 0.08, freqTo: 1600 });
  },

  /** Coin — Mario coin collect */
  coin() {
    _osc('square', 988, 0.08, { volume: 0.2 });    // B5
    _osc('square', 1319, 0.3, { volume: 0.2, delay: 0.08 }); // E6
  },

  /** Navigate — soft click for pan/zoom */
  navigate() {
    _osc('sine', 500, 0.04, { volume: 0.1, freqTo: 600, release: 0.02 });
  },

  /** Zoom in — ascending pitch */
  zoomIn() {
    _osc('sine', 400, 0.1, { volume: 0.12, freqTo: 800, release: 0.05 });
  },

  /** Zoom out — descending pitch */
  zoomOut() {
    _osc('sine', 800, 0.1, { volume: 0.12, freqTo: 400, release: 0.05 });
  },

  /** Reset — Nintendo Switch return/cancel */
  reset() {
    _osc('sine', 880, 0.08, { volume: 0.2, freqTo: 440 });
    _osc('sine', 660, 0.12, { volume: 0.15, delay: 0.06 });
  },

  /** Load complete — Zelda item get (short) */
  loaded() {
    _osc('sine', 587, 0.1, { volume: 0.2 });          // D5
    _osc('sine', 698, 0.1, { volume: 0.2, delay: 0.08 }); // F5
    _osc('sine', 880, 0.1, { volume: 0.2, delay: 0.16 }); // A5
    _osc('sine', 1175, 0.25, { volume: 0.25, delay: 0.24 }); // D6
  },

  /** Typing — keyboard tick (for label reveals) */
  tick() {
    _osc('square', 2000 + Math.random() * 1000, 0.02, { volume: 0.06, release: 0.01 });
  },
};

// ━━━ Public API ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

root.KamiSound = {
  VERSION: '1.0.0',

  /** Initialize audio context (call on first user interaction). */
  init(opts) {
    opts = opts || {};
    if (opts.volume !== undefined) _volume = opts.volume;
    _enabled = opts.enabled !== false;
    _ensureCtx();
    if (ctx.state === 'suspended') ctx.resume();
  },

  /** Play a named sound. */
  play(name) {
    if (!_enabled) return;
    const fn = presets[name];
    if (fn) fn();
  },

  /** Set master volume (0-1). */
  setVolume(v) {
    _volume = v;
    if (masterGain) masterGain.gain.value = v;
  },

  /** Enable/disable sound. */
  setEnabled(v) { _enabled = v; },

  /** Get available sound names. */
  list() { return Object.keys(presets); },

  /** Register a custom sound preset. */
  register(name, fn) { presets[name] = fn; },

  /** Low-level: create oscillator. */
  osc: _osc,
  /** Low-level: create noise burst. */
  noise: _noise,
};

})(typeof globalThis !== 'undefined' ? globalThis : typeof window !== 'undefined' ? window : this);
