(ns spice.circuit
  "SPICE circuit elements + circuit container. Restored from kami-spice's
  `circuit` module (kami-engine/kami-spice/src/lib.rs, deleted PR #82).
  An element is a plain EDN map `{:kind <kind> ...}`; a circuit is
  `{:elements [...] :models {name -> definition-string}}`.")

(def element-kinds
  #{:resistor :capacitor :inductor :voltage-source :current-source
    :mosfet :bjt :diode})

(defn circuit
  "A fresh, empty circuit."
  []
  {:elements [] :models {}})

(defn add-element
  [circuit element]
  (update circuit :elements conj element))

(defn diode
  "A diode element, anode -> cathode. Optional compact-model overrides
  `:is` (saturation current), `:n` (emission coefficient), `:vt` (thermal
  voltage) and `:model-name` — `spice.analysis/solve-dc-op-nonlinear`
  falls back to Shockley defaults (Is=1e-14, n=1.0, Vt=0.02585) for any
  omitted."
  [name anode cathode & {:keys [is n vt model-name]}]
  (cond-> {:kind :diode :name name :anode anode :cathode cathode}
    is (assoc :is is)
    n (assoc :n n)
    vt (assoc :vt vt)
    model-name (assoc :model-name model-name)))

(defn mosfet
  "A MOSFET element (drain/gate/source/bulk). Optional compact-model
  overrides `:vth` (threshold voltage) and `:kp` (transconductance
  parameter, already W/L-scaled — this simplified square-law model does
  not track W/L separately) — `spice.analysis/solve-dc-op-nonlinear`
  falls back to defaults (Vth=0.7, Kp=2e-4) for any omitted."
  [name drain gate source bulk & {:keys [vth kp mosfet-type w l model-name]}]
  (cond-> {:kind :mosfet :name name :drain drain :gate gate :source source :bulk bulk}
    vth (assoc :vth vth)
    kp (assoc :kp kp)
    mosfet-type (assoc :mosfet-type mosfet-type)
    w (assoc :w w)
    l (assoc :l l)
    model-name (assoc :model-name model-name)))

(defn bjt
  "An NPN BJT element (collector/base/emitter). Optional compact-model
  overrides `:is` (saturation current), `:beta` (forward current gain),
  `:vt` (thermal voltage) — `spice.analysis/solve-dc-op-nonlinear` falls
  back to defaults (Is=1e-16, beta=100.0, Vt=0.02585) for any omitted.
  Forward-active region only (stated simplification, see
  `spice.analysis`)."
  [name collector base emitter & {:keys [is beta bjt-type vt model-name]}]
  (cond-> {:kind :bjt :name name :collector collector :base base :emitter emitter}
    is (assoc :is is)
    beta (assoc :beta beta)
    bjt-type (assoc :bjt-type bjt-type)
    vt (assoc :vt vt)
    model-name (assoc :model-name model-name)))

(defn- ground? [n] (or (= n "0") (= n "gnd")))

(defn- element-nodes
  "The (non-ground) net names an element touches."
  [{:keys [kind n1 n2 n-pos n-neg gate drain source bulk collector base emitter anode cathode]}]
  (case kind
    (:resistor :capacitor :inductor) [n1 n2]
    (:voltage-source :current-source) [n-pos n-neg]
    :mosfet [gate drain source bulk]
    :bjt [collector base emitter]
    :diode [anode cathode]))

(defn node-count
  "The number of unique non-ground nodes referenced across `circuit`'s elements."
  [circuit]
  (->> (:elements circuit)
       (mapcat element-nodes)
       (remove ground?)
       (into #{})
       count))

(defn element-count [circuit] (count (:elements circuit)))
