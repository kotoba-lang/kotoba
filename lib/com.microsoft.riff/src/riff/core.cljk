(ns riff.core
  "RIFF containers and WAVE audio (Microsoft/IBM `RIFF` + `WAVE`), both
   directions, in portable `.cljc` with no dependencies.

   ```clojure
   (require '[riff.core :as riff])

   (riff/chunks bytes)     ; every chunk: id, offset, size
   (riff/parse bytes)      ; => {:format :pcm :channels 2 :sample-rate 44100
                           ;     :bits 16 :frames 1024 :data-offset n :data-size n}
   (riff/samples bytes)    ; => [[ch0 …] [ch1 …]] deinterleaved
   (riff/build {:channels [[…] […]] :sample-rate 44100 :bits 16})
   ```

   RIFF is a chunk container, not an audio format: `WAVE` is one form of it and
   `AVI`/`WEBP` are others, so `chunks` is useful on its own. What this repo
   decodes is **uncompressed PCM and IEEE float**; every compressed WAVE codec
   (ADPCM, mu-law, A-law, MP3-in-WAV, GSM) is refused by name rather than handed
   back as if it were samples.

   Bytes in and out are vectors of unsigned 0-255 integers. Samples are signed
   integers for PCM and doubles for float, matching what the file actually holds
   — a library that silently normalised everything to [-1,1] would make a
   bit-exact round trip impossible."
  (:require [riff.bytes :as b]))

;; ---------------------------------------------------------------------------
;; Chunks
;; ---------------------------------------------------------------------------

(def ^:private riff-id "RIFF")

(defn riff?
  "True when `data` starts with a RIFF header."
  [data]
  (let [v (vec (take 4 data))]
    (= (b/->fourcc riff-id) v)))

(defn chunks
  "Walk the chunks of a RIFF file →
   `{:form \"WAVE\" :chunks [{:id \"fmt \" :offset n :size n} …]}`.

   Every chunk is padded to an even length, and **the pad byte is not part of the
   chunk's size** — a walker that forgets it drifts by one byte per odd chunk and
   then reads garbage ids."
  [data]
  (let [v (vec data)
        n (count v)]
    (when (< n 12)
      (throw (ex-info "riff: shorter than a RIFF header" {:reason :truncated :size n})))
    (when-not (riff?  v)
      (throw (ex-info "riff: no RIFF signature"
                      {:reason :not-riff :saw (b/fourcc v 0)})))
    (let [declared (b/u32 v 4)
          form (b/fourcc v 8)]
      {:form form
       :declared-size declared
       :chunks
       (loop [pos 12 out []]
         (if (> (+ pos 8) n)
           out
           (let [id (b/fourcc v pos)
                 size (b/u32 v (+ pos 4))
                 start (+ pos 8)]
             (when (> (+ start size) n)
               (throw (ex-info "riff: chunk runs past the end of the file"
                               {:reason :truncated :chunk id :offset pos
                                :size size :available (- n start)})))
             (recur (+ start size (if (odd? size) 1 0))
                    (conj out {:id id :offset start :size size})))))})))

