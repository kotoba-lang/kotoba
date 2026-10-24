// Hand-written registerProcessor tail, appended after the compiled
// worklet-dsp bundle (see scripts/build-e2e-bundles.sh). Deliberately plain
// native JS class-extends syntax (real `super()` semantics) rather than a
// cljs deftype: extending a native built-in like AudioWorkletProcessor from
// cljs is not a solved idiom, whereas this is a handful of lines and keeps
// registerProcessor's real-`class` requirements unambiguous. All DSP math
// still comes from the compiled bundle's globalThis.kamiRenderNote (i.e.
// from kotoba-lang/audio's own audio.synth) -- this file only streams the
// precomputed buffer out through the realtime process() quantum callback.
class KamiNoteProcessor extends AudioWorkletProcessor {
  constructor(options) {
    super();
    const p = (options && options.processorOptions) || {};
    this.buffer = w3.webaudio.e2e.worklet_dsp.render_note(
      p.freq, p.sr, p.durSamples, p.gateOff, p.attack, p.decay, p.sustain, p.release);
    this.readIdx = 0;
  }
  process(_inputs, outputs) {
    const output = outputs[0];
    if (!output || output.length === 0) return this.readIdx < this.buffer.length;
    const n = output[0].length;
    for (let ch = 0; ch < output.length; ch++) {
      const outCh = output[ch];
      for (let k = 0; k < n; k++) {
        const gi = this.readIdx + k;
        outCh[k] = gi < this.buffer.length ? this.buffer[gi] : 0;
      }
    }
    this.readIdx += n;
    return this.readIdx < this.buffer.length;
  }
}
registerProcessor('kami-note-processor', KamiNoteProcessor);
