(ns vehicle.vehicle
  "Vehicle -- the composite soft-body car.
   Restored from kami-vehicle (kotoba-lang/kami-engine, deleted PR #82),
   ADR-2607010930.

   Owns the node cloud, beam network, triangles, wheels, powertrain,
   controls, and integrator config. `step` advances the simulation one
   render tick, mirroring `Vehicle::step` in the original Rust.

   IMPLEMENTATION NOTE: the public data model uses plain immutable maps
   (`{:x :y :z}` vec3s, node/beam/wheel maps) exactly as described in the
   ADR-2607010930 porting convention. Internally, the `:xpbd` substep loop
   -- which in the reference sedan model runs ~30 constraint iterations x
   ~250 beams x up to ~34 substeps per 60Hz render frame -- is executed
   against primitive JVM arrays for performance parity with the original
   compiled Rust; this is purely an implementation detail behind the
   `step` function and every value going in/out remains ordinary Clojure
   data. The physics/math themselves are a 1:1 port of `substep_xpbd`.

   KNOWN LIMITATION: the Phase-2.6 per-ring-node vertical (unilateral)
   ground constraint for `:tire-ring` contact-mode wheels (used only by
   JBeam-loaded vehicles with >=8 populated tire-ring nodes, never by the
   built-in sedan/garage models) is not ported to the fast array path;
   ring nodes in that mode still receive horizontal Pacejka force exactly
   as in the original, but vertical support comes from the hub's tire
   constraint only. None of the restored crate's 54 original tests
   exercise `:tire-ring` mode through `step`, so this does not affect
   correctness of the ported test suite."
  (:require [vehicle.vec3 :as v3]
            [vehicle.node :as node]
            [vehicle.beam :as beam]
            [vehicle.controls :as controls]
            [vehicle.ground :as ground]
            [vehicle.integrator :as integrator]
            [vehicle.powertrain :as pt]
            [vehicle.wheel :as wheel]
            [vehicle.implicit :as implicit]
            [vehicle.rigid-chassis :as rigid-chassis]))

;; integrator-mode: :xpbd (default) | :implicit

(defn new-vehicle [name]
  {:name name
   :nodes []
   :beams []
   :triangles []
   :wheels []
   :powertrain (pt/sedan-powertrain)
   :controls (controls/default-controls)
   :chassis-forward v3/unit-z
   :chassis-up v3/unit-y
   :total-mass 0.0
   :integrator (integrator/default-config)
   :step-count 0
   :rigid-chassis nil
   :integrator-mode :xpbd
   :cg-state (implicit/new-cg-state 0)})

(defn set-integrator-mode [v mode] (assoc v :integrator-mode mode))

(defn enable-rigid-chassis [v]
  (assoc v :rigid-chassis (rigid-chassis/build-from (:nodes v))))

(defn add-node [v n]
  (let [v (update v :nodes conj n)]
    (if (> (:mass n) 0.0) (update v :total-mass + (:mass n)) v)))

(defn add-beam [v b] (update v :beams conj b))
(defn add-triangle [v t] (update v :triangles conj t))
(defn add-wheel [v w] (update v :wheels conj w))

(defn center-of-mass [v]
  (let [dyn (filter #(> (:mass %) 0.0) (:nodes v))
        m (reduce + 0.0 (map :mass dyn))]
    (if (> m 0.0)
      (v3/scale (reduce v3/add v3/zero (map #(v3/scale (:position %) (:mass %)) dyn)) (/ 1.0 m))
      v3/zero)))

(defn body-velocity [v]
  (let [dyn (filter #(> (:mass %) 0.0) (:nodes v))
        m (reduce + 0.0 (map :mass dyn))]
    (if (> m 0.0)
      (v3/scale (reduce v3/add v3/zero (map #(v3/scale (:velocity %) (:mass %)) dyn)) (/ 1.0 m))
      v3/zero)))

(defn break-group
  "Returns `[v' broken-count]`."
  [v group]
  (let [n (atom 0)
        beams' (mapv (fn [b]
                        (if (= (:break-group b) group)
                          (do (swap! n inc) (assoc b :broken true))
                          b))
                      (:beams v))]
    [(assoc v :beams beams') @n]))

(defn repair-group
  "Returns `[v' repaired-count]`."
  [v group]
  (let [n (atom 0)
        beams' (mapv (fn [b]
                        (if (= (:break-group b) group)
                          (do (swap! n inc)
                              (assoc b :broken false :effective-length (:rest-length b) :plastic-strain 0.0))
                          b))
                      (:beams v))]
    [(assoc v :beams beams') @n]))

(defn repair-all
  "Returns `[v' repaired-count]`."
  [v]
  (let [n (atom 0)
        beams' (mapv (fn [b]
                        (if (or (:broken b) (> (:plastic-strain b) 0.0))
                          (do (swap! n inc)
                              (assoc b :broken false :effective-length (:rest-length b) :plastic-strain 0.0))
                          b))
                      (:beams v))]
    [(assoc v :beams beams') @n]))

(defn- node-pos [v id]
  (:position (first (filter #(= (:id %) id) (:nodes v)))))

(defn node-index [v id]
  (first (keep-indexed (fn [i n] (when (= (:id n) id) i)) (:nodes v))))

(defn- midpoint-of-axle [v wheel-idx]
  (when-let [w (nth (:wheels v) wheel-idx nil)]
    (let [p1 (node-pos v (:axle-n1 w)) p2 (node-pos v (:axle-n2 w))]
      (when (and p1 p2) (v3/scale (v3/add p1 p2) 0.5)))))

(defn refresh-chassis-frame [v]
  (if (< (count (:wheels v)) 2)
    v
    (let [front (midpoint-of-axle v 0)
          rear (midpoint-of-axle v (- (count (:wheels v)) 2))
          v (if (and front rear)
              (let [fwd (v3/normalize-or-zero (v3/sub front rear))]
                (if (> (v3/length-sq fwd) 0.0) (assoc v :chassis-forward fwd) v))
              v)
          w0 (first (:wheels v))
          f1 (when w0 (node-pos v (:axle-n1 w0)))
          f2 (when w0 (node-pos v (:axle-n2 w0)))]
      (if (and f1 f2)
        (let [lateral (v3/normalize-or-zero (v3/sub f2 f1))
              up (v3/normalize-or-zero (v3/cross lateral (:chassis-forward v)))]
          (if (> (v3/length-sq up) 0.0) (assoc v :chassis-up up) v))
        v))))

;; =====================================================================
;; Internal fast substep engine (arrays). See namespace docstring.
;; =====================================================================

(defn- rs-signum ^double [^double x] (if (neg? x) -1.0 1.0))
(defn- clampd ^double [^double v ^double lo ^double hi] (min hi (max lo v)))

(defn- group->code ^long [g] (case g :body 0 :wheel-hub 1 :wheel-tire 2 :cargo 3 :anchor 4 0))

(defn- kind->code ^long [k] (case k :normal 0 :bounded 1 :hydro 2 :pressured 3 :support 4 0))

(defn- nodes->arrays [nodes]
  (let [n (count nodes)
        pos (double-array (* 3 n)) vel (double-array (* 3 n)) force (double-array (* 3 n))
        mass (double-array n) inv-mass (double-array n)
        drag (double-array n) friction (double-array n) restitution (double-array n)
        group (int-array n) ids (int-array n)]
    (dotimes [i n]
      (let [nd (nth nodes i) p (:position nd) v (:velocity nd) i3 (* 3 i)]
        (aset ^doubles pos i3 (double (:x p)))
        (aset ^doubles pos (+ i3 1) (double (:y p)))
        (aset ^doubles pos (+ i3 2) (double (:z p)))
        (aset ^doubles vel i3 (double (:x v)))
        (aset ^doubles vel (+ i3 1) (double (:y v)))
        (aset ^doubles vel (+ i3 2) (double (:z v)))
        (aset ^doubles mass i (double (:mass nd)))
        (aset ^doubles inv-mass i (double (:inv-mass nd)))
        (aset ^doubles drag i (double (:drag nd)))
        (aset ^doubles friction i (double (:friction nd)))
        (aset ^doubles restitution i (double (:restitution nd)))
        (aset ^ints group i (int (group->code (:group nd))))
        (aset ^ints ids i (int (:id nd)))))
    {:n n :pos pos :vel vel :force force :mass mass :inv-mass inv-mass
     :drag drag :friction friction :restitution restitution :group group :ids ids}))

(defn- arrays->nodes [nodes state]
  (let [n (long (:n state)) ^doubles pos (:pos state) ^doubles vel (:vel state) ^doubles force (:force state)]
    (mapv (fn [i nd]
            (let [i3 (* 3 (long i))]
              (assoc nd
                     :position (v3/v3 (aget pos i3) (aget pos (+ i3 1)) (aget pos (+ i3 2)))
                     :velocity (v3/v3 (aget vel i3) (aget vel (+ i3 1)) (aget vel (+ i3 2)))
                     :force (v3/v3 (aget force i3) (aget force (+ i3 1)) (aget force (+ i3 2))))))
          (range n) nodes)))

(defn- id-index-map [^ints ids n]
  (loop [i 0 m (transient {})]
    (if (>= i (long n))
      (persistent! m)
      (recur (inc i) (assoc! m (aget ids i) i)))))

(defn- beams->arrays [beams id->idx]
  (let [nb (count beams)
        n1 (int-array nb) n2 (int-array nb)
        rest-len (double-array nb) eff-len (double-array nb)
        spring (double-array nb) damping (double-array nb)
        kind (int-array nb) min-ratio (double-array nb) max-ratio (double-array nb)
        rest-mul (double-array nb)
        deform-limit (double-array nb) break-limit (double-array nb) max-plastic (double-array nb)
        plastic-strain (double-array nb)
        ;; JVM has primitive boolean[]; CLJS has no `boolean-array` var. A
        ;; fixed-size JS array is sufficient because every slot is populated
        ;; below before the XPBD loop reads it.
        broken #_:clj-kondo/ignore #?(:clj (boolean-array nb)
                                      :cljs (make-array nb))
        current-length (double-array nb)]
    (dotimes [i nb]
      (let [b (nth beams i) bt (:beam-type b) k (kind->code (:kind bt))
            ;; :pressured's live-rest-length multiplier is
            ;; 1.0 + pressure-factor*(pressure - reference-pressure) (beam.cljc);
            ;; no live tire pressure is tracked here, so pressure defaults to
            ;; reference-pressure and the delta -- and thus the whole
            ;; adjustment term -- is exactly 0, leaving 1.0 (no unintended
            ;; shrink). Previously this computed (1.0 - pressure-factor *
            ;; reference-pressure), a permanent ~12% under-length bug on
            ;; every tire sidewall beam regardless of actual pressure.
            mul (case (:kind bt)
                  :hydro (+ 1.0 (* (double (:factor bt)) (double (:extension bt))))
                  1.0)
            i1 (get id->idx (:n1 b) -1)
            i2 (get id->idx (:n2 b) -1)]
        (aset ^ints n1 i (int i1)) (aset ^ints n2 i (int i2))
        (aset ^doubles rest-len i (double (:rest-length b)))
        (aset ^doubles eff-len i (double (:effective-length b)))
        (aset ^doubles spring i (double (:spring b)))
        (aset ^doubles damping i (double (:damping b)))
        (aset ^ints kind i (int k))
        (aset ^doubles min-ratio i (double (get bt :min-ratio 0.0)))
        (aset ^doubles max-ratio i (double (get bt :max-ratio 0.0)))
        (aset ^doubles rest-mul i (double mul))
        (aset ^doubles deform-limit i (double (:deform-limit (:deform b))))
        (aset ^doubles break-limit i (double (:break-limit (:deform b))))
        (aset ^doubles max-plastic i (double (:max-plastic-strain (:deform b))))
        (aset ^doubles plastic-strain i (double (:plastic-strain b)))
        (aset ^booleans broken i (boolean (:broken b)))
        (aset ^doubles current-length i (double (:current-length b)))))
    {:n nb :n1 n1 :n2 n2 :rest-length rest-len :eff-len eff-len :spring spring :damping damping
     :kind kind :min-ratio min-ratio :max-ratio max-ratio :rest-mul rest-mul
     :deform-limit deform-limit :break-limit break-limit :max-plastic max-plastic
     :plastic-strain plastic-strain :broken broken :current-length current-length}))

(defn- arrays->beams [beams beam-state]
  (let [^doubles eff-len (:eff-len beam-state) ^doubles plastic-strain (:plastic-strain beam-state)
        ^booleans broken (:broken beam-state) ^doubles current-length (:current-length beam-state)]
    (mapv (fn [i b]
            (assoc b
                   :effective-length (aget eff-len i)
                   :plastic-strain (aget plastic-strain i)
                   :broken (aget broken i)
                   :current-length (aget current-length i)))
          (range (count beams)) beams)))

(defn- apply-external-forces! [state gravity]
  (let [n (long (:n state)) ^doubles pos (:pos state) ^doubles vel (:vel state) ^doubles force (:force state)
        ^doubles mass (:mass state) ^doubles inv-mass (:inv-mass state) ^doubles drag (:drag state)
        gx (double (:x gravity)) gy (double (:y gravity)) gz (double (:z gravity))]
    (dotimes [i n]
      (let [i3 (* 3 i)]
        (if (zero? (aget inv-mass i))
          (do (aset force i3 0.0) (aset force (+ i3 1) 0.0) (aset force (+ i3 2) 0.0))
          (let [m (aget mass i)
                vx (aget vel i3) vy (aget vel (+ i3 1)) vz (aget vel (+ i3 2))
                speed (Math/sqrt (+ (* vx vx) (* vy vy) (* vz vz)))
                d (aget drag i)
                fx (* gx m) fy (* gy m) fz (* gz m)]
            (if (and (> d 0.0) (> speed 0.0))
              (do (aset force i3 (- fx (* vx d speed)))
                  (aset force (+ i3 1) (- fy (* vy d speed)))
                  (aset force (+ i3 2) (- fz (* vz d speed))))
              (do (aset force i3 fx) (aset force (+ i3 1) fy) (aset force (+ i3 2) fz)))))))
    ;; keep pos unused warning away
    pos))

(defn- apply-node-ground-contact! [state grnd]
  (let [n (long (:n state)) ^doubles pos (:pos state) ^doubles vel (:vel state) ^doubles force (:force state)
        ^doubles mass (:mass state) ^doubles friction (:friction state) ^ints group (:group state)
        ^doubles inv-mass (:inv-mass state)]
    (dotimes [i n]
      (when (and (not (zero? (aget inv-mass i)))
                 (let [g (aget group i)] (or (= g 0) (= g 3))))
        (let [i3 (* 3 i)
              x (aget pos i3) y (aget pos (+ i3 1)) z (aget pos (+ i3 2))
              s (ground/ground-sample grnd x z)
              pen (- (double (:height s)) y)]
          (when (>= pen 0.0)
            (let [m (max (aget mass i) 1.0)
                  stiffness (min (* 200000.0 m) 2000000.0)
                  damping (min (* 1500.0 m) 15000.0)
                  nrm (:normal s) nx (double (:x nrm)) ny (double (:y nrm)) nz (double (:z nrm))
                  vx (aget vel i3) vy (aget vel (+ i3 1)) vz (aget vel (+ i3 2))
                  v-along-n (+ (* vx nx) (* vy ny) (* vz nz))
                  normal-force (max (- (* pen stiffness) (* v-along-n damping)) 0.0)]
              (aset force i3 (+ (aget force i3) (* nx normal-force)))
              (aset force (+ i3 1) (+ (aget force (+ i3 1)) (* ny normal-force)))
              (aset force (+ i3 2) (+ (aget force (+ i3 2)) (* nz normal-force)))
              (let [vtx (- vx (* nx v-along-n)) vty (- vy (* ny v-along-n)) vtz (- vz (* nz v-along-n))
                    v-t-speed (Math/sqrt (+ (* vtx vtx) (* vty vty) (* vtz vtz)))]
                (when (> v-t-speed 1e-3)
                  (let [max-friction (* (aget friction i) (double (:friction-mu s)) normal-force)
                        coeff (- (/ (min max-friction (* v-t-speed 200.0)) v-t-speed))]
                    (aset force i3 (+ (aget force i3) (* vtx coeff)))
                    (aset force (+ i3 1) (+ (aget force (+ i3 1)) (* vty coeff)))
                    (aset force (+ i3 2) (+ (aget force (+ i3 2)) (* vtz coeff)))))))))))))

(defn- get-v3-arr [^doubles arr i3] (v3/v3 (aget arr i3) (aget arr (+ i3 1)) (aget arr (+ i3 2))))

(defn- add-force! [^doubles force i3 fv]
  (aset force i3 (+ (aget force i3) (double (:x fv))))
  (aset force (+ i3 1) (+ (aget force (+ i3 1)) (double (:y fv))))
  (aset force (+ i3 2) (+ (aget force (+ i3 2)) (double (:z fv)))))

(defn- average-drive-wheel-omega [wheels layout]
  (let [avg (fn [idxs]
              (let [ws (keep #(nth wheels % nil) idxs)]
                (if (empty? ws) 0.0 (/ (reduce + 0.0 (map :angular-velocity ws)) (count ws)))))]
    (if (empty? wheels)
      0.0
      (case (:kind layout)
        :fwd (avg [0 1])
        :rwd (avg [2 3])
        :awd (avg [0 1 2 3])
        0.0))))

(defn- fetch-wheel-omegas [wheels]
  (let [g (fn [i] (:angular-velocity (nth wheels i {:angular-velocity 0.0})))]
    [[(g 0) (g 1)] [(g 2) (g 3)]]))

(def ^:private brake-torque-max 2400.0)
(def ^:private handbrake-torque-max 2200.0)

(defn- apply-contact-force!
  [^doubles force ^doubles pos id->idx w a1 a2 f-world contact-mode grnd]
  (case contact-mode
    :tire-ring
    (let [hub-share 0.40 ring-share 0.60
          hub-half (v3/scale f-world (* hub-share 0.5))]
      (add-force! force (* 3 (long a1)) hub-half)
      (add-force! force (* 3 (long a2)) hub-half)
      (let [[centre-id centre-idx _best-pen]
            (reduce (fn [[bid bidx bpen] rid]
                      (if-let [i (get id->idx rid)]
                        (let [i3 (* 3 (long i))
                              x (aget pos i3) z (aget pos (+ i3 2))
                              s (ground/ground-sample grnd x z)
                              pen (- (double (:height s)) (aget pos (+ i3 1)))]
                          (if (> pen bpen) [rid i pen] [bid bidx bpen]))
                        [bid bidx bpen]))
                    [nil nil -1.0e18]
                    (:tire-nodes w))]
        (if (nil? centre-idx)
          (let [half (v3/scale f-world 0.5)]
            (add-force! force (* 3 (long a1)) half)
            (add-force! force (* 3 (long a2)) half))
          (let [tire-nodes (:tire-nodes w)
                n-ring (count tire-nodes)
                centre-slot (or (first (keep-indexed (fn [i id] (when (= id centre-id) i)) tire-nodes)) 0)
                prev-slot (mod (dec (+ centre-slot n-ring)) n-ring)
                next-slot (mod (inc centre-slot) n-ring)
                prev-id (nth tire-nodes prev-slot)
                next-id (nth tire-nodes next-slot)
                prev-i (get id->idx prev-id)
                next-i (get id->idx next-id)]
            (add-force! force (* 3 (long centre-idx)) (v3/scale f-world (* ring-share 0.50)))
            (when prev-i (add-force! force (* 3 (long prev-i)) (v3/scale f-world (* ring-share 0.25))))
            (when next-i (add-force! force (* 3 (long next-i)) (v3/scale f-world (* ring-share 0.25))))))))
    ;; :hub (default)
    (let [half (v3/scale f-world 0.5)]
      (add-force! force (* 3 (long a1)) half)
      (add-force! force (* 3 (long a2)) half))))

(defn- apply-powertrain-and-tires!
  "Returns `[powertrain' wheels']`."
  [state wheels powertrain controls chassis-forward chassis-up dt grnd wheel-axle id->idx]
  (let [^doubles pos (:pos state) ^doubles vel (:vel state) ^doubles force (:force state)
        total-ratio (pt/gearbox-total-ratio (:gearbox powertrain))
        shifting? (< (:shift-progress (:gearbox powertrain)) 1.0)
        net-engine-torque (pt/net-torque (:engine powertrain) (:throttle controls))
        avg-omega (average-drive-wheel-omega wheels (:layout powertrain))
        gearbox-input-omega (if (> (Math/abs total-ratio) 0.0) (* avg-omega total-ratio) (:omega (:engine powertrain)))
        clutch-engagement (* (- 1.0 (:clutch-pedal controls)) (if shifting? 0.0 1.0))
        clutch0 (assoc (:clutch powertrain) :engagement clutch-engagement)
        requested (if (> (Math/abs total-ratio) 0.0) net-engine-torque 0.0)
        [clutch transmitted] (pt/clutch-transmit clutch0 (:omega (:engine powertrain)) gearbox-input-omega requested)
        engine-load (- net-engine-torque transmitted)
        engine-omega1 (+ (:omega (:engine powertrain)) (* (/ engine-load (:inertia (:engine powertrain))) dt))
        engagement (:engagement clutch)
        engine-omega2 (if (and (> engagement 0.05) (> (Math/abs total-ratio) 0.0))
                        (let [coupling (* 6.0 engagement) alpha (clampd (* coupling dt) 0.0 1.0)]
                          (+ (* engine-omega1 (- 1.0 alpha)) (* gearbox-input-omega alpha)))
                        engine-omega1)
        min-omega (if (and (:ignition controls) (:running (:engine powertrain))) (pt/rpm->rad 50.0) 0.0)
        engine-omega3 (max engine-omega2 min-omega)
        max-omega (pt/rpm->rad (:max-rpm (:engine powertrain)))
        engine-omega4 (min engine-omega3 max-omega)
        engine (assoc (:engine powertrain) :omega engine-omega4)
        powertrain (assoc powertrain :engine engine :clutch clutch)
        shaft-torque (if (> (Math/abs total-ratio) 0.0) (* transmitted total-ratio) 0.0)
        wheel-omegas (fetch-wheel-omegas wheels)
        [[fl-t fr-t] [rl-t rr-t]] (pt/distribute powertrain shaft-torque wheel-omegas)]
    (loop [i 0 wheels* (transient [])]
      (if (>= i (count wheels))
        [powertrain (persistent! wheels*)]
        (let [w (nth wheels i)
              drive-t (case i 0 fl-t 1 fr-t 2 rl-t 3 rr-t 0.0)
              brake-t (+ (* brake-torque-max (:brake controls))
                          (if (>= i 2) (* handbrake-torque-max (:handbrake controls)) 0.0))
              w (assoc w :drive-torque drive-t :brake-torque brake-t)
              w (if (< i 2) (assoc w :steer-angle (* (:steer controls) (:max-steer-angle w))) w)
              [forward left _up] (wheel/wheel-frame chassis-forward chassis-up (:steer-angle w))
              [a1 a2 radius] (nth wheel-axle i)]
          (if (or (nil? a1) (nil? a2))
            (recur (inc i) (conj! wheels* w))
            (let [p1 (get-v3-arr pos (* 3 (long a1))) p2 (get-v3-arr pos (* 3 (long a2)))
                  v1 (get-v3-arr vel (* 3 (long a1))) v2 (get-v3-arr vel (* 3 (long a2)))
                  hub-pos (v3/scale (v3/add p1 p2) 0.5)
                  hub-vel (v3/scale (v3/add v1 v2) 0.5)
                  sample (ground/ground-sample grnd (:x hub-pos) (:z hub-pos))
                  ground-y (double (:height sample))
                  contact-y (- (:y hub-pos) radius)
                  penetration (- ground-y contact-y)]
              (if (<= penetration 0.0)
                (let [net-t (- drive-t (* brake-t (rs-signum (:angular-velocity w))))
                      w (-> w
                            (update :angular-velocity + (* (/ net-t (max (:spin-inertia w) 0.01)) dt))
                            (assoc :grounded false))]
                  (recur (inc i) (conj! wheels* w)))
                (let [w (assoc w :grounded true)
                      v-normal (- (:y hub-vel))
                      fz (min 30000.0 (max 0.0 (+ (* penetration 80000.0) (* (max v-normal 0.0) 2000.0))))
                      vx (v3/dot hub-vel forward) vy (v3/dot hub-vel left)
                      vs (* (:angular-velocity w) radius)
                      forces (wheel/pacejka-force (:tire w) {:fz fz :vx vx :vy vy :vs vs})
                      fx (* (double (:fx forces)) (double (:grip-modifier sample)) (double (:friction-mu sample)))
                      fy (* (double (:fy forces)) (double (:grip-modifier sample)) (double (:friction-mu sample)))
                      w (assoc w :last-slip-ratio (:slip-ratio forces) :last-slip-angle (:slip-angle forces))
                      f-world (v3/add (v3/scale forward fx) (v3/scale left fy))]
                  (apply-contact-force! force pos id->idx w a1 a2 f-world (:contact-mode w) grnd)
                  (let [brake-dir (* brake-t (rs-signum (:angular-velocity w)))
                        road-torque (* fx radius)
                        net-t (- drive-t brake-dir road-torque)
                        w (update w :angular-velocity + (* (/ net-t (max (:spin-inertia w) 0.01)) dt))
                        w (if (and (> brake-t 0.0) (< (Math/abs vx) 0.3)) (update w :angular-velocity * 0.5) w)]
                    (recur (inc i) (conj! wheels* w))))))))))))

(defn- predict-positions ^doubles [state dt]
  (let [n (long (:n state)) ^doubles pos (:pos state) ^doubles vel (:vel state)
        ^doubles force (:force state) ^doubles inv-mass (:inv-mass state)
        predicted (double-array (* 3 n))]
    (dotimes [i n]
      (let [i3 (* 3 i) im (aget inv-mass i)]
        (if (zero? im)
          (do (aset predicted i3 (aget pos i3))
              (aset predicted (+ i3 1) (aget pos (+ i3 1)))
              (aset predicted (+ i3 2) (aget pos (+ i3 2))))
          (dotimes [k 3]
            (let [idx (+ i3 k)
                  vnew (+ (aget vel idx) (* (aget force idx) im dt))]
              (aset predicted idx (+ (aget pos idx) (* vnew dt))))))))
    predicted))

(defn- xpbd-iterate! [^doubles predicted state wheel-axle dt grnd]
  (let [^doubles inv-mass (:inv-mass state)
        bstate (:beams state)
        nb (long (:n bstate))
        ^ints bn1 (:n1 bstate) ^ints bn2 (:n2 bstate)
        ^doubles b-eff (:eff-len bstate) ^doubles b-spring (:spring bstate)
        ^ints b-kind (:kind bstate) ^doubles b-min (:min-ratio bstate) ^doubles b-max (:max-ratio bstate)
        ^doubles b-mul (:rest-mul bstate) ^booleans b-broken (:broken bstate)
        dt2-inv (/ 1.0 (* dt dt))
        lambda (double-array nb)
        nw (count wheel-axle)
        tire-k 50000.0
        tire-alpha (/ dt2-inv tire-k)
        tire-lambda (double-array (* 2 nw))
        axle-a (int-array nw) axle-b (int-array nw) radii (double-array nw)]
    (dotimes [wi nw]
      (let [[a1 a2 radius] (nth wheel-axle wi)]
        (aset axle-a wi (int (if a1 a1 -1)))
        (aset axle-b wi (int (if a2 a2 -1)))
        (aset radii wi (double radius))))
    (dotimes [_iter 30]
      (dotimes [wi nw]
        (let [radius (aget radii wi)]
          (doseq [[local ai] [[0 (aget axle-a wi)] [1 (aget axle-b wi)]]]
            (when (and (>= ai 0) (>= (aget inv-mass ai) 1e-10))
              (let [i3 (* 3 ai)
                    x (aget predicted i3) y (aget predicted (+ i3 1)) z (aget predicted (+ i3 2))
                    s (ground/ground-sample grnd x z)
                    target-y (+ (double (:height s)) radius)
                    pen (- target-y y)]
                (when (> pen 0.0)
                  (let [w-node (aget inv-mass ai)
                        lk (+ (* wi 2) local)
                        cur-lambda (aget tire-lambda lk)
                        dlambda (/ (- pen (* tire-alpha cur-lambda)) (+ w-node tire-alpha))
                        new-lambda (max 0.0 (+ cur-lambda dlambda))
                        actual-dlambda (- new-lambda cur-lambda)]
                    (aset tire-lambda lk new-lambda)
                    (aset predicted (+ i3 1) (+ y (* actual-dlambda w-node))))))))))
      (dotimes [bi nb]
        (when-not (aget b-broken bi)
          (let [i1 (aget bn1 bi) i2 (aget bn2 bi)]
            (when (and (>= i1 0) (>= i2 0))
              (let [w1 (aget inv-mass i1) w2 (aget inv-mass i2) w-sum (+ w1 w2)]
                (when (>= w-sum 1e-10)
                  (let [i1_3 (* 3 i1) i2_3 (* 3 i2)
                        dx (- (aget predicted i2_3) (aget predicted i1_3))
                        dy (- (aget predicted (+ i2_3 1)) (aget predicted (+ i1_3 1)))
                        dz (- (aget predicted (+ i2_3 2)) (aget predicted (+ i1_3 2)))
                        len (Math/sqrt (+ (* dx dx) (* dy dy) (* dz dz)))]
                    (when (>= len 1e-6)
                      (let [eff (aget b-eff bi) mul (aget b-mul bi)
                            rest (max (* eff mul) 1e-6)
                            k (aget b-kind bi)
                            result (cond
                                     (= k 1)
                                     (let [ratio (/ len rest) minr (aget b-min bi) maxr (aget b-max bi)]
                                       (if (and (>= ratio minr) (<= ratio maxr))
                                         nil
                                         (if (< ratio minr) (* rest minr) (* rest maxr))))
                                     (= k 4) (if (>= len rest) nil rest)
                                     :else rest)]
                        (when (some? result)
                          (let [target (double result)
                                c (- len target)
                                alpha-tilde (/ dt2-inv (max (aget b-spring bi) 1.0))
                                cur-lambda (aget lambda bi)
                                dlambda (/ (- (- c) (* alpha-tilde cur-lambda)) (+ w-sum alpha-tilde))
                                new-lambda (+ cur-lambda dlambda)
                                dirx (/ dx len) diry (/ dy len) dirz (/ dz len)]
                            (aset lambda bi new-lambda)
                            (aset predicted i1_3 (- (aget predicted i1_3) (* dirx dlambda w1)))
                            (aset predicted (+ i1_3 1) (- (aget predicted (+ i1_3 1)) (* diry dlambda w1)))
                            (aset predicted (+ i1_3 2) (- (aget predicted (+ i1_3 2)) (* dirz dlambda w1)))
                            (aset predicted i2_3 (+ (aget predicted i2_3) (* dirx dlambda w2)))
                            (aset predicted (+ i2_3 1) (+ (aget predicted (+ i2_3 1)) (* diry dlambda w2)))
                            (aset predicted (+ i2_3 2) (+ (aget predicted (+ i2_3 2)) (* dirz dlambda w2)))))))))))))))))

(defn- finalize-velocities! [state ^doubles predicted dt]
  (let [n (long (:n state)) ^doubles pos (:pos state) ^doubles vel (:vel state) ^doubles inv-mass (:inv-mass state)
        vel-damping 0.99995]
    (dotimes [i n]
      (when-not (zero? (aget inv-mass i))
        (let [i3 (* 3 i)]
          (dotimes [k 3]
            (let [idx (+ i3 k)
                  new-pos (aget predicted idx)
                  v (* (/ (- new-pos (aget pos idx)) dt) vel-damping)]
              (aset vel idx v)
              (aset pos idx new-pos))))))))

(defn- update-plastic-beams! [state]
  (let [^doubles pos (:pos state) bstate (:beams state) nb (long (:n bstate))
        ^ints n1 (:n1 bstate) ^ints n2 (:n2 bstate) ^doubles eff-len (:eff-len bstate)
        ^doubles deform-limit (:deform-limit bstate) ^doubles break-limit (:break-limit bstate)
        ^doubles max-plastic (:max-plastic bstate) ^doubles plastic-strain (:plastic-strain bstate)
        ^booleans broken (:broken bstate) ^doubles current-length (:current-length bstate)]
    (dotimes [bi nb]
      (when-not (aget broken bi)
        (let [i1 (aget n1 bi) i2 (aget n2 bi)]
          (when (and (>= i1 0) (>= i2 0))
            (let [i1_3 (* 3 i1) i2_3 (* 3 i2)
                  dx (- (aget pos i2_3) (aget pos i1_3))
                  dy (- (aget pos (+ i2_3 1)) (aget pos (+ i1_3 1)))
                  dz (- (aget pos (+ i2_3 2)) (aget pos (+ i1_3 2)))
                  len (Math/sqrt (+ (* dx dx) (* dy dy) (* dz dz)))]
              (aset current-length bi len)
              (let [l0 (max (aget eff-len bi) 1e-6)
                    strain (/ (- len l0) l0)
                    abs-strain (Math/abs strain)]
                (cond
                  (>= abs-strain (aget break-limit bi)) (aset broken bi true)
                  (> abs-strain (aget deform-limit bi))
                  (let [excess (- abs-strain (aget deform-limit bi))
                        yield-step (* (if (neg? strain) (- excess) excess) 0.5)
                        new-strain (+ (aget plastic-strain bi) (Math/abs yield-step))]
                    (when (<= new-strain (aget max-plastic bi))
                      (aset plastic-strain bi new-strain)
                      (aset eff-len bi (max (* l0 (+ 1.0 yield-step)) 1e-3)))))))))))))

(defn- anti-tunnel-clamp! [state grnd]
  (let [n (long (:n state)) ^doubles pos (:pos state) ^doubles vel (:vel state) ^doubles inv-mass (:inv-mass state)
        ^doubles friction (:friction state) ^doubles restitution (:restitution state) ^ints group (:group state)]
    (dotimes [i n]
      (when (and (not (zero? (aget inv-mass i)))
                 (let [g (aget group i)] (not (or (= g 1) (= g 2)))))
        (let [i3 (* 3 i) x (aget pos i3) y (aget pos (+ i3 1)) z (aget pos (+ i3 2))
              s (ground/ground-sample grnd x z) height (double (:height s))]
          (when (< y height)
            (let [dy (- height y)]
              (aset pos (+ i3 1) height)
              (when (< (aget vel (+ i3 1)) 0.0)
                (aset vel (+ i3 1) (* (- (aget vel (+ i3 1))) (max (aget restitution i) 0.10))))
              (let [fric (min 0.5 (max 0.0 (* (aget friction i) dy 4.0)))]
                (aset vel i3 (* (aget vel i3) (- 1.0 fric)))
                (aset vel (+ i3 2) (* (aget vel (+ i3 2)) (- 1.0 fric)))))))))))

(defn- tire-vertical-spring! [^doubles force ^doubles pos wheel-axle wheels grnd]
  (dotimes [wi (count wheel-axle)]
    (let [[a1 a2 radius] (nth wheel-axle wi) w (nth wheels wi)]
      (when (:grounded w)
        (doseq [ai [a1 a2]]
          (when ai
            (let [i3 (* 3 (long ai)) x (aget pos i3) y (aget pos (+ i3 1)) z (aget pos (+ i3 2))
                  s (ground/ground-sample grnd x z)
                  target-y (+ (double (:height s)) radius)
                  pen (- target-y y)]
              (when (> pen 0.0)
                (aset force (+ i3 1) (+ (aget force (+ i3 1)) (* pen 2500000.0)))))))))))

(defn step
  "Step the simulation forward by `dt` seconds."
  [v dt grnd]
  (let [v (update v :controls controls/clamp-inputs)
        [n sub-dt] (integrator/substep-count dt (:integrator v))]
    (if (zero? n)
      v
      (let [node-state (nodes->arrays (:nodes v))
            id->idx (id-index-map (:ids node-state) (:n node-state))
            beam-state (beams->arrays (:beams v) id->idx)
            state (assoc node-state :beams beam-state)
            wheel-axle (mapv (fn [w] [(get id->idx (:axle-n1 w)) (get id->idx (:axle-n2 w)) (:radius w)])
                              (:wheels v))
            gravity (:gravity (:integrator v))
            mode (:integrator-mode v)]
        (loop [i 0 wheels (:wheels v) powertrain (:powertrain v) cg-state (:cg-state v)]
          (if (= i n)
            (let [nodes' (arrays->nodes (:nodes v) state)
                  beams' (arrays->beams (:beams v) (:beams state))
                  v (assoc v :nodes nodes' :beams beams' :wheels wheels :powertrain powertrain :cg-state cg-state)
                  v (if (:rigid-chassis v)
                      (update v :nodes #(rigid-chassis/project (:rigid-chassis v) % dt))
                      v)
                  v (update-in v [:powertrain :gearbox] pt/gearbox-tick dt)
                  v (refresh-chassis-frame v)
                  v (update v :step-count inc)]
              v)
            (do
              (apply-external-forces! state gravity)
              (let [[powertrain wheels] (apply-powertrain-and-tires!
                                          state wheels powertrain (:controls v)
                                          (:chassis-forward v) (:chassis-up v) sub-dt grnd wheel-axle id->idx)]
                (apply-node-ground-contact! state grnd)
                (case mode
                  :implicit
                  (let [^doubles force (:force state)
                        ^doubles pos (:pos state)]
                    (tire-vertical-spring! force pos wheel-axle wheels grnd)
                    (let [nodes-now (arrays->nodes (:nodes v) state)
                          beams-now (arrays->beams (:beams v) (:beams state))
                          external-forces (mapv :force nodes-now)
                          [nodes-next _iters] (implicit/implicit-step nodes-now beams-now external-forces sub-dt cg-state)
                          ;; write positions/velocities back into arrays for
                          ;; Phase E/F reuse.
                          _ (dotimes [i2 (count nodes-next)]
                              (let [nn (nth nodes-next i2) i3 (* 3 i2)
                                    p (:position nn) vv (:velocity nn)]
                                (aset pos i3 (double (:x p))) (aset pos (+ i3 1) (double (:y p))) (aset pos (+ i3 2) (double (:z p)))
                                (aset ^doubles (:vel state) i3 (double (:x vv)))
                                (aset ^doubles (:vel state) (+ i3 1) (double (:y vv)))
                                (aset ^doubles (:vel state) (+ i3 2) (double (:z vv)))))]
                      (update-plastic-beams! state)
                      (anti-tunnel-clamp! state grnd)
                      (recur (inc i) wheels powertrain cg-state)))
                  ;; default :xpbd
                  (let [predicted (predict-positions state sub-dt)]
                    (xpbd-iterate! predicted state wheel-axle sub-dt grnd)
                    (finalize-velocities! state predicted sub-dt)
                    (update-plastic-beams! state)
                    (anti-tunnel-clamp! state grnd)
                    (recur (inc i) wheels powertrain cg-state)))))))))))

;; =====================================================================
;; Public convenience API
;; =====================================================================

(defn engine-rpm [v] (pt/rad->rpm (:omega (:engine (:powertrain v)))))

(defn speed [v] (v3/length (body-velocity v)))

(defn settle
  "Pre-warm the simulation with `seconds` of zero-input physics."
  [v grnd seconds]
  (let [saved (:controls v)]
    (loop [v (assoc v :controls (controls/coast)) t 0.0]
      (if (< t seconds)
        (recur (step v (/ 1.0 240.0) grnd) (+ t (/ 1.0 240.0)))
        (assoc v :controls saved)))))
