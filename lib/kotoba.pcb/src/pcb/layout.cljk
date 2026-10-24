(ns pcb.layout
  "PCB layout: footprint placement, trace routing, via insertion, copper
  zone pours, and design-rule checking. Restored from kami-eda's `pcb`
  module (deleted PR #82) — named `pcb.layout` here (not `pcb.pcb`) since
  the top-level namespace is already `pcb`. Violations are plain maps
  matching kotoba-lang/engineer's `engineer.drc` violation shape
  (`{:rule-id :severity :message :entity-ids :location}`).")

(def pad-shapes #{:round :rect :oblong :custom})
(def zone-fills #{:solid :hatched})
(def layer-kinds #{:front :back}) ; plus [:inner n]

(defn- v-distance [[ax ay] [bx by]] (Math/sqrt (+ (Math/pow (- bx ax) 2) (Math/pow (- by ay) 2))))
(defn- fmt3
  "Format `x` to 3 decimal places, matching Rust's `{:.3}`."
  [x]
  #?(:clj (format "%.3f" (double x))
     :cljs (.toFixed (double x) 3)))

(defn pad
  "`:net-id` is optional (nil = unassigned) — set it to make this pad a
  routable endpoint for pcb.route/route-net (added alongside pcb.route;
  the original kami-eda restoration's `pad` had no net association, since
  nothing consumed one)."
  [{:keys [center size shape drill layers net-id]}]
  {:center center :size size :shape shape :drill drill :layers layers :net-id net-id})

(defn layer-def [layer name thickness-mm] {:layer layer :name name :thickness-mm thickness-mm})
(defn pcb-board [outline layer-stack] {:outline outline :layer-stack layer-stack})

(defn drc-config
  ([] (drc-config {}))
  ([{:keys [min-trace-width min-clearance min-via-drill min-annular-ring
            min-drill-to-drill min-copper-to-edge min-silk-to-pad]
     :or {min-trace-width 0.15 min-clearance 0.15 min-via-drill 0.2
          min-annular-ring 0.125 min-drill-to-drill 0.25
          min-copper-to-edge 0.25 min-silk-to-pad 0.05}}]
   {:min-trace-width min-trace-width :min-clearance min-clearance
    :min-via-drill min-via-drill :min-annular-ring min-annular-ring
    :min-drill-to-drill min-drill-to-drill :min-copper-to-edge min-copper-to-edge
    :min-silk-to-pad min-silk-to-pad}))

(defn pcb-layout
  "A fresh PCB layout over `board`, default DRC config."
  [board]
  {:next-id 0 :board board :footprints [] :traces [] :vias [] :zones []
   :drc-config (drc-config)})

(defn- alloc-id [layout] [(inc (:next-id layout)) (update layout :next-id inc)])

(defn place-footprint
  [layout library-ref designator x y rotation layer pads]
  (let [[id layout] (alloc-id layout)]
    [id (update layout :footprints conj
                {:id id :library-ref library-ref :designator designator
                 :x x :y y :rotation rotation :layer layer :pads pads})]))

(defn route-trace [layout net-id points width layer]
  (let [[id layout] (alloc-id layout)]
    [id (update layout :traces conj {:id id :net-id net-id :points points :width width :layer layer})]))

(defn add-via [layout x y drill outer-diameter net-id]
  (let [[id layout] (alloc-id layout)]
    [id (update layout :vias conj {:id id :x x :y y :drill drill :outer-diameter outer-diameter :net-id net-id})]))

(defn pour-zone [layout net-id boundary layer fill]
  (let [[id layout] (alloc-id layout)]
    [id (update layout :zones conj {:id id :net-id net-id :boundary boundary :layer layer :fill fill})]))

(defn run-drc
  "Run design-rule checks: trace width, via drill diameter, via annular
  ring, and trace-to-trace clearance (different net, same layer)."
  [layout]
  (let [cfg (:drc-config layout)
        trace-violations
        (for [trace (:traces layout) :when (< (:width trace) (:min-trace-width cfg))]
          {:rule-id "PCB_MIN_TRACE_WIDTH" :severity :error
           :message (str "Trace (id=" (:id trace) ") width " (fmt3 (:width trace))
                         " mm < min " (fmt3 (:min-trace-width cfg)) " mm")
           :entity-ids [(:id trace)]
           :location (first (:points trace))})
        via-drill-violations
        (for [via (:vias layout) :when (< (:drill via) (:min-via-drill cfg))]
          {:rule-id "PCB_MIN_VIA_DRILL" :severity :error
           :message (str "Via (id=" (:id via) ") drill " (fmt3 (:drill via))
                         " mm < min " (fmt3 (:min-via-drill cfg)) " mm")
           :entity-ids [(:id via)]
           :location [(:x via) (:y via)]})
        via-annular-violations
        (for [via (:vias layout)
              :let [annular (/ (- (:outer-diameter via) (:drill via)) 2.0)]
              :when (< annular (:min-annular-ring cfg))]
          {:rule-id "PCB_MIN_ANNULAR_RING" :severity :error
           :message (str "Via (id=" (:id via) ") annular ring " (fmt3 annular)
                         " mm < min " (fmt3 (:min-annular-ring cfg)) " mm")
           :entity-ids [(:id via)]
           :location [(:x via) (:y via)]})
        traces (vec (:traces layout))
        n (count traces)
        clearance-violations
        (for [i (range n) j (range (inc i) n)
              :let [a (nth traces i) b (nth traces j)]
              :when (and (= (:layer a) (:layer b)) (not= (:net-id a) (:net-id b)))
              pa (:points a) pb (:points b)
              :let [dist (v-distance pa pb)
                    required (+ (:min-clearance cfg) (/ (+ (:width a) (:width b)) 2.0))]
              :when (< dist required)]
          {:rule-id "PCB_MIN_CLEARANCE" :severity :error
           :message (str "Clearance " (fmt3 dist) " mm between traces (id=" (:id a) ", id=" (:id b)
                         ") < min " (fmt3 (:min-clearance cfg)) " mm")
           :entity-ids [(:id a) (:id b)]
           :location pa})]
    (vec (concat trace-violations via-drill-violations via-annular-violations clearance-violations))))
