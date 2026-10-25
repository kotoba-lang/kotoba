(ns w3.webcodecs
  "Raw W3C WebCodecs JS API — thin ClojureScript wrapper, one function per
   spec call. No bitstream parsing, no container/demux opinions: this is the
   binding layer other repos (kotoba-lang/utsushi) build on, the same way
   org-w3-webgpu is the raw-spec layer under kami-webgpu.

   Config objects (desc/opts args below) are plain JS objects (`#js {...}`),
   built by the caller with the spec's own camelCase keys — this wrapper does
   not translate Clojure maps into configs, mirroring org-w3-webgpu's
   deliberate choice to leave map<->JS-descriptor translation to the
   EDN-vocabulary layer one level up (utsushi, for the codec/container
   domain).

   The one piece of WebCodecs logic with no browser dependency — parsing and
   constructing codec strings like \"avc1.42001f\" — lives in the portable
   `w3.webcodecs.codec-string` (.cljc) namespace instead, since it doesn't
   need a UA and can carry real clojure.test coverage.

   https://www.w3.org/TR/webcodecs/")

(defn supported?
  "true if this UA exposes the WebCodecs globals at all. WebCodecs has no
   single navigator.* capability flag the way WebGPU has `navigator.gpu` —
   the constructors themselves are the presence check."
  []
  (and (some? (.-VideoDecoder js/globalThis))
       (some? (.-VideoEncoder js/globalThis))))

;; --- capability checks (WebCodecs' analog of feature-detecting before use) -

(defn video-decoder-config-supported!
  "VideoDecoder.isConfigSupported(config) -> Promise<VideoDecoderSupport>.
   config is a VideoDecoderConfig JS object (must include :codec, spelled
   `codec` as a JS key — build it with `w3.webcodecs.codec-string` for the
   AVC case). Callers MUST check `.-supported` on the resolved value before
   constructing a decoder with this config — do not assume support from
   construction not throwing (per the ADR's completion-gate: capability
   judged explicitly, never silently degraded)."
  [config]
  (.isConfigSupported js/VideoDecoder config))

(defn video-encoder-config-supported!
  "VideoEncoder.isConfigSupported(config) -> Promise<VideoEncoderSupport>."
  [config]
  (.isConfigSupported js/VideoEncoder config))

(defn audio-decoder-config-supported!
  "AudioDecoder.isConfigSupported(config) -> Promise<AudioDecoderSupport>."
  [config]
  (.isConfigSupported js/AudioDecoder config))

(defn audio-encoder-config-supported!
  "AudioEncoder.isConfigSupported(config) -> Promise<AudioEncoderSupport>."
  [config]
  (.isConfigSupported js/AudioEncoder config))

;; --- decode: EncodedVideoChunk -> VideoFrame -------------------------------

(defn make-video-decoder
  "new VideoDecoder(init) — init is a VideoDecoderInit JS object with
   `output`/`error` callback fields (plain JS fns, e.g.
   `#js {:output (fn [^js frame] ...) :error (fn [^js e] ...)}`)."
  [init]
  (js/VideoDecoder. init))

(defn configure-video-decoder!
  "decoder.configure(config) — config is a VideoDecoderConfig JS object."
  [^js decoder config]
  (.configure decoder config))

(defn decode-video-chunk!
  "decoder.decode(chunk) — chunk is an EncodedVideoChunk."
  [^js decoder chunk]
  (.decode decoder chunk))

(defn make-encoded-video-chunk
  "new EncodedVideoChunk(init) — init: {:type \"key\"|\"delta\" :timestamp
   micros :duration micros :data (BufferSource)}, spelled with the spec's
   own camelCase JS keys (`type`/`timestamp`/`duration`/`data`)."
  [init]
  (js/EncodedVideoChunk. init))

(defn video-decoder-flush!
  "decoder.flush() -> Promise<void>. Resolves once all pending decode()
   calls' outputs have fired."
  [^js decoder]
  (.flush decoder))

(defn close-video-decoder! [^js decoder] (.close decoder))

;; --- encode: VideoFrame -> EncodedVideoChunk -------------------------------

(defn make-video-encoder
  "new VideoEncoder(init) — init: {:output (fn [chunk metadata] ...)
   :error (fn [e] ...)}."
  [init]
  (js/VideoEncoder. init))

(defn configure-video-encoder!
  "encoder.configure(config) — config is a VideoEncoderConfig JS object
   (:codec via w3.webcodecs.codec-string, :width, :height, :bitrate, ...)."
  [^js encoder config]
  (.configure encoder config))

(defn encode-video-frame!
  "encoder.encode(frame, opts?) — opts is an optional VideoEncoderEncodeOptions
   JS object (e.g. #js {:keyFrame true})."
  ([^js encoder frame] (.encode encoder frame))
  ([^js encoder frame opts] (.encode encoder frame opts)))

(defn make-video-frame
  "new VideoFrame(source, init) — source is a CanvasImageSource-compatible
   value (e.g. an ImageBitmap or another VideoFrame) or a BufferSource
   (raw pixel data), init is a VideoFrameInit/VideoFrameBufferInit JS object
   (:timestamp is required; :codedWidth/:codedHeight/:format required for
   the BufferSource form)."
  [source init]
  (js/VideoFrame. source init))

(defn close-video-frame! [^js frame] (.close frame))

(defn video-encoder-flush! [^js encoder] (.flush encoder))
(defn close-video-encoder! [^js encoder] (.close encoder))

;; --- audio mirrors ----------------------------------------------------------

(defn make-audio-decoder [init] (js/AudioDecoder. init))
(defn configure-audio-decoder! [^js decoder config] (.configure decoder config))
(defn decode-audio-chunk! [^js decoder chunk] (.decode decoder chunk))
(defn make-encoded-audio-chunk [init] (js/EncodedAudioChunk. init))
(defn audio-decoder-flush! [^js decoder] (.flush decoder))
(defn close-audio-decoder! [^js decoder] (.close decoder))

(defn make-audio-encoder [init] (js/AudioEncoder. init))
(defn configure-audio-encoder! [^js encoder config] (.configure encoder config))
(defn encode-audio-data! [^js encoder data] (.encode encoder data))
(defn make-audio-data [init] (js/AudioData. init))
(defn close-audio-data! [^js data] (.close data))
(defn audio-encoder-flush! [^js encoder] (.flush encoder))
(defn close-audio-encoder! [^js encoder] (.close encoder))
