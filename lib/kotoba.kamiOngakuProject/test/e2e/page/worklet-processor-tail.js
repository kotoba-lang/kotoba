// Hand-written registerProcessor tail, appended after the compiled
// worklet-dsp bundle (see scripts/build-e2e-bundles.sh) -- same pattern as
// every sibling repo's own test/e2e/page/worklet-processor-tail.js.
// Deliberately plain native JS class-extends syntax (real `super()`
// semantics) rather than a cljs deftype: extending a native built-in like
// AudioWorkletProcessor from cljs is not a solved idiom.
//
// All scheduling + DSP + BUS-GRAPH MIXING math comes from the compiled
// bundle's kami.ongaku.project.e2e.worklet_dsp.render_mix (i.e. from
// kami-ongaku-project's OWN real track/bus/clip session data +
// kami-ongaku-notation's/kami-ongaku-sequencer's own real content +
// kotoba-lang/audio's OWN oscillator/ADSR, not reimplementations) -- this
// file only (a) reads `drumsGain` off options.processorOptions (a plain
// number, structured-cloned in by the AudioWorkletNode constructor -- see
// main_driver.cljs docstring), (b) calls render_mix once in the
// constructor, (c) posts the computed validation/plan info back to the main
// thread over the port (a worklet's process() return value carries no data,
// only a continue/stop signal), and (d) streams the precomputed,
// already-bus-mixed buffer out through the realtime process() quantum
// callback.
class KamiProjectMixProcessor extends AudioWorkletProcessor {
  constructor(options) {
    super();
    const drumsGain =
      options && options.processorOptions && typeof options.processorOptions.drumsGain === 'number'
        ? options.processorOptions.drumsGain
        : 1.0;
    const result = kami.ongaku.project.e2e.worklet_dsp.render_mix(drumsGain);
    this.buffer = result.pcm;
    this.readIdx = 0;
    this.port.postMessage({
      drumsGain: result.drumsGain,
      totalSamples: result.totalSamples,
      validationErrors: result.validationErrors,
      notationNotes: result.notationNotes,
      midiNotes: result.midiNotes
    });
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
registerProcessor('kami-project-mix-processor', KamiProjectMixProcessor);
