(ns flac.core
  "FLAC decoding (xiph.org's format specification) in portable `.cljc`, zero
   dependencies.

   ```clojure
   (require '[flac.core :as flac])

   (flac/flac? bytes)      ; signature sniff
   (flac/stream-info bytes) ; sample rate, channels, bit depth, total samples, MD5
   (flac/metadata bytes)   ; every metadata block, including VORBIS_COMMENT tags
   (flac/decode bytes)     ; => {:channels [[…] […]] :sample-rate … :bits …}
   (flac/encode {:channels [[…] […]] :sample-rate 44100 :bits 16})
   ```

   FLAC is lossless: `decode` returns the original integer samples, per channel,
   exactly. Samples are signed integers at the stream's own bit depth — not
   normalised — for the same reason `org-microsoft-riff` keeps them that way.

   `encode` writes FLAC too, with fixed predictors and Rice-coded residuals —
   every choice made by counting bits rather than by search. **No LPC and no
   stereo decorrelation**, which is the whole of the ratio gap against the
   reference and is stated rather than papered over.

   Bytes in are a vector of unsigned 0-255 integers."
  (:require [flac.bits :as bits]
            [flac.encode :as encode]))

(def signature [0x66 0x4c 0x61 0x43])                       ; "fLaC"

(def block-types
  {0 :stream-info 1 :padding 2 :application 3 :seek-table
   4 :vorbis-comment 5 :cuesheet 6 :picture})

(def sample-rate-codes
  {0 :from-stream-info 1 88200 2 176400 3 192000 4 8000 5 16000 6 22050
   7 24000 8 32000 9 44100 10 48000 11 96000
   12 :8-bit-khz 13 :16-bit-hz 14 :16-bit-10hz 15 :invalid})

(def ^:private bit-depth-codes
  {0 :from-stream-info 1 8 2 12 3 :reserved 4 16 5 20 6 24 7 32})

(defn flac?
  "True when `data` starts with the fLaC signature."
  [data]
  (= signature (vec (take 4 data))))

;; ---------------------------------------------------------------------------
;; Metadata
;; ---------------------------------------------------------------------------

(defn- u32le [v i]
  (+ (nth v i) (* 256 (nth v (+ i 1))) (* 65536 (nth v (+ i 2)))
     (* 16777216 (nth v (+ i 3)))))

