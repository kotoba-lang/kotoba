// Hand-written registerProcessor tail, appended after the compiled
// worklet-dsp bundle (see scripts/build-e2e-bundles.sh) -- same pattern as
// kotoba-lang/org-w3-webaudio's and kotoba-lang/kami-ongaku-sampler's own
// test/e2e/page/worklet-processor-tail.js. Deliberately plain native JS
// class-extends syntax (real `super()` semantics) rather than a cljs
// deftype: extending a native built-in like AudioWorkletProcessor from cljs
// is not a solved idiom, whereas this is a handful of lines and keeps
// registerProcessor's real-`class` requirements unambiguous.
//
// All scheduling + DSP math comes from the compiled bundle's
// kami.ongaku.sequencer.e2e.worklet_dsp.render_pattern (i.e. from kami-ongaku-
// sequencer's OWN real, reimported-after-SMF-round-trip event data +
// kotoba-lang/audio's OWN oscillator/ADSR, not reimplementations) -- this
// file only (a) calls it once in the constructor, (b) posts the computed
// plan back to the main thread over the port (a worklet's process() return
// value only controls whether rendering continues, it carries no arbitrary
// data back to the main thread -- the MessagePort is the only channel for
// that), and (c) streams the precomputed, already-multi-note-mixed buffer
// out through the realtime process() quantum callback.
class KamiSequencerProcessor extends AudioWorkletProcessor {
  constructor(options) {
    super();
    const result = kami.ongaku.sequencer.e2e.worklet_dsp.render_pattern();
    this.buffer = result.pcm;
    this.readIdx = 0;
    this.port.postMessage({ plan: result.plan, totalSamples: result.totalSamples });
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
registerProcessor('kami-sequencer-processor', KamiSequencerProcessor);
