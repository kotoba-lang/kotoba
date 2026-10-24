(ns audio.wav
  "WAV sink — restored from kami-engine's `kami-audio` Rust crate
  (`src/wav.rs`, deleted PR #82 \"Remove Rust workspace from
  kami-engine\") to zero-dep portable CLJC as part of the clj-wgsl
  migration (ADR-2607010930, com-junkawasaki/root).

  Encodes an interleaved stereo f32 buffer (e.g. from
  [[audio.binaural/mix-stereo]]) into 16-bit PCM WAV bytes. A
  device-free audio sink: the host can write these bytes to a file
  (offline render / golden audio test) or hand them to a real device
  backend (cpal / Web Audio). Dependency-free — the WAV container is
  hand-written, matching the original.

  Ledger class `:port-to-WGSL-compute`; restored as a plain interim
  CLJC port of the pure binary-encode logic per owner decision — this
  is pure data transformation (float samples -> WAV bytes), not a
  real-time audio-hardware callback, so nothing was excluded.

  Binary I/O uses a `#?(:clj ... :cljs ...)` reader conditional: JVM
  writes via `java.nio.ByteBuffer` (matching the JVM-binary-export
  pattern in `kotoba-lang/engineer-io`'s `engineer-io.stl/export-binary`
  and `kotoba-lang/pnr`'s `pnr.gdsii`); CLJS writes via `js/ArrayBuffer`
  + `js/DataView`."
  #?(:clj (:import [java.nio ByteBuffer ByteOrder])))

(def header-size
  "Fixed WAV header size in bytes (RIFF/WAVE + fmt chunk + data chunk
  header, no extra chunks)."
  44)

#?(:clj
   (defn encode-pcm16-stereo
     "Encode interleaved stereo float samples `interleaved` (`[L R L R
     ...]`, range [-1, 1]) as 16-bit PCM stereo WAV bytes at
     `sample-rate`. Values are clamped to [-1, 1] before conversion.
     Returns a `byte[]` (JVM)."
     [interleaved sample-rate]
     (let [channels 2
           bits 16
           block-align (/ (* channels bits) 8) ; 4 bytes/frame
           byte-rate (* sample-rate block-align)
           n (count interleaved)
           data-len (* n 2) ; 2 bytes per sample
           buf (ByteBuffer/allocate (+ header-size data-len))]
       (.order buf ByteOrder/LITTLE_ENDIAN)
       (.put buf (.getBytes "RIFF" "US-ASCII"))
       (.putInt buf (int (+ 36 data-len)))
       (.put buf (.getBytes "WAVE" "US-ASCII"))
       (.put buf (.getBytes "fmt " "US-ASCII"))
       (.putInt buf (int 16))                 ; PCM fmt chunk size
       (.putShort buf (short 1))               ; audio format = PCM
       (.putShort buf (short channels))
       (.putInt buf (int sample-rate))
       (.putInt buf (int byte-rate))
       (.putShort buf (short block-align))
       (.putShort buf (short bits))
       (.put buf (.getBytes "data" "US-ASCII"))
       (.putInt buf (int data-len))
       (doseq [s interleaved]
         (let [clamped (-> s (clojure.core/max -1.0) (clojure.core/min 1.0))
               v (Math/round (* clamped (double Short/MAX_VALUE)))]
           (.putShort buf (short v))))
       (.array buf))))

#?(:cljs
   (defn encode-pcm16-stereo
     "Encode interleaved stereo float samples `interleaved` (`[L R L R
     ...]`, range [-1, 1]) as 16-bit PCM stereo WAV bytes at
     `sample-rate`. Values are clamped to [-1, 1] before conversion.
     Returns a `js/Uint8Array` (CLJS)."
     [interleaved sample-rate]
     (let [channels 2
           bits 16
           block-align (/ (* channels bits) 8)
           byte-rate (* sample-rate block-align)
           n (count interleaved)
           data-len (* n 2)
           total (+ header-size data-len)
           ab (js/ArrayBuffer. total)
           dv (js/DataView. ab)
           put-str (fn [offset s]
                     (dotimes [i (.-length s)]
                       (.setUint8 dv (+ offset i) (.charCodeAt s i))))]
       (put-str 0 "RIFF")
       (.setUint32 dv 4 (+ 36 data-len) true)
       (put-str 8 "WAVE")
       (put-str 12 "fmt ")
       (.setUint32 dv 16 16 true)
       (.setUint16 dv 20 1 true)
       (.setUint16 dv 22 channels true)
       (.setUint32 dv 24 sample-rate true)
       (.setUint32 dv 28 byte-rate true)
       (.setUint16 dv 32 block-align true)
       (.setUint16 dv 34 bits true)
       (put-str 36 "data")
       (.setUint32 dv 40 data-len true)
       (doseq [[i s] (map-indexed vector interleaved)]
         (let [clamped (-> s (clojure.core/max -1.0) (clojure.core/min 1.0))
               v (Math/round (* clamped 32767))]
           (.setInt16 dv (+ header-size (* i 2)) v true)))
       (js/Uint8Array. ab))))
