(ns pcb.schematic
  "Schematic capture: symbol placement, wire routing, net labelling, and
  netlist extraction. Restored from kami-eda's `schematic` module
  (kami-engine/kami-eda/src/lib.rs, deleted PR #82). Positions are `[x y]`
  2-vectors (glam::Vec2 in the original).")

(def pin-types
  #{:input :output :bidirectional :tri-state :passive :power
    :open-collector :open-emitter :not-connected :unspecified})
(def orientations #{:left :right :up :down})

(defn- v-distance [[ax ay] [bx by]] (Math/sqrt (+ (Math/pow (- bx ax) 2) (Math/pow (- by ay) 2))))
(defn- v+ [[ax ay] [bx by]] [(+ ax bx) (+ ay by)])

(defn pin [{:keys [name number pin-type position orientation]}]
  {:name name :number number :pin-type pin-type :position position :orientation orientation})

(defn schematic
  "A fresh, empty schematic."
  []
  {:next-id 0 :sheets [] :symbols [] :wires [] :nets {} :labels [] :power-ports [] :junctions []})

(defn- alloc-id [sch] [(inc (:next-id sch)) (update sch :next-id inc)])

(defn place-symbol
  "Place a symbol instance. Returns `[id sch']`."
  [sch library-ref designator value position rotation mirror pins]
  (let [[id sch] (alloc-id sch)]
    [id (update sch :symbols conj
                {:id id :library-ref library-ref :designator designator :value value
                 :position position :rotation rotation :mirror mirror :pins pins})]))

(defn route-wire
  "Route a wire between two points, optionally assigning it to a net.
  Returns `[id sch']`."
  [sch start end net-id]
  (let [[id sch] (alloc-id sch)]
    [id (update sch :wires conj {:id id :start start :end end :net-id net-id})]))

(defn add-net-label
  "Add a net label at `position`. Returns `[id sch']`."
  [sch name position orientation]
  (let [[id sch] (alloc-id sch)]
    [id (update sch :labels conj {:id id :name name :position position :orientation orientation})]))

(defn generate-netlist
  "Build the netlist from placed symbols and wires: `{net-id -> net}`. Pins
  whose position coincides with a net-assigned wire endpoint are grouped
  into that net."
  [sch]
  (let [eps 0.01]
    (reduce
     (fn [nets sym]
       (reduce
        (fn [nets p]
          (let [abs-pin-pos (v+ (:position sym) (:position p))]
            (reduce
             (fn [nets wire]
               (if-not (:net-id wire)
                 nets
                 (if-not (or (< (v-distance abs-pin-pos (:start wire)) eps)
                             (< (v-distance abs-pin-pos (:end wire)) eps))
                   nets
                   (let [nid (:net-id wire)
                         nets (if (contains? nets nid)
                                nets
                                (assoc nets nid
                                       {:id nid
                                        :name (or (some #(when (or (< (v-distance (:position %) (:start wire)) eps)
                                                                    (< (v-distance (:position %) (:end wire)) eps))
                                                            (:name %))
                                                         (:labels sch))
                                                  (str "NET_" nid))
                                        :pins []}))
                         entry [(:id sym) (:number p)]]
                     (if (some #(= % entry) (get-in nets [nid :pins]))
                       nets
                       (update-in nets [nid :pins] conj entry))))))
             nets (:wires sch))))
        nets (:pins sym)))
     {} (:symbols sch))))

(defn delete-entity
  "Delete any entity (symbol/wire/label/power-port/junction) by `id`.
  Returns `[deleted? sch']`."
  [sch id]
  (let [count-all (fn [s] (+ (count (:symbols s)) (count (:wires s)) (count (:labels s))
                              (count (:power-ports s)) (count (:junctions s))))
        before (count-all sch)
        sch (-> sch
                (update :symbols (fn [xs] (vec (remove #(= (:id %) id) xs))))
                (update :wires (fn [xs] (vec (remove #(= (:id %) id) xs))))
                (update :labels (fn [xs] (vec (remove #(= (:id %) id) xs))))
                (update :power-ports (fn [xs] (vec (remove #(= (:id %) id) xs))))
                (update :junctions (fn [xs] (vec (remove #(= (:id %) id) xs)))))
        after (count-all sch)]
    [(< after before) sch]))