(defn- parse-stream-info [v at]
  ;; Every read is sequenced through a `let`, never written as value expressions
  ;; inside one map literal. A map literal with more than eight entries becomes a
  ;; hash-map, and under SCI (nbb) its value forms are *not* evaluated in written
  ;; order — so a bit reader threaded through them returns fields in a shuffled
  ;; order. Measured: sample rate came back as 315, the min frame size.
  (let [r (bits/reader v at)
        min-block (bits/read-bits r 16)
        max-block (bits/read-bits r 16)
        min-frame (bits/read-bits r 24)
        max-frame (bits/read-bits r 24)
        rate (bits/read-bits r 20)
        channels (inc (bits/read-bits r 3))
        bps (inc (bits/read-bits r 5))
        total (bits/read-bits r 36)]
    {:min-block-size min-block
     :max-block-size max-block
     :min-frame-size min-frame
     :max-frame-size max-frame
     :sample-rate rate
     :channels channels
     :bits bps
     :total-samples total
     ;; the MD5 of the *decoded* samples. Recorded, not verified: there is no MD5
     ;; in this workspace, and a codec is the wrong place to add one
     :md5 (mapv #(nth v (+ at 18 %)) (range 16))}))

(defn- parse-vorbis-comment [v at len]
  (let [vendor-len (u32le v at)
        vendor-at (+ at 4)
        n-at (+ vendor-at vendor-len)
        n (u32le v n-at)]
    (loop [i 0 pos (+ n-at 4) out []]
      (if (or (= i n) (>= pos (+ at len)))
        {:vendor (apply str (map char (subvec v vendor-at n-at)))
         :comments out}
        (let [l (u32le v pos)
              s (apply str (map char (subvec v (+ pos 4) (+ pos 4 l))))]
          (recur (inc i) (+ pos 4 l) (conj out s)))))))

(defn metadata
  "Every metadata block → `[{:type :stream-info :last? false :length n …} …]`.

   STREAMINFO and VORBIS_COMMENT are parsed; the rest are reported with their
   type, offset and length so a caller can read them without this repo having to
   understand PICTURE or CUESHEET."
  [data]
  (let [v (vec data)]
    (when-not (flac? v)
      (throw (ex-info "flac: no fLaC signature"
                      {:reason :not-flac :saw (vec (take 4 v))})))
    (loop [pos 4 out []]
      (when (> (+ pos 4) (count v))
        (throw (ex-info "flac: truncated metadata block header"
                        {:reason :truncated :offset pos})))
      (let [b0 (nth v pos)
            last? (>= b0 128)
            type-id (mod b0 128)
            len (+ (* 65536 (nth v (+ pos 1))) (* 256 (nth v (+ pos 2))) (nth v (+ pos 3)))
            at (+ pos 4)
            _ (when (> (+ at len) (count v))
                (throw (ex-info "flac: metadata block runs past the end"
                                {:reason :truncated :offset at :length len})))
            kind (get block-types type-id :unknown)
            block (cond-> {:type kind :type-id type-id :last? last?
                           :offset at :length len}
                    (= kind :stream-info) (merge (parse-stream-info v at))
                    (= kind :vorbis-comment) (merge (parse-vorbis-comment v at len)))
            out (conj out block)]
        (if last? out (recur (+ at len) out))))))

(defn stream-info
  "The STREAMINFO block, which every FLAC stream must open with."
  [data]
  (let [blocks (metadata data)
        si (first blocks)]
    (when-not (= :stream-info (:type si))
      (throw (ex-info "flac: first metadata block is not STREAMINFO"
                      {:reason :bad-metadata :type (:type si)})))
    si))

(defn- audio-offset
  "Where the frames begin: just past the last metadata block."
  [data]
  (let [last-block (last (metadata data))]
    (+ (:offset last-block) (:length last-block))))

;; ---------------------------------------------------------------------------
;; Subframes
;; ---------------------------------------------------------------------------

(def ^:private fixed-coefficients
  ;; the four fixed predictors, as their difference equations
  {0 [] 1 [1] 2 [2 -1] 3 [3 -3 1] 4 [4 -6 4 -1]})

(defn- read-residual
  "The Rice-coded residual for `n` samples after `order` warmup values."
  [r block-size order]
  (let [method (bits/read-bits r 2)
        param-bits (case method
                     0 4
                     1 5
                     (throw (ex-info "flac: reserved residual coding method"
                                     {:reason :unsupported :method method})))
        escape (dec (bits/pow2 param-bits))
        partition-order (bits/read-bits r 4)
        partitions (bits/pow2 partition-order)]
    (when-not (zero? (rem block-size partitions))
      (throw (ex-info "flac: block size is not divisible by the partition count"
                      {:reason :bad-residual :block-size block-size
                       :partitions partitions})))
    (loop [p 0 out (transient [])]
      (if (= p partitions)
        (persistent! out)
        (let [n (if (zero? p)
                  (- (quot block-size partitions) order)
                  (quot block-size partitions))
              param (bits/read-bits r param-bits)]
          (when (neg? n)
            (throw (ex-info "flac: first partition is smaller than the predictor order"
                            {:reason :bad-residual :order order})))
          (if (= param escape)
            ;; escape: the partition is stored raw at a fixed width
            (let [width (bits/read-bits r 5)]
              (recur (inc p)
                     (loop [i 0 acc out]
                       (if (= i n) acc (recur (inc i) (conj! acc (bits/read-signed r width)))))))
            (recur (inc p)
                   (loop [i 0 acc out]
                     (if (= i n)
                       acc
                       (let [q (bits/read-unary r)
                             rem' (bits/read-bits r param)
                             ;; zigzag: the low bit is the sign
                             u (+ (* q (bits/pow2 param)) rem')]
                         (recur (inc i)
                                (conj! acc (if (odd? u)
                                             (- (- (quot (dec u) 2)) 1)
                                             (quot u 2))))))))))))))

(defn- restore-linear
  "Undo a fixed or LPC prediction: `warmup` plus residual, folded through the
   coefficients with `shift`."
  [warmup residual coefficients shift]
  (let [order (count warmup)]
    (loop [i 0 out (transient (vec warmup))]
      (if (= i (count residual))
        (persistent! out)
        (let [pred (loop [k 0 acc 0]
                     (if (= k order)
                       acc
                       (recur (inc k)
                              (+ acc (* (nth coefficients k)
                                        (nth out (- (+ order i) k 1)))))))]
          (recur (inc i)
                 (conj! out (+ (nth residual i)
                               (if (zero? shift)
                                 pred
                                 (bits/floor-div pred (bits/pow2 shift)))))))))))

(defn- read-subframe
  "One subframe → a vector of `block-size` samples at `bps` bits."
  [r block-size bps]
  (when-not (zero? (bits/read-bit r))
    (throw (ex-info "flac: subframe padding bit is not zero"
                    {:reason :bad-subframe})))
  (let [type-code (bits/read-bits r 6)
        wasted (if (zero? (bits/read-bit r))
                 0
                 ;; unary-coded count of low zero bits removed from every sample
                 (inc (bits/read-unary r)))
        bps (- bps wasted)
        samples
        (cond
          (zero? type-code)                                 ; CONSTANT
          (let [x (bits/read-signed r bps)] (vec (repeat block-size x)))

          (= 1 type-code)                                   ; VERBATIM
          (mapv (fn [_] (bits/read-signed r bps)) (range block-size))

          (and (>= type-code 8) (<= type-code 12))          ; FIXED, order 0-4
          (let [order (- type-code 8)
                warmup (mapv (fn [_] (bits/read-signed r bps)) (range order))
                residual (read-residual r block-size order)]
            (restore-linear warmup residual (get fixed-coefficients order) 0))

          (>= type-code 32)                                 ; LPC, order 1-32
          (let [order (- type-code 31)
                warmup (mapv (fn [_] (bits/read-signed r bps)) (range order))
                precision (inc (bits/read-bits r 4))
                _ (when (= precision 16)
                    (throw (ex-info "flac: reserved LPC coefficient precision"
                                    {:reason :bad-subframe})))
                shift (bits/read-signed r 5)
                _ (when (neg? shift)
                    (throw (ex-info "flac: negative LPC shift"
                                    {:reason :bad-subframe :shift shift})))
                coefficients (mapv (fn [_] (bits/read-signed r precision)) (range order))
                residual (read-residual r block-size order)]
            (restore-linear warmup residual coefficients shift))

          :else
          (throw (ex-info "flac: reserved subframe type"
                          {:reason :unsupported :type-code type-code})))]
    (if (zero? wasted)
      samples
      (mapv #(* % (bits/pow2 wasted)) samples))))

;; ---------------------------------------------------------------------------
;; Frames
;; ---------------------------------------------------------------------------

(defn- read-frame
  "One frame → `{:channels [[…] …] :block-size n :end byte-offset}`."
  [v pos si]
  (let [r (bits/reader v pos)
        sync (bits/read-bits r 14)]
    (when-not (= 0x3ffe sync)
      (throw (ex-info "flac: frame sync code not found"
                      {:reason :bad-frame-header :offset pos :sync sync})))
    (when-not (zero? (bits/read-bit r))
      (throw (ex-info "flac: reserved frame header bit is set"
                      {:reason :bad-frame-header :offset pos})))
    (let [variable? (= 1 (bits/read-bit r))
          bs-code (bits/read-bits r 4)
          sr-code (bits/read-bits r 4)
          ch-code (bits/read-bits r 4)
          bps-code (bits/read-bits r 3)
          _ (when-not (zero? (bits/read-bit r))
              (throw (ex-info "flac: reserved frame header bit is set"
                              {:reason :bad-frame-header})))
          _ (bits/read-utf8-number r)                       ; frame or sample number
          block-size (case bs-code
                       0 (throw (ex-info "flac: reserved block size code"
                                         {:reason :bad-frame-header}))
                       1 192
                       (2 3 4 5) (* 576 (bits/pow2 (- bs-code 2)))
                       6 (inc (bits/read-bits r 8))
                       7 (inc (bits/read-bits r 16))
                       (* 256 (bits/pow2 (- bs-code 8))))
          _ (case sr-code
              12 (bits/read-bits r 8)
              (13 14) (bits/read-bits r 16)
              15 (throw (ex-info "flac: invalid sample rate code"
                                 {:reason :bad-frame-header}))
              nil)
          bps (let [b (get bit-depth-codes bps-code)]
                (cond (= b :from-stream-info) (:bits si)
                      (= b :reserved) (throw (ex-info "flac: reserved bit depth code"
                                                      {:reason :bad-frame-header}))
                      :else b))
          _ (bits/read-bits r 8)                            ; header CRC-8
          ;; 0-7 are independent channels; 8/9/10 are the stereo decorrelations
          n-channels (if (<= ch-code 7) (inc ch-code) 2)
          _ (when (> ch-code 10)
              (throw (ex-info "flac: reserved channel assignment"
                              {:reason :bad-frame-header :assignment ch-code})))
          subframes (mapv (fn [ch]
                            ;; the side channel of a decorrelated pair carries one
                            ;; extra bit, because a difference needs the range
                            (read-subframe r block-size
                                           (+ bps (case ch-code
                                                    8 (if (= ch 1) 1 0)
                                                    9 (if (= ch 0) 1 0)
                                                    10 (if (= ch 1) 1 0)
                                                    0))))
                          (range n-channels))
          channels (case ch-code
                     8 (let [[l s] subframes] [l (mapv - l s)])          ; left/side
                     9 (let [[s rgt] subframes] [(mapv + rgt s) rgt])    ; right/side
                     ;; mid/side: the mid channel carries a dropped low bit that
                     ;; the side channel's parity restores
                     10 (let [[m s] subframes
                              mid (mapv (fn [mi si']
                                          (let [m2 (+ (* 2 mi) (mod si' 2))]
                                            (quot (+ m2 si') 2)))
                                        m s)
                              side (mapv (fn [mi si']
                                           (let [m2 (+ (* 2 mi) (mod si' 2))]
                                             (quot (- m2 si') 2)))
                                         m s)]
                          [mid side])
                     subframes)]
      (bits/align! r)
      (bits/read-bits r 16)                                 ; frame CRC-16
      {:channels channels
       :block-size block-size
       :variable-blocking? variable?
       :end (quot (bits/bit-pos r) 8)})))

(defn decode
  "Decode every frame → `{:channels [[…] […]] :sample-rate n :bits n :samples n}`.

   Samples are signed integers at the stream's own bit depth, per channel."
  ([data] (decode data {}))
  ([data {:keys [max-samples] :or {max-samples 100000000}}]
   (let [v (vec data)
         si (stream-info v)
         start (audio-offset v)
         n (count v)]
     (loop [pos start acc (mapv (fn [_] (transient [])) (range (:channels si))) total 0]
       (if (or (>= pos n)
               ;; a stream that declares its length stops there; the bytes after
               ;; the last frame may be padding rather than another frame
               (and (pos? (:total-samples si)) (>= total (:total-samples si))))
         {:channels (mapv persistent! acc)
          :sample-rate (:sample-rate si)
          :bits (:bits si)
          :channel-count (:channels si)
          :samples total
          :md5 (:md5 si)}
         (let [f (read-frame v pos si)
               total' (+ total (:block-size f))]
           (when (> total' max-samples)
             (throw (ex-info "flac: more samples than :max-samples allows"
                             {:reason :output-too-large :samples total'})))
           (recur (:end f)
                  (mapv (fn [a ch] (reduce conj! a ch)) acc (:channels f))
                  total')))))))

(def encode
  "Encode signed-integer samples into a FLAC stream. See `flac.encode/encode`."
  encode/encode)
