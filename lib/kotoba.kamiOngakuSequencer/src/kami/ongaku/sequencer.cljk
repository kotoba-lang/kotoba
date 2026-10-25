(ns kami.ongaku.sequencer
  "Portable MIDI-equivalent event/pattern/track IR: quantize, groove,
   validation. Ticks are integers at a fixed PPQ (pulses/ticks per quarter
   note) resolution — no floating point beat math, matching real MIDI/DAW
   internals.

   Event shapes (all keyed by :type, all carry :tick and :channel):
     {:type :note               :pitch 0-127 :velocity 0-127 :tick n :duration-ticks pos-int :channel 0-15}
     {:type :cc                 :controller 0-127 :value 0-127 :tick n :channel 0-15}
     {:type :pitch-bend         :value -8192..8191 :tick n :channel 0-15}
     {:type :aftertouch         :pitch 0-127 :value 0-127 :tick n :channel 0-15}
     {:type :channel-aftertouch :value 0-127 :tick n :channel 0-15}

   Pattern: {:name string :length-ticks pos-int :loop? bool :events [event...]}
   Track:   {:name string :channel 0-15 :clips [{:clip pattern :start-tick n} ...]}")

(def default-ppq
  "Ticks per quarter note. 480 matches common DAW/SMF resolution."
  480)

;; ---------------------------------------------------------------------------
;; portable integer rounding (no Math/round — behaves identically on clj/cljs)

(defn- round* [x]
  #?(:clj (long (Math/floor (+ (double x) 0.5)))
     :cljs (js/Math.round x)))

(defn- floor* [x]
  #?(:clj (long (Math/floor (double x)))
     :cljs (js/Math.floor x)))

;; ---------------------------------------------------------------------------
;; validation

(defn validate-event
  "Returns a (possibly empty) seq of error strings for a single event map."
  [{:keys [type tick channel] :as ev}]
  (let [common (cond-> []
                 (or (nil? tick) (neg? tick)) (conj (str "tick must be >= 0, got " tick))
                 (and (some? channel) (not (<= 0 channel 15)))
                 (conj (str "channel out of range 0-15: " channel)))]
    (into common
          (case type
            :note (cond-> []
                    (not (<= 0 (:pitch ev) 127)) (conj (str "note pitch out of range 0-127: " (:pitch ev)))
                    (not (<= 0 (:velocity ev) 127)) (conj (str "note velocity out of range 0-127: " (:velocity ev)))
                    (not (pos-int? (:duration-ticks ev))) (conj (str "note duration-ticks must be a positive int: " (:duration-ticks ev))))
            :cc (cond-> []
                  (not (<= 0 (:controller ev) 127)) (conj (str "cc controller out of range 0-127: " (:controller ev)))
                  (not (<= 0 (:value ev) 127)) (conj (str "cc value out of range 0-127: " (:value ev))))
            :pitch-bend (cond-> []
                          (not (<= -8192 (:value ev) 8191)) (conj (str "pitch-bend value out of range -8192..8191: " (:value ev))))
            :aftertouch (cond-> []
                          (not (<= 0 (:pitch ev) 127)) (conj (str "aftertouch pitch out of range 0-127: " (:pitch ev)))
                          (not (<= 0 (:value ev) 127)) (conj (str "aftertouch value out of range 0-127: " (:value ev))))
            :channel-aftertouch (cond-> []
                                   (not (<= 0 (:value ev) 127)) (conj (str "channel-aftertouch value out of range 0-127: " (:value ev))))
            [(str "unknown event :type " type)]))))

(defn validate-events [events]
  (vec (mapcat validate-event events)))

(defn validate-pattern
  "Checks every event is valid and that no event runs past the pattern's
   length-ticks."
  [{:keys [events length-ticks]}]
  (let [errs (validate-events events)
        overflowing (filter (fn [{:keys [tick duration-ticks] :or {duration-ticks 0}}]
                               (> (+ (or tick 0) duration-ticks) length-ticks))
                             events)]
    (cond-> errs
      (seq overflowing)
      (conj (str (count overflowing) " event(s) exceed pattern length-ticks " length-ticks)))))

;; ---------------------------------------------------------------------------
;; quantize

(defn quantize-events
  "Snap event :tick values to a grid of grid-ticks spacing.

   :strength (0.0-1.0, default 1.0) — 0 leaves ticks untouched, 1 snaps fully,
   values in between blend linearly toward the grid target (\"partial quantize\").

   :swing (0.0-1.0, default 0.0) — delays every odd-indexed grid line
   (the off-beat subdivisions) by swing * grid-ticks before blending, i.e.
   classic swing/shuffle timing."
  [events grid-ticks {:keys [strength swing] :or {strength 1.0 swing 0.0}}]
  (mapv
   (fn [{:keys [tick] :as ev}]
     (let [idx (round* (/ tick grid-ticks))
           base-target (* idx grid-ticks)
           target (if (odd? idx)
                    (+ base-target (round* (* swing grid-ticks)))
                    base-target)
           blended (+ tick (* strength (- target tick)))]
       (assoc ev :tick (max 0 (round* blended)))))
   events))

;; ---------------------------------------------------------------------------
;; groove / humanize

(defn apply-groove
  "Applies a repeating groove template to events. groove-template is a vector
   of {:offset-ticks n :velocity-offset n}, one entry per grid subdivision;
   it repeats every (count groove-template) subdivisions (a \"groove
   template\"/\"groove quantize\" table, as in real DAWs). Each event's tick
   is shifted by its slot's offset-ticks; note events additionally have
   :velocity adjusted by velocity-offset (clamped to 0-127)."
  [events grid-ticks groove-template]
  (let [n (count groove-template)]
    (if (zero? n)
      (vec events)
      (mapv
       (fn [{:keys [tick type velocity] :as ev}]
         (let [slot (mod (floor* (/ tick grid-ticks)) n)
               {:keys [offset-ticks velocity-offset] :or {offset-ticks 0 velocity-offset 0}} (nth groove-template slot)]
           (cond-> (update ev :tick + offset-ticks)
             (and (= type :note) (some? velocity))
             (update :velocity #(-> (+ % velocity-offset) (max 0) (min 127))))))
       events))))

;; ---------------------------------------------------------------------------
;; clip / track flattening (bridge to the SMF interchange layer)

(defn flatten-track
  "Flattens a Track's placed clips into a single absolute-tick, tick-sorted
   event stream: {:channel n :events [event...]}. This is the shape
   kami.ongaku.sequencer.smf/export-smf consumes — SMF, like real-world MIDI
   files, has no concept of DAW clip boundaries, only per-track absolute
   events, so clip structure does not survive an SMF round-trip."
  [{:keys [clips channel] :or {channel 0}}]
  {:channel channel
   :events (->> clips
                (mapcat (fn [{:keys [clip start-tick] :or {start-tick 0}}]
                          (map (fn [ev]
                                 (cond-> (update ev :tick + start-tick)
                                   (nil? (:channel ev)) (assoc :channel channel)))
                               (:events clip))))
                (sort-by :tick)
                vec)})
