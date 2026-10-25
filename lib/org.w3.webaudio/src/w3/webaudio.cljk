(ns w3.webaudio
  "Raw W3C Web Audio API — thin ClojureScript wrapper, one function per spec
   call. No DSP, no synthesis/effects/mixer opinions: this is the binding
   layer other repos (kotoba-lang/audio) build on, the same way
   kotoba-lang/webgpu builds on kotoba-lang/org-w3-webgpu.

   Descriptors/options (opts args below) are plain JS objects (`#js {...}`),
   built by the caller with the spec's own camelCase keys — this wrapper does
   not translate Clojure maps into descriptors, mirroring org-w3-webgpu's
   same deliberate non-translation stance.

   AudioWorkletNode <-> AudioWorkletProcessor communication crosses a
   MessagePort; the *content* of those messages (note-on/note-off/param
   changes/PCM-block framing) is not part of this repo's raw-spec scope —
   see `w3.webaudio.protocol` for a portable, unit-testable message
   encode/decode layer above this wrapper's `post-message!`/`on-message!`.

   https://www.w3.org/TR/webaudio/")

(defn supported? []
  (or (some? (.-AudioContext js/window))
      (some? (.-webkitAudioContext js/window))))

(defn- ctor []
  (or (.-AudioContext js/window) (.-webkitAudioContext js/window)))

(defn new-audio-context!
  "-> AudioContext. opts, if given, is an AudioContextOptions JS object."
  ([] (new-audio-context! nil))
  ([opts]
   ;; `(new (ctor) ...)` mis-compiles when the class expression is itself a
   ;; fn call: cljs emits `(new w3.webaudio.ctor.call(null))(opts)` (a `new`
   ;; over the bare `.call` reference, then invoking the *result* with
   ;; `(opts)`), throwing "... .call is not a constructor" at runtime. Bind
   ;; the constructor to a local first so `new` gets a plain symbol.
   (let [Ctor (ctor)]
     (if opts (new Ctor opts) (new Ctor)))))

(defn new-offline-audio-context!
  "-> OfflineAudioContext(numberOfChannels, length, sampleRate). Used for
   deterministic, non-realtime (software) rendering — the only way to
   exercise AudioWorklet output in headless/CI environments without a real
   audio output device."
  [num-channels length sample-rate]
  (new js/OfflineAudioContext num-channels length sample-rate))

(defn start-rendering!
  "OfflineAudioContext.startRendering() -> Promise<AudioBuffer>."
  [^js ctx]
  (.startRendering ctx))

(defn sample-rate [^js ctx] (.-sampleRate ctx))
(defn current-time [^js ctx] (.-currentTime ctx))
(defn state [^js ctx] (keyword (.-state ctx)))
(defn destination [^js ctx] (.-destination ctx))

(defn resume! [^js ctx] (.resume ctx))
(defn suspend! [^js ctx] (.suspend ctx))
(defn close! [^js ctx] (.close ctx))

(defn add-worklet-module!
  "ctx.audioWorklet.addModule(url) -> Promise<undefined>."
  [^js ctx url]
  (.addModule (.-audioWorklet ctx) url))

(defn create-worklet-node!
  "new AudioWorkletNode(ctx, processor-name, opts) -> AudioWorkletNode.
   opts, if given, is an AudioWorkletNodeOptions JS object (may include
   numberOfInputs/numberOfOutputs/outputChannelCount/processorOptions)."
  ([^js ctx processor-name] (create-worklet-node! ctx processor-name nil))
  ([^js ctx processor-name opts]
   (if opts
     (new js/AudioWorkletNode ctx processor-name opts)
     (new js/AudioWorkletNode ctx processor-name))))

(defn create-gain! [^js ctx] (.createGain ctx))
(defn create-buffer!
  "ctx.createBuffer(numberOfChannels, length, sampleRate) -> AudioBuffer."
  [^js ctx num-channels length sample-rate]
  (.createBuffer ctx num-channels length sample-rate))

(defn create-buffer-source! [^js ctx] (.createBufferSource ctx))

(defn set-gain! [^js gain-node value]
  (set! (.-value (.-gain gain-node)) value))

(defn connect!
  "src.connect(dest) -- dest may be an AudioNode or an AudioParam."
  [^js src dest]
  (.connect src dest))

(defn disconnect!
  ([^js node] (.disconnect node))
  ([^js node dest] (.disconnect node dest)))

;; --- AudioWorkletNode.port (MessagePort) -----------------------------------

(defn port [^js worklet-node] (.-port worklet-node))

(defn post-message!
  "port.postMessage(data, transfer?) -- data is a plain JS value (see
   w3.webaudio.protocol for building it from an EDN message map).
   transfer, if given, is a JS array of Transferable objects
   (e.g. #js [float32-array.buffer])."
  ([^js port data] (.postMessage port data))
  ([^js port data transfer] (.postMessage port data transfer)))

(defn on-message!
  "Registers f (a fn of one arg, the MessageEvent) as port.onmessage.
   Returns nil; call again with a no-op fn to unregister."
  [^js port f]
  (set! (.-onmessage port) f))