(defn chunk-named
  "The first chunk with `id`, or nil."
  [parsed id]
  (first (filter #(= id (:id %)) (:chunks parsed))))

;; ---------------------------------------------------------------------------
;; WAVE format
;; ---------------------------------------------------------------------------

(def format-tags
  "WAVE format tags, including the ones this repo refuses."
  {0x0001 :pcm
   0x0003 :float
   0x0006 :a-law
   0x0007 :mu-law
   0x0002 :ms-adpcm
   0x0011 :ima-adpcm
   0x0031 :gsm-610
   0x0055 :mp3
   0xfffe :extensible})

;; WAVE_FORMAT_EXTENSIBLE carries the real tag in a GUID whose first two bytes
;; are the tag and whose remainder is a fixed suffix.
(def ^:private guid-suffix
  [0x00 0x00 0x00 0x00 0x10 0x00 0x80 0x00 0x00 0xaa 0x00 0x38 0x9b 0x71])

(defn- resolve-extensible
  "The effective format of an extensible fmt chunk, from its SubFormat GUID."
  [v fmt-at fmt-size]
  (when (< fmt-size 40)
    (throw (ex-info "riff: extensible fmt chunk is too short for a SubFormat GUID"
                    {:reason :bad-fmt :size fmt-size})))
  (let [guid-at (+ fmt-at 24)
        tag (b/u16 v guid-at)
        suffix (vec (subvec v (+ guid-at 2) (+ guid-at 16)))]
    (when-not (= suffix guid-suffix)
      (throw (ex-info "riff: unrecognised SubFormat GUID"
                      {:reason :unsupported-format :guid suffix})))
    (get format-tags tag :unknown)))

(defn parse
  "Header information for a WAVE file. Does not decode samples — see `samples`.

       {:form :format :format-tag :channels :sample-rate :bits :block-align
        :byte-rate :frames :data-offset :data-size :chunk-ids}"
  [data]
  (let [v (vec data)
        parsed (chunks v)]
    (when-not (= "WAVE" (:form parsed))
      (throw (ex-info "riff: not a WAVE file"
                      {:reason :not-wave :form (:form parsed)})))
    (let [fmt (or (chunk-named parsed "fmt ")
                  (throw (ex-info "riff: no fmt chunk" {:reason :bad-fmt})))
          data-chunk (or (chunk-named parsed "data")
                         (throw (ex-info "riff: no data chunk" {:reason :no-data})))
          at (:offset fmt)
          _ (when (< (:size fmt) 16)
              (throw (ex-info "riff: fmt chunk shorter than 16 bytes"
                              {:reason :bad-fmt :size (:size fmt)})))
          tag (b/u16 v at)
          declared (get format-tags tag :unknown)
          format (if (= declared :extensible)
                   (resolve-extensible v at (:size fmt))
                   declared)
          channels (b/u16 v (+ at 2))
          sample-rate (b/u32 v (+ at 4))
          byte-rate (b/u32 v (+ at 8))
          block-align (b/u16 v (+ at 12))
          bits (b/u16 v (+ at 14))]
      (when-not (contains? #{:pcm :float} format)
        (throw (ex-info (str "riff: unsupported WAVE format: " (name format))
                        {:reason :unsupported-format :format format :format-tag tag})))
      (when (zero? channels)
        (throw (ex-info "riff: zero channels" {:reason :bad-fmt})))
      (when-not (contains? #{8 16 24 32 64} bits)
        (throw (ex-info (str "riff: unsupported sample width: " bits)
                        {:reason :unsupported-format :bits bits})))
      (when (and (= format :float) (not (contains? #{32 64} bits)))
        (throw (ex-info "riff: IEEE float samples must be 32 or 64 bits"
                        {:reason :bad-fmt :bits bits})))
      (let [frame-bytes (* channels (quot bits 8))]
        {:form "WAVE"
         :format format
         :format-tag tag
         :extensible? (= declared :extensible)
         :channels channels
         :sample-rate sample-rate
         :byte-rate byte-rate
         :block-align block-align
         :bits bits
         ;; the data chunk's declared size is authoritative, not the file length
         :frames (quot (:size data-chunk) frame-bytes)
         :data-offset (:offset data-chunk)
         :data-size (:size data-chunk)
         :frame-bytes frame-bytes
         :chunk-ids (mapv :id (:chunks parsed))}))))

(defn samples
  "Deinterleave a WAVE file's samples → a vector of one vector per channel.

   PCM comes back as signed integers at the file's own width, except 8-bit, which
   the format stores **unsigned with a 128 bias** — the one place in WAVE where
   sample sign flips with width. Float comes back as doubles."
  [data]
  (let [v (vec data)
        {:keys [format channels bits data-offset data-size]} (parse v)
        width (quot bits 8)
        frame (* channels width)
        n-frames (quot data-size frame)
        read-one (case [format bits]
                   [:pcm 8] (fn [i] (- (b/u8 v i) 128))
                   [:pcm 16] (fn [i] (b/i16 v i))
                   [:pcm 24] (fn [i] (b/i24 v i))
                   [:pcm 32] (fn [i] (b/i32 v i))
                   [:float 32] (fn [i] (b/f32 v i))
                   [:float 64] (fn [i] (b/f64 v i))
                   (throw (ex-info "riff: no reader for this format and width"
                                   {:reason :unsupported-format :format format :bits bits})))]
    (mapv (fn [ch]
            (mapv (fn [f] (read-one (+ data-offset (* f frame) (* ch width))))
                  (range n-frames)))
          (range channels))))

;; ---------------------------------------------------------------------------
;; Writing
;; ---------------------------------------------------------------------------

(defn- chunk-bytes
  "One chunk with its header and, if the payload is odd, its pad byte."
  [id payload]
  (let [p (vec payload)]
    (into (into (b/->fourcc id) (b/put-u32 (count p)))
          (if (odd? (count p)) (conj p 0) p))))

(defn build
  "Assemble a WAVE file → a vector of unsigned bytes.

       (build {:channels [[…] […]] :sample-rate 44100 :bits 16 :format :pcm})

   `:channels` is one vector of samples per channel, all the same length.
   `:format` is `:pcm` (default) or `:float`; `:bits` is 8/16/24/32 for PCM and
   32/64 for float.

   Output is **reproducible**: no timestamps, no encoder tag, nothing but the
   samples decides the bytes. WAVE_FORMAT_EXTENSIBLE is used only when asked for
   (`:extensible? true`), since a plain fmt chunk is what every reader handles."
  [{:keys [channels sample-rate bits format extensible?]
    :or {sample-rate 44100 bits 16 format :pcm}}]
  (let [chs (mapv vec channels)
        n-ch (count chs)]
    (when (zero? n-ch)
      (throw (ex-info "riff: no channels" {:reason :bad-fmt})))
    (when (apply not= (map count chs))
      (throw (ex-info "riff: channels have different lengths"
                      {:reason :bad-fmt :lengths (mapv count chs)})))
    (when-not (contains? #{:pcm :float} format)
      (throw (ex-info (str "riff: cannot write " (name format))
                      {:reason :unsupported-format :format format})))
    (when-not (if (= format :float) (contains? #{32 64} bits) (contains? #{8 16 24 32} bits))
      (throw (ex-info (str "riff: cannot write " bits "-bit " (name format))
                      {:reason :unsupported-format :bits bits :format format})))
    (let [width (quot bits 8)
          n-frames (count (first chs))
          put-one (case [format bits]
                    [:pcm 8] (fn [x] [(bit-and (+ x 128) 0xff)])
                    [:pcm 16] b/put-i16
                    [:pcm 24] b/put-i24
                    [:pcm 32] b/put-i32
                    [:float 32] b/put-f32
                    [:float 64] b/put-f64)
          tag (cond extensible? 0xfffe (= format :float) 0x0003 :else 0x0001)
          block-align (* n-ch width)
          fmt-body (into (into (into (into (into (b/put-u16 tag) (b/put-u16 n-ch))
                                           (b/put-u32 sample-rate))
                                     (b/put-u32 (* sample-rate block-align)))
                               (b/put-u16 block-align))
                         (b/put-u16 bits))
          fmt-body (if extensible?
                     (into (into (into fmt-body (b/put-u16 22))    ; cbSize
                                 (into (b/put-u16 bits) (b/put-u32 0)))  ; validBits, mask
                           (into (b/put-u16 (if (= format :float) 0x0003 0x0001))
                                 guid-suffix))
                     fmt-body)
          audio (loop [f 0 out (transient [])]
                  (if (= f n-frames)
                    (persistent! out)
                    (recur (inc f)
                           (loop [c 0 out out]
                             (if (= c n-ch)
                               out
                               (recur (inc c)
                                      (reduce conj! out (put-one (nth (nth chs c) f)))))))))
          body (into (into (b/->fourcc "WAVE") (chunk-bytes "fmt " fmt-body))
                     (chunk-bytes "data" audio))]
      (into (into (b/->fourcc riff-id) (b/put-u32 (count body))) body))))
