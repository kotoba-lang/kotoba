(ns spice.analysis
  "DC operating-point analysis via Modified Nodal Analysis (MNA) + Gaussian
  elimination with partial pivoting. Restored from kami-spice's `analysis`
  module (deleted PR #82). Matrix ops use plain nested vectors — circuit
  sizes here are node-count scale (tens, not per-pixel/per-frame), matching
  ADR-2607010930's 'coarse-grained dispatch' CLJC scope, not a hot loop.

  Nonlinear devices (diode/MOSFET/BJT) are solved via `solve-dc-op-nonlinear`,
  which re-linearizes each device into a companion conductance + equivalent
  current source (the standard SPICE MNA technique) at every Newton-Raphson
  iteration and re-solves the same linear MNA system. `solve-dc-op` itself
  remains the pure-linear fast path (unchanged behavior — it still ignores
  nonlinear devices entirely) so existing linear-circuit callers/tests are
  unaffected.")

(defn- build-node-map
  "Sorted non-ground net name -> matrix index. Includes diode/MOSFET/BJT
  terminal nodes (harmless additive extension for purely-linear circuits,
  which have no such elements — `solve-dc-op`'s own stamp loop still never
  touches them) so `solve-dc-op-nonlinear` can size/guess the full system."
  [circuit]
  (let [nodes (->> (:elements circuit)
                    (mapcat (fn [{:keys [kind n1 n2 n-pos n-neg
                                          gate drain source bulk
                                          collector base emitter
                                          anode cathode]}]
                              (case kind
                                (:resistor :capacitor :inductor) [n1 n2]
                                (:voltage-source :current-source) [n-pos n-neg]
                                :mosfet [gate drain source bulk]
                                :bjt [collector base emitter]
                                :diode [anode cathode]
                                nil)))
                    (remove nil?)
                    (remove #(or (= % "0") (= % "gnd")))
                    (into (sorted-set)))]
    (into {} (map-indexed (fn [i n] [n i]) nodes))))

(defn- node-idx [node-map name]
  (when-not (or (= name "0") (= name "gnd"))
    (get node-map name)))

(defn- mat-set [mat r c v] (assoc-in mat [r c] v))
(defn- mat-get [mat r c] (get-in mat [r c]))
(defn- mat-add [mat r c v] (update-in mat [r c] + v))

(defn- gaussian-eliminate
  "Gaussian elimination with partial pivoting on augmented `size x (size+1)`
  matrix `mat`. Returns the reduced matrix (mutates conceptually — actually
  threads a fresh persistent matrix through)."
  [mat size]
  (reduce
   (fn [mat col]
     (let [max-row (reduce (fn [best row]
                              (if (> (Math/abs (double (mat-get mat row col)))
                                      (Math/abs (double (mat-get mat best col))))
                                row best))
                            col (range (inc col) size))
           mat (if (= max-row col) mat
                 (assoc mat col (nth mat max-row) max-row (nth mat col)))
           pivot (mat-get mat col col)]
       (if (< (Math/abs (double pivot)) 1e-15)
         mat
         (reduce
          (fn [mat row]
            (let [factor (/ (mat-get mat row col) pivot)]
              (reduce (fn [mat j] (mat-add mat row j (- (* factor (mat-get mat col j)))))
                      mat (range col (inc size)))))
          mat (range (inc col) size)))))
   mat (range size)))

(defn- back-substitute [mat size]
  (reduce
   (fn [x i]
     (let [row (nth mat i)
           sum (reduce (fn [s j] (- s (* (nth row j) (nth x j))))
                       (nth row size)
                       (range (inc i) size))
           diag (nth row i)]
       (assoc x i (if (> (Math/abs (double diag)) 1e-15) (/ sum diag) 0.0))))
   (vec (repeat size 0.0))
   (range (dec size) -1 -1)))

(defn solve-dc-op
  "Solve DC operating point via MNA + Gaussian elimination. Returns
  `{:node-voltages {name -> [v]} :branch-currents {vsrc-name -> [i]}
  :time-points []}`. Nonlinear devices (MOSFET/BJT/diode) are ignored in
  this linear DC-op solve (matches the original — this fast path stays
  purely linear on purpose). For circuits containing nonlinear devices,
  use `solve-dc-op-nonlinear`, which solves them via Newton-Raphson."
  [circuit]
  (let [node-map (build-node-map circuit)
        n (count node-map)
        vsrcs (filterv #(= :voltage-source (:kind %)) (:elements circuit))
        vsrc-count (count vsrcs)
        size (+ n vsrc-count)
        mat0 (vec (repeat size (vec (repeat (inc size) 0.0))))
        [mat _]
        (reduce
         (fn [[mat vsrc-idx] el]
           (case (:kind el)
             :resistor
             (let [g (/ 1.0 (:value el))
                   a (node-idx node-map (:n1 el))
                   b (node-idx node-map (:n2 el))
                   mat (cond-> mat
                         a (mat-add a a g)
                         b (mat-add b b g)
                         (and a b) (mat-add a b (- g))
                         (and a b) (mat-add b a (- g)))]
               [mat vsrc-idx])

             :voltage-source
             (let [row (+ n vsrc-idx)
                   a (node-idx node-map (:n-pos el))
                   b (node-idx node-map (:n-neg el))
                   mat (cond-> mat
                         a (-> (mat-add row a 1.0) (mat-add a row 1.0))
                         b (-> (mat-add row b -1.0) (mat-add b row -1.0)))
                   mat (mat-set mat row size (:dc-value el))]
               [mat (inc vsrc-idx)])

             :current-source
             (let [a (node-idx node-map (:n-pos el))
                   b (node-idx node-map (:n-neg el))
                   mat (cond-> mat
                         a (mat-add a size (- (:dc-value el)))
                         b (mat-add b size (:dc-value el)))]
               [mat vsrc-idx])

             ;; MOSFET/BJT/diode: nonlinear, skipped in linear DC op
             [mat vsrc-idx]))
         [mat0 0]
         (:elements circuit))
        mat (gaussian-eliminate mat size)
        x (back-substitute mat size)
        node-voltages (into {} (map (fn [[name idx]] [name [(nth x idx)]]) node-map))
        branch-currents (into {}
                               (map-indexed
                                (fn [i vsrc] [(:name vsrc) [(nth x (+ n i))]])
                                vsrcs))]
    {:node-voltages node-voltages :branch-currents branch-currents :time-points []}))

;; ---------------------------------------------------------------------
;; Nonlinear DC-op via Newton-Raphson
;;
;; Each nonlinear device is re-linearized every iteration into a companion
;; MNA model around the previous iteration's node-voltage guess: a
;; conductance (or transconductance, for 3-terminal devices) plus an
;; equivalent current source, exactly like the classic SPICE diode/BJT/
;; MOSFET companion-model technique. The resulting *linear* system is then
;; solved with the same `gaussian-eliminate`/`back-substitute` used above.
;;
;; Stated simplifications (this is an educational restore, not full SPICE):
;;   - Diode: Shockley equation only, no series resistance, no junction
;;     capacitance, no reverse breakdown. Exponential argument clamped to
;;     +-40 so far-off NR guesses can't overflow `Math/exp`.
;;   - MOSFET: simple square-law (Level-1-style) model, NO channel-length
;;     modulation (lambda=0) and NO body effect; ideal (zero DC current)
;;     gate.
;;   - BJT: simplified Ebers-Moll, FORWARD-ACTIVE REGION ONLY (no
;;     saturation/cutoff/reverse-active regions, no Early effect).
;;   - No temperature sweep — thermal voltage `Vt` is a fixed room-temp
;;     constant (0.02585 V) throughout.
;; ---------------------------------------------------------------------

(def ^:private diode-defaults {:is 1e-14 :n 1.0 :vt 0.02585})
(def ^:private mosfet-defaults {:vth 0.7 :kp 2e-4})
(def ^:private bjt-defaults {:is 1e-16 :beta 100.0 :vt 0.02585})

(def ^:private nr-max-iterations 100)
(def ^:private nr-tolerance 1e-6)
;; Damped-Newton per-node voltage-step cap (V). Starting the NR guess at
;; V=0 linearizes exponential diode/BJT junctions at (effectively) an open
;; circuit; the resulting first raw solve can put the junction voltage far
;; out on the exponential, whose companion conductance is then so large
;; that an *undamped* update overshoots past the true root and oscillates
;; forever instead of converging (verified empirically while designing
;; this solver — a plain undamped update on a 5V/1k-ohm/diode circuit
;; settles into a 2-cycle around 2.44V and never converges). Capping the
;; step at a modest, fixed voltage is the standard, simple fix; circuits
;; with larger legitimate voltage swings just take a few more iterations
;; to walk there — the pure-linear case (whose matrix doesn't depend on
;; the guess at all) still converges well within `nr-max-iterations`.
(def ^:private nr-max-step 1.0)

(defn- clamp [x lo hi] (max lo (min hi x)))

(defn- diode-companion
  "Shockley diode companion model at guessed junction voltage `v` (anode
  minus cathode). Returns `{:g conductance :ieq equivalent-current}` for
  the standard `I(V) ~= g*V + ieq` linearization about `v`."
  [el v]
  (let [is (or (:is el) (:is diode-defaults))
        n (or (:n el) (:n diode-defaults))
        vt (or (:vt el) (:vt diode-defaults))
        arg (clamp (/ v (* n vt)) -40.0 40.0)
        ev (Math/exp arg)
        i (* is (- ev 1.0))
        g (/ (* is ev) (* n vt))]
    {:g g :ieq (- i (* g v))}))

(defn- mosfet-companion
  "Square-law NMOS companion model (no channel-length modulation, no body
  effect) at guessed `vgs`/`vds`. Returns `{:gm :gds :ieq :id}` for the
  linearization `Id ~= gm*Vgs + gds*Vds + ieq` about (`vgs`, `vds`)."
  [el vgs vds]
  (let [vth (or (:vth el) (:vth mosfet-defaults))
        kp (or (:kp el) (:kp mosfet-defaults))
        vov (- vgs vth)]
    (cond
      (<= vgs vth) ;; cutoff
      {:gm 0.0 :gds 0.0 :ieq 0.0 :id 0.0}

      (>= vds vov) ;; saturation
      (let [id (* 0.5 kp vov vov)
            gm (* kp vov)
            gds 0.0]
        {:gm gm :gds gds :ieq (- id (* gm vgs) (* gds vds)) :id id})

      :else ;; triode/linear region
      (let [id (* kp (- (* vov vds) (/ (* vds vds) 2.0)))
            gm (* kp vds)
            gds (* kp (- vov vds))]
        {:gm gm :gds gds :ieq (- id (* gm vgs) (* gds vds)) :id id}))))

(defn- bjt-companion
  "Simplified Ebers-Moll NPN companion model, forward-active region only,
  at guessed `vbe`. Returns `{:gc :gb :ieq-c :ieq-b :ic :ib}` where `:gc`/
  `:ieq-c` linearize the collector current (`Ic ~= gc*Vbe + ieq-c`) and
  `:gb`/`:ieq-b` linearize the base current (`Ib = Ic/beta`, so it's the
  same exponential scaled by `1/beta`)."
  [el vbe]
  (let [is (or (:is el) (:is bjt-defaults))
        beta (or (:beta el) (:beta bjt-defaults))
        vt (or (:vt el) (:vt bjt-defaults))
        arg (clamp (/ vbe vt) -40.0 40.0)
        ev (Math/exp arg)
        ic (* is ev)
        ib (/ ic beta)
        gc (/ ic vt)
        gb (/ gc beta)]
    {:gc gc :gb gb :ieq-c (- ic (* gc vbe)) :ieq-b (- ib (* gb vbe)) :ic ic :ib ib}))

(defn- guess-v
  "Guessed voltage at `name` (0.0 for ground or an unguessed node)."
  [guess name]
  (if (or (= name "0") (= name "gnd")) 0.0 (get guess name 0.0)))

(defn- stamp-branch
  "Stamp a two-terminal branch carrying constant-linearized current
  `g*(V-from - V-to) + ieq`, flowing from `from` toward `to`, into `mat`
  (generalizes the resistor conductance stamp + current-source stamp
  above into one helper — used for the diode)."
  [mat node-map size from to g ieq]
  (let [a (node-idx node-map from)
        b (node-idx node-map to)]
    (cond-> mat
      a (mat-add a a g)
      b (mat-add b b g)
      (and a b) (mat-add a b (- g))
      (and a b) (mat-add b a (- g))
      a (mat-add a size (- ieq))
      b (mat-add b size ieq))))

(defn- stamp-mosfet
  "Stamp a linearized MOSFET (`Id ~= gm*Vgs + gds*Vds + ieq`, flowing from
  drain to source) into `mat`. Ideal gate — zero DC gate current, so the
  gate row is untouched; bulk is untouched too (no body effect, stated
  simplification)."
  [mat node-map size el vgs vds]
  (let [{:keys [gm gds ieq]} (mosfet-companion el vgs vds)
        d (node-idx node-map (:drain el))
        g (node-idx node-map (:gate el))
        s (node-idx node-map (:source el))]
    (cond-> mat
      ;; row d: current leaving drain into the device = Id
      d (mat-add d d gds)
      (and d g) (mat-add d g gm)
      (and d s) (mat-add d s (- (+ gds gm)))
      d (mat-add d size (- ieq))
      ;; row s: current leaving source into the device = -Id
      (and s d) (mat-add s d (- gds))
      (and s g) (mat-add s g (- gm))
      s (mat-add s s (+ gds gm))
      s (mat-add s size ieq))))

(defn- stamp-bjt
  "Stamp a linearized forward-active NPN BJT (controlled solely by
  `Vbe = Vbase - Vemitter`) into `mat`: `Ic` flows into the collector,
  `Ib = Ic/beta` flows into the base, and `Ie = Ic+Ib` flows out of the
  emitter."
  [mat node-map size el vbe]
  (let [{:keys [gc gb ieq-c ieq-b]} (bjt-companion el vbe)
        ge (+ gc gb)
        ieq-e (+ ieq-c ieq-b)
        c (node-idx node-map (:collector el))
        b (node-idx node-map (:base el))
        e (node-idx node-map (:emitter el))]
    (cond-> mat
      ;; row c: current leaving collector into the device = Ic
      (and c b) (mat-add c b gc)
      (and c e) (mat-add c e (- gc))
      c (mat-add c size (- ieq-c))
      ;; row b: current leaving base into the device = Ib
      b (mat-add b b gb)
      (and b e) (mat-add b e (- gb))
      b (mat-add b size (- ieq-b))
      ;; row e: current leaving emitter into the device = -Ie
      (and e b) (mat-add e b (- ge))
      e (mat-add e e ge)
      e (mat-add e size ieq-e))))

