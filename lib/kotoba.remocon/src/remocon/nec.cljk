(ns remocon.nec
  "NEC-family IR protocol: frame decode from raw burst to bits, and the
  repeat-frame recognition.

  NEC (and NEC1) encodes a 32-bit frame: 8-bit address, 8-bit inverted
  address, 8-bit command, 8-bit inverted command. Logical values are carried
  by mark duration relative to the frame's own 560us unit tick (measured,
  not assumed): a short mark (~1 tick) = logical 0, a long mark (~3 ticks) =
  logical 1, with fixed 1-tick spaces between bits.

  The decoder derives the tick from the burst itself (median of bit-space
  gaps), so a receiver's clock skew does not break decode. A repeat frame is
  a single ~9ms mark + ~2.25ms space + 560us mark stop bit, carrying no data.

  Fails closed: any violation throws with a :remocon.error/... code."

  (:require [remocon.raw :as raw]))

(def ^:const ^:long lead-mark-us 9000)
(def ^:const ^:long lead-space-us 4500)
(def ^:const ^:long repeat-space-us 2250)
(def ^:const ^:long bit-space-us 560)
(def ^:const ^:long stop-mark-us 560)

(defn- with-tick
  [burst]
  (let [pairs (partition 2 burst)
        body (drop 1 (drop-last 1 pairs))          ; drop the lead and [stop trailing-gap] pairs
        ;; the last pair of an NEC frame is [stop-mark trailing-gap]; body
        ;; pairs are the 32 bit pairs, each [mark space]. The tick is the
        ;; MINIMUM body mark (the logical-0 mark), not the median — a frame
        ;; dominated by 1-bits would push a median past 3 ticks.
        marks (mapv (comp second first) body)
        tick (or (and (seq marks) (apply min marks)) bit-space-us)]
    {:tick tick :pairs pairs}))

(defn tick-of
  "The frame's unit tick in us — derived, not assumed."
  [burst]
  (let [{:keys [tick]} (with-tick burst)]
    tick))

(defn- decode-bits
  [pairs tick]
  (reduce
   (fn [acc [m _s]]
     (let [mk (second m)]
       (cond
         ;; logical 0: mark ~1 tick; logical 1: mark ~3 ticks. Tolerance is
         ;; one tick wide either way — receiver clocks are not lab clocks.
         (< mk (* 2 tick)) (conj acc 0)
         (< mk (* 4 tick)) (conj acc 1)
         :else (throw (ex-info "NEC bit mark is neither 1 nor 3 ticks"
                               {:remocon.error :remocon.error/bit-mark
                                :mark-us mk :tick tick})))))
   []
   (->> pairs (drop 1) (drop-last 1))))             ; drop the lead pair and the [stop-mark trailing-space] pair — 32 bit pairs remain

(defn- bits->byte
  "NEC sends LSB first."
  [bits]
  (when-not (= 8 (count bits))
    (throw (ex-info "NEC frame must carry 32 bits"
                    {:remocon.error :remocon.error/frame-length :bits (count bits)})))
  (reduce (fn [acc bit] (+ (* 2 acc) bit)) 0 (reverse bits)))

(defn decode
  "Raw burst -> {:address n :command n :inverted? true :repeat? false} or a
  repeat frame {:repeat? true}. Throws (fail closed) when the burst is not a
  valid NEC frame."
  [burst]
  (raw/assert-burst! burst)
  (let [[lead-mark lead-space] (map second (take 2 burst))
        abs (fn [x] (if (neg? x) (- x) x))]
    (cond
      ;; NEC repeat frame: one long mark, one long space, stop mark — the
      ;; trailing :space is the inter-frame gap, not part of the frame.
      (and (<= (abs (- lead-mark-us lead-mark)) 1000)
           (<= (abs (- repeat-space-us lead-space)) 1000))
      (do (when-not (contains? #{3 4} (count burst))
            (throw (ex-info "NEC repeat frame has extra segments"
                            {:remocon.error :remocon.error/repeat-frame})))
          {:repeat? true :protocol :nec})

      ;; normal frame: 9ms mark + 4.5ms space. Tolerances stay tight: the
      ;; 4.5ms lead space is 500us apart from a 4ms non-NEC space.
      (and (<= (abs (- lead-mark-us lead-mark)) 800)
           (<= (abs (- lead-space-us lead-space)) 400))
      (let [{:keys [tick pairs]} (with-tick burst)
            _ (when-not (= 34 (count pairs))          ; lead + 32 bits + stop + trailing space
                (throw (ex-info "NEC frame must have 34 mark/space pairs"
                                {:remocon.error :remocon.error/pair-count
                                 :got (count pairs)})))
            bits (decode-bits pairs tick)
            _ (when-not (= 32 (count bits))
                (throw (ex-info "NEC frame must carry 32 bits"
                                {:remocon.error :remocon.error/frame-length
                                 :got (count bits)})))
            [a a' c c'] (map #(bits->byte %) (partition 8 bits))
            _ (when-not (and (= a (bit-xor a' 0xFF))
                             (= c (bit-xor c' 0xFF)))
                (throw (ex-info "NEC inverted bytes do not match"
                                {:remocon.error :remocon.error/inverted-bytes})))
            _ (when-not (<= (abs (- stop-mark-us (second (first (last pairs))))) 200)
                (throw (ex-info "NEC stop mark is not one tick"
                                {:remocon.error :remocon.error/stop-mark})))]
        {:protocol :nec :address a :command c :inverted? true :repeat? false})

      :else
      (throw (ex-info "burst does not lead like an NEC frame"
                      {:remocon.error :remocon.error/lead
                       :lead-mark-us lead-mark
                       :lead-space-us lead-space})))))

(defn encode
  "Frame map -> raw burst (with the canonical 560us tick). The stop mark is
  followed by a 1-tick space so the result is a valid burst (mark-first,
  space-last)."
  [{:keys [address command repeat?]}]
  (if repeat?
    [[:mark lead-mark-us] [:space repeat-space-us] [:mark stop-mark-us]
     [:space 108000]]
    (let [bits (fn [n] (for [i (range 8)] (bit-and 1 (bit-shift-right n i))))
          byte-bits (fn [n] (vec (bits n)))
          inv (fn [x] (bit-xor x 0xFF))
          all-bits (vec (concat (byte-bits address)
                                (byte-bits (inv address))
                                (byte-bits command)
                                (byte-bits (inv command))))
          frame (into [[:mark lead-mark-us] [:space lead-space-us]]
                      (mapcat (fn [b]
                                [[:mark (if (zero? b) bit-space-us (* 3 bit-space-us))]
                                 [:space bit-space-us]])
                              all-bits))]
      (conj frame [:mark stop-mark-us] [:space 108000]))))
