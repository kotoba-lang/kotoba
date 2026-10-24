(ns kami.ongaku.sampler
  "Sample zone/mapping, round-robin variation cycling, velocity-layer
   lookup, and a streaming-lifecycle state machine for portable
   sample-playback engines (Kontakt-equivalent mapping model).

   No audio decoding, no disk/network I/O — pure data model + lookup
   functions. `:variation/gain-offset` and `:layer/gain` are linear
   multipliers (not dB) so this stays JVM/cljs math-portable without
   any platform-specific log/exp calls.")

(declare validate-sample-map)

;; --- construction -----------------------------------------------------

(defn make-variation
  "sample-ref: opaque sample id/URI. gain-offset: linear multiplier
   applied on top of the layer's gain (default 1.0 = no change)."
  ([sample-ref] (make-variation sample-ref {}))
  ([sample-ref {:keys [gain-offset] :or {gain-offset 1.0}}]
   {:variation/sample-ref sample-ref
    :variation/gain-offset gain-offset}))

(defn make-layer
  "key/vel ranges are inclusive on both ends. Returns nil if the shape
   is invalid (empty range, no variations)."
  [{:keys [key-low key-high vel-low vel-high pitch-offset gain pan variations]
    :or {pitch-offset 0.0 gain 1.0 pan 0.0}}]
  (when (and (integer? key-low) (integer? key-high) (<= key-low key-high)
             (integer? vel-low) (integer? vel-high) (<= vel-low vel-high)
             (seq variations))
    {:layer/key-low key-low :layer/key-high key-high
     :layer/vel-low vel-low :layer/vel-high vel-high
     :layer/pitch-offset pitch-offset
     :layer/gain gain
     :layer/pan pan
     :layer/variations (vec variations)}))

(defn make-sample-map
  "Returns {:sample-map/layers [...]} if layers don't overlap, else nil.
   Use validate-sample-map directly if you want the overlap detail."
  [layers]
  (when (:valid? (validate-sample-map layers))
    {:sample-map/layers (vec layers)}))

;; --- range / overlap ----------------------------------------------------

(defn in-range? [low high v]
  (and (<= low v) (<= v high)))

(defn ranges-overlap?
  "Two inclusive integer ranges overlap iff each range's low bound is
   <= the other range's high bound."
  [low1 high1 low2 high2]
  (and (<= low1 high2) (<= low2 high1)))

(defn layer-matches? [layer note velocity]
  (and (in-range? (:layer/key-low layer) (:layer/key-high layer) note)
       (in-range? (:layer/vel-low layer) (:layer/vel-high layer) velocity)))

(defn layers-overlap?
  "Two layers overlap iff both their key ranges AND their velocity
   ranges overlap (a shared key range at disjoint velocity bands is
   the normal multi-velocity-layer case, not an overlap)."
  [a b]
  (and (ranges-overlap? (:layer/key-low a) (:layer/key-high a)
                         (:layer/key-low b) (:layer/key-high b))
       (ranges-overlap? (:layer/vel-low a) (:layer/vel-high a)
                         (:layer/vel-low b) (:layer/vel-high b))))

(defn validate-sample-map
  "{:valid? true} or {:valid? false :overlaps [[i j] ...]} (0-based
   indices into the input layer vector)."
  [layers]
  (let [layers (vec layers)
        n (count layers)
        overlaps (for [i (range n) j (range (inc i) n)
                       :when (layers-overlap? (nth layers i) (nth layers j))]
                   [i j])]
    (if (seq overlaps)
      {:valid? false :overlaps (vec overlaps)}
      {:valid? true})))

;; --- lookup ---------------------------------------------------------

(defn find-layer
  "First layer whose key+velocity ranges contain (note, velocity), or
   nil. Callers should validate the sample map up front so at most one
   layer can ever match; this does not itself enforce that."
  [layers note velocity]
  (first (filter #(layer-matches? % note velocity) layers)))

(defn next-round-robin-index [variations trigger-count]
  (mod trigger-count (count variations)))

(defn next-round-robin-sample [layer trigger-count]
  (nth (:layer/variations layer)
       (next-round-robin-index (:layer/variations layer) trigger-count)))

(defn trigger-sample
  "Resolve (note, velocity, trigger-count) against a layer vector.
   Returns {:sample-ref :pitch-offset :gain :pan} or nil if no layer
   matches."
  [layers note velocity trigger-count]
  (when-let [layer (find-layer layers note velocity)]
    (let [variation (next-round-robin-sample layer trigger-count)]
      {:sample-ref (:variation/sample-ref variation)
       :pitch-offset (:layer/pitch-offset layer)
       :gain (* (:layer/gain layer) (:variation/gain-offset variation))
       :pan (:layer/pan layer)})))

(defn trigger
  [sample-map note velocity trigger-count]
  (trigger-sample (:sample-map/layers sample-map) note velocity trigger-count))

;; --- streaming lifecycle state machine -------------------------------

(def states #{:unloaded :loading :ready :streaming :error})

(def valid-transitions
  #{[:unloaded :loading]
    [:loading :ready]
    [:loading :error]
    [:error :loading]
    [:ready :streaming]
    [:streaming :ready]
    [:ready :unloaded]
    [:streaming :unloaded]
    [:error :unloaded]})

(defn valid-transition? [from to]
  (contains? valid-transitions [from to]))

(defn transition
  "Returns `to` if the transition is legal, else nil."
  [from to]
  (when (valid-transition? from to) to))