(defn- build-mna
  "Build the full augmented MNA matrix for `circuit`, linearizing any
  nonlinear devices around the per-node `guess` voltage map. Identical
  resistor/voltage-source/current-source stamps as `solve-dc-op`, plus
  diode/MOSFET/BJT companion-model stamps evaluated at `guess`."
  [circuit node-map n vsrcs guess]
  (let [size (+ n (count vsrcs))
        mat0 (vec (repeat size (vec (repeat (inc size) 0.0))))]
    (first
     (reduce
      (fn [[mat vsrc-idx] el]
        (case (:kind el)
          :resistor
          (let [g (/ 1.0 (:value el))
                a (node-idx node-map (:n1 el))
                b (node-idx node-map (:n2 el))
                mat (cond-> mat
                      a (mat-add a a g)
                      b (mat-add b b g)
                      (and a b) (mat-add a b (- g))
                      (and a b) (mat-add b a (- g)))]
            [mat vsrc-idx])

          :voltage-source
          (let [row (+ n vsrc-idx)
                a (node-idx node-map (:n-pos el))
                b (node-idx node-map (:n-neg el))
                mat (cond-> mat
                      a (-> (mat-add row a 1.0) (mat-add a row 1.0))
                      b (-> (mat-add row b -1.0) (mat-add b row -1.0)))
                mat (mat-set mat row size (:dc-value el))]
            [mat (inc vsrc-idx)])

          :current-source
          (let [a (node-idx node-map (:n-pos el))
                b (node-idx node-map (:n-neg el))
                mat (cond-> mat
                      a (mat-add a size (- (:dc-value el)))
                      b (mat-add b size (:dc-value el)))]
            [mat vsrc-idx])

          :diode
          (let [va (guess-v guess (:anode el))
                vk (guess-v guess (:cathode el))
                {:keys [g ieq]} (diode-companion el (- va vk))
                mat (stamp-branch mat node-map size (:anode el) (:cathode el) g ieq)]
            [mat vsrc-idx])

          :mosfet
          (let [vg (guess-v guess (:gate el))
                vd (guess-v guess (:drain el))
                vs (guess-v guess (:source el))
                mat (stamp-mosfet mat node-map size el (- vg vs) (- vd vs))]
            [mat vsrc-idx])

          :bjt
          (let [vb (guess-v guess (:base el))
                ve (guess-v guess (:emitter el))
                mat (stamp-bjt mat node-map size el (- vb ve))]
            [mat vsrc-idx])

          [mat vsrc-idx]))
      [mat0 0]
      (:elements circuit)))))

