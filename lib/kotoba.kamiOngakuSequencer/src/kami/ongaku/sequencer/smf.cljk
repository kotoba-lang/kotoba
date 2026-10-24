(ns kami.ongaku.sequencer.smf
  "Standard MIDI File (SMF, .mid) Format 1 encode/decode — the MusicXML-
   equivalent interchange contract for kami.ongaku.sequencer.

   Operates entirely on plain vectors of ints 0-255 (\"byte vectors\"), not
   platform byte-array/Uint8Array types, so the whole namespace is 100%
   portable .cljc with zero reader-conditional branches. Converting to/from
   an actual file (java.io byte[] on the JVM, a Blob/Uint8Array in the
   browser) is deliberately left to thin host-specific glue outside this ns.

   Track 0 is always the conductor track (tempo + time signature meta events
   only, tick 0). Tracks 1..N carry one kami.ongaku.sequencer/flatten-track
   result each. Only note/cc/pitch-bend/aftertouch/channel-aftertouch are
   round-tripped; other MIDI event types (program change, sysex, unknown meta)
   are safely skipped on import rather than erroring."
  (:require [kami.ongaku.sequencer :as sq]))

;; ---------------------------------------------------------------------------
;; constants

(def ^:private mthd-tag [0x4D 0x54 0x68 0x64])
(def ^:private mtrk-tag [0x4D 0x54 0x72 0x6B])

;; ---------------------------------------------------------------------------
;; small portable helpers

(defn- subvec* [bytes start len]
  (vec (take len (drop start bytes))))

(defn- u16 [bytes offset]
  (+ (* 256 (nth bytes offset)) (nth bytes (inc offset))))

(defn- u32 [bytes offset]
  (reduce (fn [acc i] (+ (* acc 256) (nth bytes (+ offset i)))) 0 (range 4)))

(defn- be16 [n] [(bit-and (bit-shift-right n 8) 0xFF) (bit-and n 0xFF)])
(defn- be32 [n] [(bit-and (bit-shift-right n 24) 0xFF) (bit-and (bit-shift-right n 16) 0xFF)
                 (bit-and (bit-shift-right n 8) 0xFF) (bit-and n 0xFF)])

;; ---------------------------------------------------------------------------
;; variable-length quantity (delta-time encoding)

(defn vlq-encode [n]
  (loop [buf (list (bit-and n 0x7F))
         rem (bit-shift-right n 7)]
    (if (pos? rem)
      (recur (cons (bit-or 0x80 (bit-and rem 0x7F)) buf) (bit-shift-right rem 7))
      (vec buf))))

(defn vlq-decode
  "Returns [value next-offset]."
  [bytes offset]
  (loop [value 0 pos offset]
    (let [b (nth bytes pos)]
      (if (zero? (bit-and b 0x80))
        [(bit-or (bit-shift-left value 7) b) (inc pos)]
        (recur (bit-or (bit-shift-left value 7) (bit-and b 0x7F)) (inc pos))))))

;; ---------------------------------------------------------------------------
;; IR event -> raw {:tick :bytes} (no delta-time yet, no channel packing order issues)

(defn- note->raw [{:keys [pitch velocity tick duration-ticks channel]}]
  [{:tick tick :bytes [(bit-or 0x90 channel) pitch velocity]}
   {:tick (+ tick duration-ticks) :bytes [(bit-or 0x80 channel) pitch 0]}])

(defn- cc->raw [{:keys [controller value tick channel]}]
  [{:tick tick :bytes [(bit-or 0xB0 channel) controller value]}])

(defn- pitch-bend->raw [{:keys [value tick channel]}]
  (let [v (+ value 8192)]
    [{:tick tick :bytes [(bit-or 0xE0 channel) (bit-and v 0x7F) (bit-and (bit-shift-right v 7) 0x7F)]}]))

(defn- aftertouch->raw [{:keys [pitch value tick channel]}]
  [{:tick tick :bytes [(bit-or 0xA0 channel) pitch value]}])

(defn- channel-aftertouch->raw [{:keys [value tick channel]}]
  [{:tick tick :bytes [(bit-or 0xD0 channel) value]}])

(defn- event->raw [{:keys [type] :as ev}]
  (case type
    :note (note->raw ev)
    :cc (cc->raw ev)
    :pitch-bend (pitch-bend->raw ev)
    :aftertouch (aftertouch->raw ev)
    :channel-aftertouch (channel-aftertouch->raw ev)
    (throw (ex-info "unsupported event :type for SMF export" {:event ev}))))

(defn- raw-priority
  "Note-offs sort before other events at the same tick, so a note never
   appears to overlap itself when a new note-on lands on the same tick."
  [{:keys [bytes]}]
  (if (= 0x80 (bit-and (first bytes) 0xF0)) 0 1))

(defn- encode-track-events [raw-events]
  (let [sorted (sort-by (juxt :tick raw-priority) raw-events)]
    (loop [evs sorted prev-tick 0 out []]
      (if (empty? evs)
        (into out [0x00 0xFF 0x2F 0x00]) ;; delta 0, end-of-track meta
        (let [{:keys [tick bytes]} (first evs)]
          (recur (rest evs) tick (-> out (into (vlq-encode (- tick prev-tick))) (into bytes))))))))

(defn- track-chunk [track-data]
  (into (into [] (concat mtrk-tag (be32 (count track-data)))) track-data))

(defn- tempo-meta-bytes [bpm]
  (let [micros (long (/ 60000000 bpm))]
    (into [0xFF 0x51 0x03]
          [(bit-and (bit-shift-right micros 16) 0xFF)
           (bit-and (bit-shift-right micros 8) 0xFF)
           (bit-and micros 0xFF)])))

(defn- time-sig-meta-bytes [numerator denominator]
  (let [exp (loop [d denominator e 0] (if (<= d 1) e (recur (quot d 2) (inc e))))]
    [0xFF 0x58 0x04 numerator exp 24 8]))

;; ---------------------------------------------------------------------------
;; export

(defn- track->raw [{:keys [events channel] :or {channel 0}}]
  (mapcat event->raw (map #(update % :channel (fn [c] (or c channel))) events)))

(defn export-smf
  "flat-tracks: [{:channel n :events [event...]} ...] — the shape produced by
   kami.ongaku.sequencer/flatten-track (one per SMF track, in order).
   Returns a byte vector (Format 1: track 0 = conductor, tracks 1..N = notes)."
  [{:keys [ppq bpm time-signature tracks]
    :or {ppq sq/default-ppq bpm 120 time-signature [4 4]}}]
  (let [[num denom] time-signature
        conductor-chunk (track-chunk
                          (encode-track-events
                           [{:tick 0 :bytes (tempo-meta-bytes bpm)}
                            {:tick 0 :bytes (time-sig-meta-bytes num denom)}]))
        track-chunks (mapv (fn [trk] (track-chunk (encode-track-events (track->raw trk)))) tracks)
        ntrks (inc (count track-chunks))
        header (into [] (concat mthd-tag [0x00 0x00 0x00 0x06] [0x00 0x01] (be16 ntrks) (be16 ppq)))]
    (into [] (concat header conductor-chunk (apply concat track-chunks)))))

;; ---------------------------------------------------------------------------
;; import

(defn- status-data-length [status]
  (let [hi (bit-and status 0xF0)]
    (if (or (= hi 0xC0) (= hi 0xD0)) 1 2)))

(defn- parse-track-events
  "Parses one MTrk chunk's data bytes (start inclusive, end exclusive) into
   wire events: {:tick abs-tick :kind :meta|:midi ...}. Handles MIDI running
   status."
  [bytes start end]
  (loop [pos start abs-tick 0 running-status nil out []]
    (if (>= pos end)
      out
      (let [[delta pos1] (vlq-decode bytes pos)
            tick (+ abs-tick delta)
            b (nth bytes pos1)]
        (cond
          (= b 0xFF)
          (let [meta-type (nth bytes (inc pos1))
                [len pos2] (vlq-decode bytes (+ pos1 2))
                data (subvec* bytes pos2 len)]
            (recur (+ pos2 len) tick nil (conj out {:tick tick :kind :meta :meta-type meta-type :data data})))

          (or (= b 0xF0) (= b 0xF7))
          (let [[len pos2] (vlq-decode bytes (inc pos1))]
            (recur (+ pos2 len) tick nil out))

          (>= b 0x80)
          (let [status b
                n (status-data-length status)
                data (subvec* bytes (inc pos1) n)]
            (recur (+ pos1 1 n) tick status (conj out {:tick tick :kind :midi :status status :data data})))

          :else
          (let [status running-status
                n (status-data-length status)
                data (subvec* bytes pos1 n)]
            (recur (+ pos1 n) tick status (conj out {:tick tick :kind :midi :status status :data data}))))))))

(defn- parse-track-chunk [bytes offset]
  (assert (= (subvec* bytes offset 4) mtrk-tag) "expected MTrk chunk")
  (let [len (u32 bytes (+ offset 4))
        data-start (+ offset 8)
        data-end (+ data-start len)]
    {:events (parse-track-events bytes data-start data-end)
     :next-offset data-end}))

(defn- note-off [acc channel pitch off-tick]
  (let [k [channel pitch]
        q (get-in acc [:pending k] [])]
    (if (empty? q)
      acc ;; stray note-off with no matching note-on: ignore
      (let [{:keys [tick velocity]} (first q)]
        (-> acc
            (assoc-in [:pending k] (subvec q 1))
            (update :ir-events conj {:type :note :pitch pitch :velocity velocity
                                      :tick tick :duration-ticks (- off-tick tick) :channel channel}))))))

(defn- wire->ir
  "Reduces one track's wire events into {:ir-events [...] :tempo bpm-or-nil
   :time-sig [n d]-or-nil}. Note-on/off pairing is per (channel, pitch), FIFO,
   scoped to this track only."
  [wire-events]
  (let [{:keys [ir-events tempo time-sig]}
        (reduce
         (fn [acc {:keys [tick kind status meta-type data]}]
           (cond
             (= kind :meta)
             (cond
               (= meta-type 0x51) (assoc acc :tempo (long (+ 0.5 (/ 60000000.0 (+ (* 65536 (nth data 0)) (* 256 (nth data 1)) (nth data 2))))))
               (= meta-type 0x58) (assoc acc :time-sig [(nth data 0) (bit-shift-left 1 (nth data 1))])
               :else acc)

             (= kind :midi)
             (let [hi (bit-and status 0xF0)
                   channel (bit-and status 0x0F)]
               (case hi
                 0x90 (let [[pitch velocity] data]
                        (if (zero? velocity)
                          (note-off acc channel pitch tick)
                          (update-in acc [:pending [channel pitch]] (fnil conj []) {:tick tick :velocity velocity})))
                 0x80 (let [[pitch] data] (note-off acc channel pitch tick))
                 0xB0 (let [[ctrl val] data] (update acc :ir-events conj {:type :cc :controller ctrl :value val :tick tick :channel channel}))
                 0xE0 (let [[lsb msb] data] (update acc :ir-events conj {:type :pitch-bend :value (- (+ (bit-shift-left msb 7) lsb) 8192) :tick tick :channel channel}))
                 0xA0 (let [[pitch val] data] (update acc :ir-events conj {:type :aftertouch :pitch pitch :value val :tick tick :channel channel}))
                 0xD0 (let [[val] data] (update acc :ir-events conj {:type :channel-aftertouch :value val :tick tick :channel channel}))
                 acc))

             :else acc))
         {:ir-events [] :pending {} :tempo nil :time-sig nil}
         wire-events)]
    {:ir-events ir-events :tempo tempo :time-sig time-sig}))

(defn import-smf
  "Inverse of export-smf: byte vector -> {:ppq :bpm :time-signature
   :tracks [{:channel :events} ...]}. Tracks that yield zero channel-voice
   events (pure conductor/meta tracks) are dropped from :tracks; their
   tempo/time-signature meta is merged into the top-level result instead."
  [bytes]
  (assert (= (subvec* bytes 0 4) mthd-tag) "not an SMF file (missing MThd)")
  (let [hdr-len (u32 bytes 4)
        n-tracks (u16 bytes 10)
        ppq (u16 bytes 12)
        header-end (+ 8 hdr-len)]
    (loop [idx 0 pos header-end acc-bpm 120 acc-time-sig [4 4] tracks []]
      (if (>= idx n-tracks)
        {:ppq ppq :bpm acc-bpm :time-signature acc-time-sig :tracks tracks}
        (let [{:keys [events next-offset]} (parse-track-chunk bytes pos)
              {:keys [ir-events tempo time-sig]} (wire->ir events)
              channel (if (seq ir-events) (:channel (first ir-events)) 0)]
          (recur (inc idx) next-offset
                 (or tempo acc-bpm)
                 (or time-sig acc-time-sig)
                 (cond-> tracks (seq ir-events) (conj {:channel channel :events (vec (sort-by :tick ir-events))}))))))))
