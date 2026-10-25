// Hand-written registerProcessor tail, appended after the compiled
// worklet-dsp bundle (see scripts/build-e2e-bundles.sh) -- same pattern as
// kotoba-lang/org-w3-webaudio's own test/e2e/page/worklet-processor-tail.js.
// Deliberately plain native JS class-extends syntax (real `super()`
// semantics) rather than a cljs deftype: extending a native built-in like
// AudioWorkletProcessor from cljs is not a solved idiom, whereas this is a
// handful of lines and keeps registerProcessor's real-`class` requirements
// unambiguous.
//
// All resolution + DSP math comes from the compiled bundle's
// kami.ongaku.sampler.e2e.worklet_dsp.render_trigger (i.e. from kami-ongaku-sampler's
// OWN trigger/lookup logic + kotoba-lang/audio's OWN oscillator/ADSR, not
// reimplementations) -- this file only (a) calls it once in the
// constructor, (b) posts the resolved decision back to the main thread over
// the port (a worklet's process() return value only controls whether
// rendering continues, it carries no arbitrary data back to the main
// thread -- the MessagePort is the only channel for that), and (c) streams
// the precomputed buffer out through the realtime process() quantum
// callback.
class KamiSamplerTriggerProcessor extends AudioWorkletProcessor {
  constructor(options) {
    super();
    const p = (options && options.processorOptions) || {};
    const result = kami.ongaku.sampler.e2e.worklet_dsp.render_trigger(
      p.note, p.velocity, p.triggerCount, p.sr, p.durSamples, p.gateOff,
      p.attack, p.decay, p.sustain, p.release);
    this.buffer = result.pcm;
    this.readIdx = 0;
    this.port.postMessage({ decision: result.decision || null });
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
registerProcessor('kami-sampler-trigger-processor', KamiSamplerTriggerProcessor);
