(ns bim.mep
  "MEP fittings/assemblies and electrical circuit design.")

(def schema-version 1)
(def ^:private pi #?(:clj Math/PI :cljs js/Math.PI))
(defn- sqrt [value] (#?(:clj Math/sqrt :cljs js/Math.sqrt) value))
(defn- acos [value] (#?(:clj Math/acos :cljs js/Math.acos) value))
(defn- math-abs [value] (#?(:clj Math/abs :cljs js/Math.abs) value))
(defn- magnitude [vector] (sqrt (reduce + (map #(* % %) vector))))
(defn- normalize [vector] (let [length (magnitude vector)] (mapv #(/ % length) vector)))
(defn- subtract [a b] (mapv - a b))
(defn- dot [a b] (reduce + (map * a b)))

(defn route-assembly
  "Turn an orthogonal/segmented route into connected segments and elbow
  fittings. End connectors remain available for equipment or branch hookup."
  [{:keys [id system-id domain shape size points bend-radius]}]
  (when (or (< (count points) 2) (some #(not= 3 (count %)) points))
    (throw (ex-info "MEP route requires at least two 3D points" {:id id})))
  (let [points (mapv vec points)
        segment-count (dec (count points))
        fittings
        (mapv (fn [index]
                (let [point (nth points index)
                      incoming (normalize (subtract (nth points (dec index)) point))
                      outgoing (normalize (subtract (nth points (inc index)) point))
                      angle (* (/ 180.0 pi) (acos (max -1.0 (min 1.0 (dot incoming outgoing)))))]
                  {:id (str id "-elbow-" index) :kind :flow-fitting
                   :mep/fitting-kind :elbow :mep/system-id system-id
                   :mep/angle-deg angle :mep/bend-radius (or bend-radius (* 1.5 size))
                   :mep/connectors
                   [{:connector/id (str id "-f" index "-in") :connector/point point
                     :connector/domain domain :connector/shape shape :connector/size size
                     :connector/flow-direction :in
                     :connector/connected-to (str id "-s" (dec index) "-end")}
                    {:connector/id (str id "-f" index "-out") :connector/point point
                     :connector/domain domain :connector/shape shape :connector/size size
                     :connector/flow-direction :out
                     :connector/connected-to (str id "-s" index "-start")}]}))
              (range 1 segment-count))
        segments
        (mapv (fn [index]
                (let [start (nth points index) end (nth points (inc index))]
                  {:id (str id "-segment-" index) :kind :mep-segment
                   :mep/system-id system-id :mep/domain domain :mep/shape shape
                   :mep/size size :geometry {:kind :swept-disk-solid
                                             :directrix [start end] :radius (/ size 2.0)}
                   :mep/connectors
                   [{:connector/id (str id "-s" index "-start") :connector/point start
                     :connector/domain domain :connector/shape shape :connector/size size
                     :connector/flow-direction :in
                     :connector/connected-to (when (pos? index)
                                               (str id "-f" index "-out"))}
                    {:connector/id (str id "-s" index "-end") :connector/point end
                     :connector/domain domain :connector/shape shape :connector/size size
                     :connector/flow-direction :out
                     :connector/connected-to (when (< index (dec segment-count))
                                               (str id "-f" (inc index) "-in"))}]}))
              (range segment-count))]
    {:mep.assembly/id id :mep.assembly/system-id system-id
     :mep.assembly/segments segments :mep.assembly/fittings fittings
     :mep.assembly/open-connectors
     [(get-in segments [0 :mep/connectors 0])
      (get-in segments [(dec segment-count) :mep/connectors 1])]}))

(defn rectangular-route-assembly
  "Turn a routed path into rectangular duct segments and semantic elbows.
  Connector size is the stable `[width height]` cross-section tuple."
  [{:keys [id system-id domain width height points bend-radius]}]
  (when-not (and id system-id domain (number? width) (pos? width)
                 (number? height) (pos? height) (<= 2 (count points))
                 (every? #(and (= 3 (count %)) (every? number? %)) points))
    (throw (ex-info "rectangular MEP route requires identity, size, and 3D points"
                    {:id id :width width :height height :points points})))
  (let [points (mapv vec points)
        segment-count (dec (count points))
        size [width height]
        fittings
        (mapv (fn [index]
                (let [point (nth points index)
                      incoming (normalize (subtract (nth points (dec index)) point))
                      outgoing (normalize (subtract (nth points (inc index)) point))
                      angle (* (/ 180.0 pi)
                               (acos (max -1.0 (min 1.0 (dot incoming outgoing)))))]
                  {:id (str id "-elbow-" index) :kind :flow-fitting
                   :mep/fitting-kind :elbow :mep/system-id system-id
                   :mep/angle-deg angle
                   :mep/bend-radius (or bend-radius (* 1.5 (max width height)))
                   :mep/connectors
                   [{:connector/id (str id "-f" index "-in")
                     :connector/point point :connector/domain domain
                     :connector/shape :rectangular :connector/size size
                     :connector/flow-direction :in
                     :connector/connected-to (str id "-s" (dec index) "-end")}
                    {:connector/id (str id "-f" index "-out")
                     :connector/point point :connector/domain domain
                     :connector/shape :rectangular :connector/size size
                     :connector/flow-direction :out
                     :connector/connected-to (str id "-s" index "-start")}]}))
              (range 1 segment-count))
        segments
        (mapv (fn [index]
                (let [start (nth points index) end (nth points (inc index))
                      axis (subtract end start) length (magnitude axis)]
                  {:id (str id "-segment-" index) :kind :mep-segment
                   :mep/kind :duct :mep/system-id system-id :mep/domain domain
                   :mep/shape :rectangular :mep/width width :mep/height height
                   :geometry {:kind :extruded-area-solid
                              :profile {:kind :rectangle :x-dim width :y-dim height}
                              :position {:location start} :direction axis :depth length}
                   :mep/connectors
                   [{:connector/id (str id "-s" index "-start")
                     :connector/point start :connector/domain domain
                     :connector/shape :rectangular :connector/size size
                     :connector/flow-direction :in
                     :connector/connected-to (when (pos? index)
                                               (str id "-f" index "-out"))}
                    {:connector/id (str id "-s" index "-end")
                     :connector/point end :connector/domain domain
                     :connector/shape :rectangular :connector/size size
                     :connector/flow-direction :out
                     :connector/connected-to (when (< index (dec segment-count))
                                               (str id "-f" (inc index) "-in"))}]}))
              (range segment-count))]
    {:mep.assembly/id id :mep.assembly/system-id system-id
     :mep.assembly/segments segments :mep.assembly/fittings fittings
     :mep.assembly/open-connectors
     [(get-in segments [0 :mep/connectors 0])
      (get-in segments [(dec segment-count) :mep/connectors 1])]}))

(defn network-assembly
  "Generate connected round segments plus elbow, reducer, tee, cross, or
  manifold fittings from an arbitrary node/edge route graph. Edge order is
  retained so connector ids remain stable across deterministic rebuilds."
  [{:keys [id system-id domain nodes edges default-size bend-radius]}]
  (let [edge-ids (map :id edges)]
    (when-not (and id system-id domain (map? nodes) (seq edges))
      (throw (ex-info "MEP network assembly requires identity, nodes, and edges"
                      {:id id :system-id system-id :domain domain})))
    (when-not (= (count edge-ids) (count (distinct edge-ids)))
      (throw (ex-info "MEP network assembly contains duplicate edge ids"
                      {:edge-ids edge-ids})))
    (doseq [[node-id {:keys [point]}] nodes]
      (when-not (and (= 3 (count point)) (every? number? point))
        (throw (ex-info "MEP network node requires a numeric 3D point"
                        {:node-id node-id :point point}))))
    (let [edge-specs
          (mapv (fn [{:keys [id from to size] :as edge}]
                  (let [start (get-in nodes [from :point]) end (get-in nodes [to :point])
                        size (or size (get-in nodes [from :size])
                                 (get-in nodes [to :size]) default-size)]
                    (when-not (and start end (number? size) (pos? size))
                      (throw (ex-info "MEP edge requires existing nodes and a positive size"
                                      {:edge edge :size size})))
                    (when (zero? (magnitude (subtract end start)))
                      (throw (ex-info "MEP edge endpoints must not coincide" {:edge edge})))
                    (assoc edge :size size :start start :end end
                           :start-connector (str id "-start")
                           :end-connector (str id "-end"))))
                edges)
          incidents
          (reduce (fn [result {:keys [id from to size start end
                                      start-connector end-connector]}]
                    (-> result
                        (update from (fnil conj [])
                                {:edge-id id :connector-id start-connector :size size
                                 :direction (normalize (subtract end start))})
                        (update to (fnil conj [])
                                {:edge-id id :connector-id end-connector :size size
                                 :direction (normalize (subtract start end))})))
                  {} edge-specs)
          fitting-kind
          (fn [node-incidents]
            (let [degree (count node-incidents)
                  sizes (set (map :size node-incidents))]
              (case degree
                1 nil
                2 (let [[left right] node-incidents
                        collinear? (> (math-abs (dot (:direction left) (:direction right)))
                                      0.999999)]
                    (cond (> (count sizes) 1) :reducer
                          (not collinear?) :elbow
                          :else nil))
                3 :tee
                4 :cross
                :manifold)))
          fittings
          (into {}
                (keep (fn [[node-id node-incidents]]
                        (when-let [kind (fitting-kind node-incidents)]
                          (let [point (get-in nodes [node-id :point])
                                fitting-id (str id "-fitting-" node-id)
                                connectors
                                (mapv (fn [index incident]
                                        {:connector/id (str fitting-id "-" index)
                                         :connector/point point :connector/domain domain
                                         :connector/shape :round
                                         :connector/size (:size incident)
                                         :connector/flow-direction :bidirectional
                                         :connector/connected-to (:connector-id incident)})
                                      (range) node-incidents)]
                            [node-id
                             {:id fitting-id :kind :flow-fitting
                              :mep/fitting-kind kind :mep/system-id system-id
                              :mep/node-id node-id :mep/point point
                              :mep/bend-radius (when (= :elbow kind)
                                                 (or bend-radius
                                                     (* 1.5 (:size (first node-incidents)))))
                              :mep/connectors connectors}]))))
                incidents)
          fitting-connector-by-segment
          (into {}
                (mapcat (fn [[_ fitting]]
                          (map (juxt :connector/connected-to :connector/id)
                               (:mep/connectors fitting))))
                fittings)
          direct-connector-by-segment
          (into {}
                (mapcat (fn [[node-id node-incidents]]
                          (when (and (= 2 (count node-incidents))
                                     (nil? (get fittings node-id)))
                            (let [[left right] node-incidents]
                              [[(:connector-id left) (:connector-id right)]
                               [(:connector-id right) (:connector-id left)]]))))
                incidents)
          connection-by-segment (merge direct-connector-by-segment
                                       fitting-connector-by-segment)
          segments
          (mapv (fn [{:keys [id from to size start end start-connector end-connector]}]
                  {:id id :kind :mep-segment :mep/system-id system-id
                   :mep/domain domain :mep/shape :round :mep/size size
                   :geometry {:kind :swept-disk-solid :directrix [start end]
                              :radius (/ size 2.0)}
                   :mep/connectors
                   [{:connector/id start-connector :connector/point start
                     :connector/domain domain :connector/shape :round
                     :connector/size size :connector/flow-direction :bidirectional
                     :connector/connected-to
                     (get connection-by-segment start-connector)}
                    {:connector/id end-connector :connector/point end
                     :connector/domain domain :connector/shape :round
                     :connector/size size :connector/flow-direction :bidirectional
                     :connector/connected-to
                     (get connection-by-segment end-connector)}]
                   :mep/from-node from :mep/to-node to})
                edge-specs)
          open-connectors
          (->> segments (mapcat :mep/connectors)
               (filter #(nil? (:connector/connected-to %))) vec)]
      {:mep.assembly/id id :mep.assembly/system-id system-id
       :mep.assembly/segments segments
       :mep.assembly/fittings (vec (sort-by (comp str :mep/node-id) (vals fittings)))
       :mep.assembly/open-connectors open-connectors})))

(defn fluid-section
  "Return flow area and hydraulic diameter for round pipe or rectangular duct."
  [{:keys [shape diameter-m width-m height-m] :as section}]
  (let [[area hydraulic-diameter]
        (case shape
          :round (when (and (number? diameter-m) (pos? diameter-m))
                   [(* pi diameter-m diameter-m 0.25) diameter-m])
          :rectangular
          (when (and (number? width-m) (pos? width-m)
                     (number? height-m) (pos? height-m))
            (let [area (* width-m height-m)]
              [area (/ (* 2.0 width-m height-m) (+ width-m height-m))]))
          nil)]
    (when-not (and area (pos? area) (pos? hydraulic-diameter))
      (throw (ex-info "fluid section requires a positive round or rectangular size"
                      {:section section})))
    {:fluid/area-m2 area :fluid/hydraulic-diameter-m hydraulic-diameter}))

(defn analyze-fluid-route
  "Darcy-Weisbach pressure analysis for a pipe/duct route. Each segment supplies
  length-m and may override section, flow-rate-m3-s, friction-factor and
  fitting-loss-coefficient. Results retain per-segment velocity and losses."
  [{:keys [segments section flow-rate-m3-s density-kg-m3 friction-factor
           max-velocity-m-s max-pressure-loss-pa]
    :or {density-kg-m3 1.204 friction-factor 0.02}}]
  (when-not (and (seq segments) (number? flow-rate-m3-s) (pos? flow-rate-m3-s)
                 (number? density-kg-m3) (pos? density-kg-m3)
                 (number? friction-factor) (pos? friction-factor))
    (throw (ex-info "fluid route requires segments, positive flow, density, and friction"
                    {:flow-rate-m3-s flow-rate-m3-s})))
  (let [results
        (mapv (fn [{:keys [length-m fitting-loss-coefficient] :as segment}]
                (when-not (and (number? length-m) (not (neg? length-m)))
                  (throw (ex-info "fluid segment length must be non-negative"
                                  {:segment segment})))
                (let [{:fluid/keys [area-m2 hydraulic-diameter-m]}
                      (fluid-section (merge section (:section segment)))
                      flow (or (:flow-rate-m3-s segment) flow-rate-m3-s)
                      factor (or (:friction-factor segment) friction-factor)
                      velocity (/ flow area-m2)
                      dynamic-pressure (* 0.5 density-kg-m3 velocity velocity)
                      friction-loss (* factor (/ length-m hydraulic-diameter-m)
                                       dynamic-pressure)
                      fitting-loss (* (or fitting-loss-coefficient 0.0)
                                      dynamic-pressure)]
                  (assoc segment :fluid/flow-rate-m3-s flow
                         :fluid/velocity-m-s velocity
                         :fluid/dynamic-pressure-pa dynamic-pressure
                         :fluid/friction-loss-pa friction-loss
                         :fluid/fitting-loss-pa fitting-loss
                         :fluid/pressure-loss-pa (+ friction-loss fitting-loss))))
              segments)
        total (reduce + (map :fluid/pressure-loss-pa results))
        peak (reduce max 0.0 (map :fluid/velocity-m-s results))
        issues (cond-> []
                 (and max-velocity-m-s (> peak max-velocity-m-s))
                 (conj {:issue :velocity-exceeded :actual peak :limit max-velocity-m-s})
                 (and max-pressure-loss-pa (> total max-pressure-loss-pa))
                 (conj {:issue :pressure-loss-exceeded :actual total
                        :limit max-pressure-loss-pa}))]
    {:fluid/segments results :fluid/total-pressure-loss-pa total
     :fluid/peak-velocity-m-s peak :fluid/issues issues}))

(defn select-fluid-section
  "Select the smallest catalog section satisfying velocity and total pressure
  limits. Catalog entries contain :section plus stable identifying metadata."
  [route catalog {:keys [max-velocity-m-s max-pressure-loss-pa]}]
  (or
   (first
    (keep (fn [entry]
            (let [analysis (analyze-fluid-route
                            (assoc route :section (:section entry)
                                   :max-velocity-m-s max-velocity-m-s
                                   :max-pressure-loss-pa max-pressure-loss-pa))]
              (when (empty? (:fluid/issues analysis))
                {:fluid.selection/catalog-entry entry
                 :fluid.selection/analysis analysis})))
          (sort-by #(-> % :section fluid-section :fluid/area-m2) catalog)))
   (throw (ex-info "no fluid section satisfies design limits"
                   {:max-velocity-m-s max-velocity-m-s
                    :max-pressure-loss-pa max-pressure-loss-pa}))))

(defn- solve-linear-system [matrix values]
  (let [size (count values)]
    (loop [column 0 matrix (mapv vec matrix) values (vec values)]
      (if (= column size)
        (loop [row (dec size) result (vec (repeat size 0.0))]
          (if (neg? row)
            result
            (let [known (reduce + (map (fn [index]
                                         (* (get-in matrix [row index]) (nth result index)))
                                       (range (inc row) size)))]
              (recur (dec row)
                     (assoc result row (/ (- (nth values row) known)
                                          (get-in matrix [row row])))))))
        (let [pivot-row (apply max-key #(math-abs (get-in matrix [% column]))
                               (range column size))
              matrix (assoc matrix column (nth matrix pivot-row)
                            pivot-row (nth matrix column))
              values (assoc values column (nth values pivot-row)
                            pivot-row (nth values column))
              pivot (get-in matrix [column column])]
          (when (< (math-abs pivot) 1.0e-18)
            (throw (ex-info "fluid network Jacobian is singular" {:node-index column})))
          (let [[matrix values]
                (reduce (fn [[current current-values] row]
                          (let [factor (/ (get-in current [row column]) pivot)]
                            [(assoc current row
                                    (mapv - (nth current row)
                                          (mapv #(* factor %) (nth current column))))
                             (assoc current-values row
                                    (- (nth current-values row)
                                       (* factor (nth current-values column))))]))
                        [matrix values] (range (inc column) size))]
            (recur (inc column) matrix values)))))))

(defn fluid-edge-resistance
  "Return quadratic pressure resistance R for Δp = R·q·|q|."
  [{:keys [length-m diameter-m density-kg-m3 friction-factor
           minor-loss-coefficient]}]
  (when-not (and (every? #(and (number? %) (pos? %))
                              [length-m diameter-m density-kg-m3 friction-factor])
                 (or (nil? minor-loss-coefficient)
                     (and (number? minor-loss-coefficient)
                          (not (neg? minor-loss-coefficient)))))
    (throw (ex-info "fluid edge resistance requires positive geometry and fluid data"
                    {:length-m length-m :diameter-m diameter-m})))
  (let [area (* pi diameter-m diameter-m 0.25)
        loss-factor (+ (* friction-factor (/ length-m diameter-m))
                       (or minor-loss-coefficient 0.0))]
    (* loss-factor (/ density-kg-m3 (* 2.0 area area)))))

(defn solve-closed-fluid-network
  "Solve branched or closed-loop fluid flow by the nonlinear nodal-pressure
  method. Edge resistance follows Δp=R·q·|q|; positive node demand extracts
  flow, and one or more source nodes have fixed pressure."
  [{:keys [nodes edges source-pressures demands initial-pressures]
    :as network}
   {:keys [tolerance-m3-s max-iterations pressure-regularization-pa]
    :or {tolerance-m3-s 1.0e-9 max-iterations 100
         pressure-regularization-pa 1.0e-6}}]
  (let [node-set (set nodes)
        edge-ids (map :id edges)
        source-set (set (keys source-pressures))
        unknowns (vec (sort-by str (remove source-set nodes)))
        unknown-index (into {} (map-indexed (fn [index id] [id index]) unknowns))
        resistances
        (into {} (map (fn [edge]
                        [(:id edge) (or (:resistance-pa-per-m3-s2 edge)
                                        (fluid-edge-resistance edge))]) edges))]
    (when-not (and (seq node-set) (= (count nodes) (count node-set))
                   (seq edges) (= (count edge-ids) (count (distinct edge-ids)))
                   (seq source-set) (every? node-set source-set)
                   (every? node-set (keys demands))
                   (every? #(and (node-set (:from %)) (node-set (:to %))
                                 (not= (:from %) (:to %))) edges)
                   (every? #(and (number? %) (pos? %)) (vals resistances))
                   (every? #(and (number? %) (not (neg? %))) (vals demands)))
      (throw (ex-info "invalid closed fluid network" {:network network})))
    (let [minimum-source-pressure (reduce min (vals source-pressures))
          initial (mapv #(or (get initial-pressures %)
                             (- minimum-source-pressure 1000.0)) unknowns)
          evaluate
          (fn [unknown-pressures]
            (let [pressures (merge source-pressures
                                   (zipmap unknowns unknown-pressures))
                  size (count unknowns)
                  base-residual (mapv #(- (or (demands %) 0.0)) unknowns)
                  base-jacobian (vec (repeat size (vec (repeat size 0.0))))]
              (reduce
               (fn [{:keys [flows residual jacobian]} edge]
                 (let [from (:from edge) to (:to edge)
                       delta (- (pressures from) (pressures to))
                       resistance (resistances (:id edge))
                       absolute (math-abs delta)
                       regularized (max absolute pressure-regularization-pa)
                       flow (if (< absolute pressure-regularization-pa)
                              (/ delta (sqrt (* resistance pressure-regularization-pa)))
                              (* (if (neg? delta) -1.0 1.0)
                                 (sqrt (/ absolute resistance))))
                       derivative (if (< absolute pressure-regularization-pa)
                                    (/ 1.0 (sqrt (* resistance pressure-regularization-pa)))
                                    (/ 0.5 (sqrt (* resistance regularized))))
                       from-index (unknown-index from) to-index (unknown-index to)
                       residual (cond-> residual
                                  from-index (update from-index - flow)
                                  to-index (update to-index + flow))
                       jacobian
                       (cond-> jacobian
                         from-index (update-in [from-index from-index] - derivative)
                         (and from-index to-index)
                         (update-in [from-index to-index] + derivative)
                         (and to-index from-index)
                         (update-in [to-index from-index] + derivative)
                         to-index (update-in [to-index to-index] - derivative))]
                   {:flows (assoc flows (:id edge) flow)
                    :residual residual :jacobian jacobian :pressures pressures}))
               {:flows {} :residual base-residual :jacobian base-jacobian
                :pressures pressures} edges)))
          solved
          (loop [iteration 0 pressures initial]
            (let [{:keys [residual] :as state} (evaluate pressures)
                  maximum-residual (reduce max 0.0 (map math-abs residual))]
              (cond
                (<= maximum-residual tolerance-m3-s)
                (assoc state :iterations iteration :maximum-residual maximum-residual)
                (>= iteration max-iterations)
                (throw (ex-info "closed fluid network did not converge"
                                {:iterations iteration :maximum-residual maximum-residual}))
                :else
                (let [correction (solve-linear-system
                                  (:jacobian state) (mapv - residual))]
                  (recur (inc iteration) (mapv + pressures correction))))))
          pressures (:pressures solved)
          flows (:flows solved)
          node-balance
          (reduce (fn [result edge]
                    (let [flow (flows (:id edge))]
                      (-> result (update (:from edge) (fnil - 0.0) flow)
                          (update (:to edge) (fnil + 0.0) flow))))
                  (zipmap nodes (repeat 0.0)) edges)
          source-flows (into {} (map (fn [id] [id (- (node-balance id))]) source-set))
          energy-residuals
          (into {}
                (map (fn [edge]
                       (let [flow (flows (:id edge))]
                         [(:id edge)
                          (- (- (pressures (:from edge)) (pressures (:to edge)))
                             (* (resistances (:id edge)) flow (math-abs flow)))]))
                     edges))]
      {:fluid.network/pressures-pa pressures
       :fluid.network/edge-flows-m3-s flows
       :fluid.network/source-flows-m3-s source-flows
       :fluid.network/edge-energy-residuals-pa energy-residuals
       :fluid.network/node-continuity-m3-s
       (into {} (map (fn [id]
                       [id (- (node-balance id) (or (demands id) 0.0))]) nodes))
       :fluid.network/iterations (:iterations solved)
       :fluid.network/maximum-residual-m3-s (:maximum-residual solved)})))

(defn electrical-circuit
  [{:keys [id name apparent-power-va voltage-v power-factor poles phase
           length-m conductor-area-mm2]}]
  {:circuit/id id :circuit/name name :circuit/apparent-power-va apparent-power-va
   :circuit/voltage-v voltage-v :circuit/power-factor (or power-factor 1.0)
   :circuit/poles (or poles 1) :circuit/phase phase :circuit/length-m length-m
   :circuit/conductor-area-mm2 conductor-area-mm2})

(defn balance-panel
  "Assign unphased single-pole circuits greedily to the least-loaded phase;
  three-pole loads are distributed equally across all panel phases."
  [phases circuits]
  (when-not (and (seq phases) (= (count phases) (count (distinct phases)))
                 (every? #(or (nil? (:circuit/phase %))
                              (contains? (set phases) (:circuit/phase %))) circuits)
                 (every? #(or (not= 3 (:circuit/poles %)) (= 3 (count phases))) circuits))
    (throw (ex-info "panel phases and circuit poles are incompatible"
                    {:phases phases})))
  (let [initial-loads (zipmap phases (repeat 0.0))]
    (reduce
     (fn [{:keys [loads assignments]} circuit]
       (cond
         (= 3 (:circuit/poles circuit))
         {:loads (reduce #(update %1 %2 + (/ (:circuit/apparent-power-va circuit)
                                             (count phases))) loads phases)
          :assignments (assoc assignments (:circuit/id circuit) :three-phase)}

         (:circuit/phase circuit)
         (let [phase (:circuit/phase circuit)]
           {:loads (update loads phase + (:circuit/apparent-power-va circuit))
            :assignments (assoc assignments (:circuit/id circuit) phase)})

         :else
         (let [phase (first (sort-by (juxt loads name) phases))]
           {:loads (update loads phase + (:circuit/apparent-power-va circuit))
            :assignments (assoc assignments (:circuit/id circuit) phase)})))
     {:loads initial-loads :assignments {}}
     (sort-by (juxt (comp - :circuit/apparent-power-va) (comp str :circuit/id)) circuits))))

(defn voltage-drop
  "Copper/aluminium resistive voltage drop for single- or three-phase circuit."
  [{:keys [apparent-power-va voltage-v power-factor poles length-m
           conductor-area-mm2 resistivity-ohm-m]}]
  (let [three-phase? (= poles 3)
        current (/ apparent-power-va (* voltage-v (or power-factor 1.0)
                                        (if three-phase? (sqrt 3.0) 1.0)))
        resistance (/ (* (or resistivity-ohm-m 1.724e-8) length-m)
                      (* conductor-area-mm2 1.0e-6))
        drop (* (if three-phase? (sqrt 3.0) 2.0) current resistance)
        percent (* 100.0 (/ drop voltage-v))]
    {:electrical/current-a current :electrical/voltage-drop-v drop
     :electrical/voltage-drop-percent percent}))

(defn select-circuit-conductor
  "Select the smallest catalog conductor satisfying ampacity and voltage-drop
  limits. Catalog entries require `:area-mm2` and `:ampacity-a`; optional
  resistivity permits copper/aluminium or temperature-adjusted catalogs."
  [circuit catalog max-voltage-drop-percent]
  (when-not (and (seq catalog) (number? max-voltage-drop-percent)
                 (pos? max-voltage-drop-percent))
    (throw (ex-info "conductor catalog and voltage-drop limit are required"
                    {:max-voltage-drop-percent max-voltage-drop-percent})))
  (let [candidates
        (keep (fn [{:keys [area-mm2 ampacity-a resistivity-ohm-m] :as conductor}]
                (when (and (number? area-mm2) (pos? area-mm2)
                           (number? ampacity-a) (pos? ampacity-a))
                  (let [drop (voltage-drop
                              {:apparent-power-va (:circuit/apparent-power-va circuit)
                               :voltage-v (:circuit/voltage-v circuit)
                               :power-factor (:circuit/power-factor circuit)
                               :poles (:circuit/poles circuit)
                               :length-m (:circuit/length-m circuit)
                               :conductor-area-mm2 area-mm2
                               :resistivity-ohm-m resistivity-ohm-m})]
                    (when (and (<= (:electrical/current-a drop) ampacity-a)
                               (<= (:electrical/voltage-drop-percent drop)
                                   max-voltage-drop-percent))
                      {:electrical.conductor/catalog-entry conductor
                       :electrical.conductor/area-mm2 area-mm2
                       :electrical.conductor/ampacity-a ampacity-a
                       :electrical.conductor/current-a (:electrical/current-a drop)
                       :electrical.conductor/voltage-drop-v
                       (:electrical/voltage-drop-v drop)
                       :electrical.conductor/voltage-drop-percent
                       (:electrical/voltage-drop-percent drop)}))))
              catalog)]
    (when-not (seq candidates)
      (throw (ex-info "no conductor satisfies circuit ampacity and voltage drop"
                      {:circuit-id (:circuit/id circuit)
                       :max-voltage-drop-percent max-voltage-drop-percent})))
    (first (sort-by (juxt :electrical.conductor/area-mm2
                          :electrical.conductor/ampacity-a
                          (comp str :id :electrical.conductor/catalog-entry))
                    candidates))))

(defn analyze-panel
  [{:keys [id phases circuits main-rating-a demand-factor max-imbalance-percent
           max-voltage-drop-percent line-voltage-v]}]
  (let [balance (balance-panel phases circuits)
        demanded-loads (into {} (map (fn [[phase load]] [phase (* load (or demand-factor 1.0))])
                                     (:loads balance)))
        phase-voltage (if (= 3 (count phases))
                        (/ (or line-voltage-v (* 230.0 (sqrt 3.0))) (sqrt 3.0))
                        (or line-voltage-v 230.0))
        phase-currents (into {} (map (fn [[phase load]] [phase (/ load phase-voltage)])
                                     demanded-loads))
        maximum (reduce max 0.0 (vals phase-currents)) minimum (reduce min (vals phase-currents))
        average (/ (reduce + (vals phase-currents)) (count phases))
        imbalance (if (zero? average) 0.0 (* 100.0 (/ (- maximum minimum) average)))
        drops (into {} (map (fn [circuit]
                              [(:circuit/id circuit)
                               (voltage-drop {:apparent-power-va (:circuit/apparent-power-va circuit)
                                              :voltage-v (:circuit/voltage-v circuit)
                                              :power-factor (:circuit/power-factor circuit)
                                              :poles (:circuit/poles circuit)
                                              :length-m (:circuit/length-m circuit)
                                              :conductor-area-mm2 (:circuit/conductor-area-mm2 circuit)})])
                            circuits))
        issues (vec (concat
                     (when (> maximum main-rating-a)
                       [{:issue/type :electrical/panel-overload :current-a maximum}])
                     (when (> imbalance (or max-imbalance-percent 20.0))
                       [{:issue/type :electrical/phase-imbalance :percent imbalance}])
                     (for [[circuit-id drop] drops
                           :when (> (:electrical/voltage-drop-percent drop)
                                    (or max-voltage-drop-percent 3.0))]
                       {:issue/type :electrical/voltage-drop :circuit-id circuit-id
                        :percent (:electrical/voltage-drop-percent drop)})))]
    {:panel/id id :panel/assignments (:assignments balance)
     :panel/line-voltage-v (or line-voltage-v
                               (if (= 3 (count phases)) (* 230.0 (sqrt 3.0)) 230.0))
     :panel/phase-voltage-v phase-voltage
     :panel/phase-loads-va demanded-loads :panel/phase-currents-a phase-currents
     :panel/imbalance-percent imbalance :panel/voltage-drops drops :panel/issues issues}))

(defn analyze-electrical-feeder
  "Calculate design current, complex-impedance voltage drop, and prospective
  short-circuit current for a single- or three-phase feeder."
  [{:keys [id phases apparent-power-va voltage-v power-factor length-m
           resistance-ohm-m reactance-ohm-m source-resistance-ohm
           source-reactance-ohm cable-ampacity-a max-voltage-drop-percent]
    :or {phases 3 power-factor 1.0 reactance-ohm-m 0.0
         source-resistance-ohm 0.0 source-reactance-ohm 0.0
         max-voltage-drop-percent 3.0}}]
  (when-not (and id (#{1 3} phases) (pos? (or apparent-power-va 0.0))
                 (pos? (or voltage-v 0.0)) (< 0.0 power-factor) (<= power-factor 1.0)
                 (not (neg? (or length-m -1.0)))
                 (not (neg? (or resistance-ohm-m -1.0)))
                 (not (neg? reactance-ohm-m))
                 (pos? (or cable-ampacity-a 0.0)))
    (throw (ex-info "invalid electrical feeder design input" {:feeder-id id})))
  (let [three-phase? (= 3 phases)
        root-three (sqrt 3.0)
        current (/ apparent-power-va (* voltage-v (if three-phase? root-three 1.0)))
        sine (sqrt (max 0.0 (- 1.0 (* power-factor power-factor))))
        voltage-drop (* (if three-phase? root-three 2.0) current length-m
                        (+ (* resistance-ohm-m power-factor)
                           (* reactance-ohm-m sine)))
        voltage-drop-percent (* 100.0 (/ voltage-drop voltage-v))
        loop-factor (if three-phase? 1.0 2.0)
        fault-r (+ source-resistance-ohm (* loop-factor length-m resistance-ohm-m))
        fault-x (+ source-reactance-ohm (* loop-factor length-m reactance-ohm-m))
        fault-impedance (sqrt (+ (* fault-r fault-r) (* fault-x fault-x)))
        _ (when-not (pos? fault-impedance)
            (throw (ex-info "feeder fault-loop impedance must be positive"
                            {:feeder-id id})))
        fault-current (/ voltage-v (* (if three-phase? root-three 1.0)
                                      fault-impedance))
        issues (vec (concat
                     (when (> current cable-ampacity-a)
                       [{:issue/type :electrical/cable-overload
                         :design-current-a current :cable-ampacity-a cable-ampacity-a}])
                     (when (> voltage-drop-percent max-voltage-drop-percent)
                       [{:issue/type :electrical/feeder-voltage-drop
                         :percent voltage-drop-percent
                         :maximum-percent max-voltage-drop-percent}])))]
    {:electrical.feeder/id id :electrical.feeder/phases phases
     :electrical.feeder/design-current-a current
     :electrical.feeder/cable-ampacity-a cable-ampacity-a
     :electrical.feeder/voltage-drop-v voltage-drop
     :electrical.feeder/voltage-drop-percent voltage-drop-percent
     :electrical.feeder/fault-resistance-ohm fault-r
     :electrical.feeder/fault-reactance-ohm fault-x
     :electrical.feeder/fault-impedance-ohm fault-impedance
     :electrical.feeder/prospective-fault-current-a fault-current
     :electrical.feeder/issues issues}))

(defn select-protective-device
  "Select the smallest protective device satisfying Ib ≤ In ≤ Iz, breaking
  capacity, and optional instantaneous fault-clearing criteria."
  [feeder-analysis catalog]
  (let [design-current (:electrical.feeder/design-current-a feeder-analysis)
        cable-ampacity (:electrical.feeder/cable-ampacity-a feeder-analysis)
        fault-current (:electrical.feeder/prospective-fault-current-a feeder-analysis)
        candidates
        (filter (fn [{:keys [rating-a breaking-capacity-a
                             instantaneous-trip-multiple]}]
                  (and (number? rating-a) (<= design-current rating-a cable-ampacity)
                       (number? breaking-capacity-a) (>= breaking-capacity-a fault-current)
                       (or (nil? instantaneous-trip-multiple)
                           (<= (* rating-a instantaneous-trip-multiple) fault-current))))
                catalog)]
    (when-not (seq candidates)
      (throw (ex-info "no protective device satisfies feeder duty"
                      {:design-current-a design-current :cable-ampacity-a cable-ampacity
                       :fault-current-a fault-current})))
    (let [device (first (sort-by (juxt :rating-a :breaking-capacity-a (comp str :id))
                                 candidates))]
      {:electrical.protection/device device
       :electrical.protection/load-margin-a (- (:rating-a device) design-current)
       :electrical.protection/cable-margin-a (- cable-ampacity (:rating-a device))
       :electrical.protection/breaking-margin-a
       (- (:breaking-capacity-a device) fault-current)
       :electrical.protection/instantaneous-threshold-a
       (when-let [multiple (:instantaneous-trip-multiple device)]
         (* (:rating-a device) multiple))})))

(defn check-protection-coordination
  "Check simple instantaneous selectivity between downstream and upstream
  devices at the calculated downstream fault current."
  [downstream upstream fault-current-a]
  (let [threshold (fn [device]
                    (when-let [multiple (:instantaneous-trip-multiple device)]
                      (* (:rating-a device) multiple)))
        downstream-threshold (threshold downstream)
        upstream-threshold (threshold upstream)
        downstream-trips? (and downstream-threshold
                               (<= downstream-threshold fault-current-a))
        upstream-restrained? (or (:selective-delay? upstream)
                                 (and upstream-threshold
                                      (> upstream-threshold fault-current-a)))
        coordinated? (and (> (:rating-a upstream) (:rating-a downstream))
                          downstream-trips? upstream-restrained?)]
    {:electrical.coordination/downstream-id (:id downstream)
     :electrical.coordination/upstream-id (:id upstream)
     :electrical.coordination/fault-current-a fault-current-a
     :electrical.coordination/downstream-threshold-a downstream-threshold
     :electrical.coordination/upstream-threshold-a upstream-threshold
     :electrical.coordination/coordinated? (boolean coordinated?)}))

(defn analyze-electrical-distribution
  "Analyze a radial source-panel → feeder → downstream-panel hierarchy.
  Downstream diversified loads roll up into upstream panels and feeders;
  results include phase balance, voltage drop, fault duty, selected protection,
  and pairwise upstream/downstream protection coordination."
  [{:keys [root-panel panels feeders protective-device-catalog]}]
  (let [panel-by-id (into {} (map (juxt :id identity) panels))
        feeder-ids (map :id feeders)
        children (group-by :from feeders)
        parent-feeder (into {} (map (juxt :to identity) feeders))
        panel-ids (set (keys panel-by-id))]
    (when-not (and (panel-by-id root-panel)
                   (= (count panels) (count panel-by-id))
                   (= (count feeders) (count (distinct feeder-ids)))
                   (every? #(and (panel-by-id (:from %)) (panel-by-id (:to %))
                                 (not= (:from %) (:to %))) feeders)
                   (every? #(= 1 %) (vals (frequencies (map :to feeders))))
                   (nil? (parent-feeder root-panel)))
      (throw (ex-info "invalid radial electrical distribution topology"
                      {:root-panel root-panel})))
    (let [reachable
          (loop [pending [root-panel] visited #{}]
            (if-let [panel-id (peek pending)]
              (if (visited panel-id)
                (recur (pop pending) visited)
                (recur (into (pop pending) (map :to (children panel-id)))
                       (conj visited panel-id)))
              visited))]
      (when-not (= reachable panel-ids)
        (throw (ex-info "electrical distribution has cycles or unreachable panels"
                        {:unreachable (set (remove reachable panel-ids))})))
      (let [local-load
            (fn [panel]
              (* (or (:demand-factor panel) 1.0)
                 (reduce + 0.0 (map :circuit/apparent-power-va (:circuits panel)))))
            downstream-load
            (fn downstream-load [panel-id]
              (+ (local-load (panel-by-id panel-id))
                 (reduce + 0.0 (map #(downstream-load (:to %))
                                    (children panel-id)))))
            loads (into {} (map (fn [id] [id (downstream-load id)]) panel-ids))
            feeder-order
            (loop [pending [root-panel] result []]
              (if-let [panel-id (first pending)]
                (let [outgoing (vec (sort-by (comp str :id) (children panel-id)))]
                  (recur (into (subvec (vec pending) 1) (map :to outgoing))
                         (into result outgoing)))
                result))
            feeder-results
            (reduce (fn [result feeder]
                      (let [target (panel-by-id (:to feeder))
                            upstream (parent-feeder (:from feeder))
                            upstream-analysis
                            (get-in result [(:id upstream)
                                            :electrical.distribution/analysis])
                            source-r (or (:source-resistance-ohm feeder)
                                         (:electrical.feeder/fault-resistance-ohm
                                          upstream-analysis)
                                         0.0)
                            source-x (or (:source-reactance-ohm feeder)
                                         (:electrical.feeder/fault-reactance-ohm
                                          upstream-analysis)
                                         0.0)
                               analysis
                               (analyze-electrical-feeder
                                (merge feeder
                                       {:apparent-power-va (loads (:to feeder))
                                        :voltage-v (or (:voltage-v feeder)
                                                       (:line-voltage-v target))
                                        :source-resistance-ohm source-r
                                        :source-reactance-ohm source-x}))
                               protection (select-protective-device
                                           analysis protective-device-catalog)]
                        (assoc result (:id feeder)
                               {:electrical.distribution/feeder feeder
                                :electrical.distribution/downstream-load-va
                                (loads (:to feeder))
                                :electrical.distribution/analysis analysis
                                :electrical.distribution/protection protection})))
                    {} feeder-order)
            panel-results
            (into {}
                  (map (fn [panel]
                         (let [child-circuits
                               (mapv (fn [feeder]
                                       (electrical-circuit
                                        {:id [:feeder (:id feeder)]
                                         :name (str "Feeder " (:id feeder))
                                         :apparent-power-va (loads (:to feeder))
                                         :voltage-v (:line-voltage-v panel)
                                         :power-factor (or (:power-factor feeder) 1.0)
                                         :poles (if (= 3 (count (:phases panel))) 3 1)
                                         :length-m 0.0 :conductor-area-mm2 1.0}))
                                     (children (:id panel)))
                               result (analyze-panel
                                       {:id (:id panel) :phases (:phases panel)
                                        :circuits (vec (concat (:circuits panel) child-circuits))
                                        :main-rating-a (:main-rating-a panel)
                                        :demand-factor 1.0
                                        :line-voltage-v (:line-voltage-v panel)
                                        :max-imbalance-percent (:max-imbalance-percent panel)
                                        :max-voltage-drop-percent
                                        (:max-voltage-drop-percent panel)})]
                           [(:id panel)
                            (assoc result :panel/local-load-va (local-load panel)
                                          :panel/downstream-load-va (loads (:id panel)))]))
                       panels))
            coordinations
            (into {}
                  (keep (fn [feeder]
                          (when-let [upstream-feeder (parent-feeder (:from feeder))]
                            (let [downstream-device
                                  (get-in feeder-results
                                          [(:id feeder) :electrical.distribution/protection
                                           :electrical.protection/device])
                                  upstream-device
                                  (get-in feeder-results
                                          [(:id upstream-feeder)
                                           :electrical.distribution/protection
                                           :electrical.protection/device])
                                  fault-current
                                  (get-in feeder-results
                                          [(:id feeder) :electrical.distribution/analysis
                                           :electrical.feeder/prospective-fault-current-a])]
                              [(:id feeder)
                               (check-protection-coordination
                                downstream-device upstream-device fault-current)])))
                        feeders))
            issues
            (vec
             (concat
              (mapcat :panel/issues (vals panel-results))
              (mapcat #(get-in % [:electrical.distribution/analysis
                                  :electrical.feeder/issues])
                      (vals feeder-results))
              (for [[feeder-id result] coordinations
                    :when (not (:electrical.coordination/coordinated? result))]
                {:issue/type :electrical/protection-not-coordinated
                 :issue/feeder feeder-id})))]
        {:electrical.distribution/root-panel root-panel
         :electrical.distribution/total-load-va (loads root-panel)
         :electrical.distribution/panels panel-results
         :electrical.distribution/feeders feeder-results
         :electrical.distribution/coordinations coordinations
         :electrical.distribution/issues issues}))))