(defn solve-dc-op-nonlinear
  "Solve DC operating point via Newton-Raphson. Nonlinear devices (diode/
  MOSFET/BJT) are re-linearized into a companion MNA model every iteration
  around the previous iteration's node-voltage guess (see the namespace
  docstring for the exact device equations and stated simplifications);
  the resulting linear system is solved via the same `gaussian-eliminate`/
  `back-substitute` as `solve-dc-op`. Convergence uses damped Newton (each
  node's per-iteration voltage step is capped at a fixed `nr-max-step`) to
  avoid the divergence a plain undamped update produces when the initial
  V=0 guess puts a diode/BJT junction far out on its exponential.

  For a purely-linear circuit the matrix doesn't depend on the guess at
  all, so this converges to the exact same answer `solve-dc-op` gives
  (just via however many damped steps it takes to walk the guess to the
  true node voltages).

  Returns `{:node-voltages {name -> [v]} :branch-currents {vsrc-name ->
  [i]} :time-points [] :iterations n :converged? bool}` — a superset of
  `solve-dc-op`'s return shape (additive `:iterations`/`:converged?`
  keys)."
  [circuit]
  (let [node-map (build-node-map circuit)
        n (count node-map)
        vsrcs (filterv #(= :voltage-source (:kind %)) (:elements circuit))
        size (+ n (count vsrcs))
        node-names (keys node-map)]
    (loop [iter 0
           guess (zipmap node-names (repeat 0.0))]
      (let [mat (gaussian-eliminate (build-mna circuit node-map n vsrcs guess) size)
            x (back-substitute mat size)
            raw (into {} (map (fn [[name idx]] [name (nth x idx)]) node-map))
            deltas (into {} (map (fn [nm] [nm (- (get raw nm 0.0) (get guess nm 0.0))]) node-names))
            max-delta (if (seq deltas)
                        (apply max 0.0 (map #(Math/abs (double %)) (vals deltas)))
                        0.0)
            converged? (< max-delta nr-tolerance)
            last-iter? (>= iter (dec nr-max-iterations))]
        (if (or converged? last-iter?)
          (let [node-voltages (into {} (map (fn [[name idx]] [name [(nth x idx)]]) node-map))
                branch-currents (into {}
                                       (map-indexed
                                        (fn [i vsrc] [(:name vsrc) [(nth x (+ n i))]])
                                        vsrcs))]
            {:node-voltages node-voltages
             :branch-currents branch-currents
             :time-points []
             :iterations (inc iter)
             :converged? converged?})
          (recur (inc iter)
                 (into {}
                       (map (fn [nm]
                              [nm (+ (get guess nm 0.0)
                                     (clamp (get deltas nm 0.0) (- nr-max-step) nr-max-step))])
                            node-names))))))))
