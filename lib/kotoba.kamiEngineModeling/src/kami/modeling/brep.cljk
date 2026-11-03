(ns kami.modeling.brep
  "Boundary-representation topology with stable identities and analytic surface
  contracts. B-rep is canonical; polygon meshes are derived projections."
  (:require [kami.modeling :as modeling]
            [kami.modeling.document :as document]))

(def analytic-surface-kinds #{:plane :cylinder :cone :sphere :torus :nurbs})
(def ^:private pi #?(:clj Math/PI :cljs js/Math.PI))
(defn- absolute [x] (#?(:clj Math/abs :cljs js/Math.abs) x))
(defn- sqrt [x] (#?(:clj Math/sqrt :cljs js/Math.sqrt) x))

(defn- vec3? [x] (and (vector? x) (= 3 (count x)) (every? number? x)))
(defn- unit-axis? [x]
  (and (vec3? x) (< (absolute (- 1.0 (sqrt (reduce + (map #(* % %) x))))) 1.0e-9)))

(defn analytic-surface [kind parameters]
  (when-not (analytic-surface-kinds kind)
    (throw (ex-info "unsupported analytic surface" {:kind kind})))
  (let [valid? (case kind
                 :plane (and (vec3? (:origin parameters)) (unit-axis? (:normal parameters)))
                 :cylinder (and (vec3? (:origin parameters)) (unit-axis? (:axis parameters))
                                (pos? (:radius parameters 0)))
                 :cone (and (vec3? (:apex parameters)) (unit-axis? (:axis parameters))
                            (< 0 (:half-angle parameters 0) (/ pi 2)))
                 :sphere (and (vec3? (:center parameters)) (pos? (:radius parameters 0)))
                 :torus (and (vec3? (:center parameters)) (unit-axis? (:axis parameters))
                             (pos? (:major-radius parameters 0)) (pos? (:minor-radius parameters 0))
                             (> (:major-radius parameters) (:minor-radius parameters)))
                 :nurbs (= :surface (:nurbs/kind (:surface parameters))))]
    (when-not valid? (throw (ex-info "invalid analytic surface parameters" {:kind kind :parameters parameters})))
    {:surface/kind kind :surface/parameters parameters}))

(defn vertex [id point tolerance]
  (when-not (and (uuid? id) (vec3? point) (number? tolerance) (pos? tolerance))
    (throw (ex-info "invalid B-rep vertex" {:id id :point point :tolerance tolerance})))
  {:vertex/id id :vertex/point point :vertex/tolerance tolerance})

(defn edge [id start end curve]
  (when-not (and (uuid? id) (uuid? start) (uuid? end) (map? curve)
                 (or (not= start end) (#{:circle :ellipse :periodic} (:curve/kind curve))))
    (throw (ex-info "invalid B-rep edge" {:id id :start start :end end})))
  {:edge/id id :edge/start start :edge/end end :edge/curve curve})

(defn coedge [edge-id orientation]
  (when-not (and (uuid? edge-id) (#{:forward :reversed} orientation))
    (throw (ex-info "invalid coedge" {:edge edge-id :orientation orientation})))
  {:coedge/edge edge-id :coedge/orientation orientation})

(defn topology-loop [id coedges]
  (when-not (and (uuid? id) (seq coedges))
    (throw (ex-info "invalid B-rep loop" {:id id})))
  {:loop/id id :loop/coedges (vec coedges)})

(defn face [id surface outer-loop inner-loops orientation]
  (when-not (and (uuid? id) (map? surface) (uuid? outer-loop)
                 (every? uuid? inner-loops) (#{:forward :reversed} orientation))
    (throw (ex-info "invalid B-rep face" {:id id :surface surface :outer-loop outer-loop
                                           :inner-loops inner-loops :orientation orientation})))
  {:face/id id :face/surface surface :face/outer-loop outer-loop
   :face/inner-loops (vec inner-loops) :face/orientation orientation})

(defn shell [id face-ids closed?]
  (when-not (and (uuid? id) (seq face-ids) (every? uuid? face-ids) (boolean? closed?))
    (throw (ex-info "invalid B-rep shell" {:id id})))
  {:shell/id id :shell/faces (vec face-ids) :shell/closed? closed?})

(defn body [id vertices edges loops faces shells]
  {:brep/id id :brep/vertices (into {} (map (juxt :vertex/id identity) vertices))
   :brep/edges (into {} (map (juxt :edge/id identity) edges))
   :brep/loops (into {} (map (juxt :loop/id identity) loops))
   :brep/faces (into {} (map (juxt :face/id identity) faces))
   :brep/shells (into {} (map (juxt :shell/id identity) shells))})

(defn- oriented-endpoints [edge orientation]
  (if (= :forward orientation) [(:edge/start edge) (:edge/end edge)]
      [(:edge/end edge) (:edge/start edge)]))

(defn validation-errors [body]
  (let [{:brep/keys [id vertices edges loops faces shells]} body
        errors (transient [])
        add! #(conj! errors %)]
    (when-not (uuid? id) (add! {:error :invalid-body-id :id id}))
    (doseq [[edge-id e] edges]
      (when-not (contains? vertices (:edge/start e)) (add! {:error :missing-edge-vertex :edge edge-id :vertex (:edge/start e)}))
      (when-not (contains? vertices (:edge/end e)) (add! {:error :missing-edge-vertex :edge edge-id :vertex (:edge/end e)})))
    (doseq [[loop-id loop] loops]
      (let [segments (mapv (fn [{:coedge/keys [edge orientation]}]
                             (when-let [e (get edges edge)] (oriented-endpoints e orientation)))
                           (:loop/coedges loop))]
        (when (some nil? segments) (add! {:error :missing-loop-edge :loop loop-id}))
        (when (and (every? some? segments)
                   (not (every? true? (map (fn [[_ end] [start _]] (= end start))
                                            segments (concat (rest segments) [(first segments)])))))
          (add! {:error :open-or-misoriented-loop :loop loop-id}))))
    (doseq [[face-id f] faces]
      (doseq [loop-id (into [(:face/outer-loop f)] (:face/inner-loops f))]
        (when-not (contains? loops loop-id) (add! {:error :missing-face-loop :face face-id :loop loop-id}))))
    (doseq [[shell-id s] shells]
      (doseq [face-id (:shell/faces s)]
        (when-not (contains? faces face-id) (add! {:error :missing-shell-face :shell shell-id :face face-id})))
      (when (:shell/closed? s)
        (let [edge-use (frequencies (for [face-id (:shell/faces s)
                                          loop-id (when-let [f (get faces face-id)]
                                                    (into [(:face/outer-loop f)] (:face/inner-loops f)))
                                          coedge (:loop/coedges (get loops loop-id))]
                                      (:coedge/edge coedge)))]
          (doseq [[edge-id uses] edge-use]
            (when-not (= 2 uses) (add! {:error :non-manifold-shell-edge :shell shell-id :edge edge-id :uses uses}))))))
    (persistent! errors)))

(defn valid-body? [body] (empty? (validation-errors body)))

(defn- distance [a b]
  (#?(:clj Math/sqrt :cljs js/Math.sqrt) (reduce + (map (fn [x y] (let [d (- x y)] (* d d))) a b))))

(defn tolerance-diagnostics [body tolerance]
  (when-not (pos? tolerance) (throw (ex-info "healing tolerance must be positive" {})))
  (let [vertices (vec (vals (:brep/vertices body)))
        near (vec (for [i (range (count vertices)) j (range (inc i) (count vertices))
                        :let [a (nth vertices i) b (nth vertices j) d (distance (:vertex/point a) (:vertex/point b))]
                        :when (<= d tolerance)]
                    {:diagnostic :near-duplicate-vertices :keep (:vertex/id a) :merge (:vertex/id b) :distance d}))
        zero-edges (vec (keep (fn [[id e]]
                                (let [a (get-in body [:brep/vertices (:edge/start e) :vertex/point])
                                      b (get-in body [:brep/vertices (:edge/end e) :vertex/point])]
                                  (when (and a b (<= (distance a b) tolerance))
                                    {:diagnostic :degenerate-edge :edge id :length (distance a b)})))
                              (:brep/edges body)))]
    (into near zero-edges)))

(defn heal-body
  "Merge near-duplicate vertices and rewire edges. Healing never deletes
  degenerate edges silently: such a result fails with structured diagnostics."
  [body tolerance]
  (let [near (filter #(= :near-duplicate-vertices (:diagnostic %)) (tolerance-diagnostics body tolerance))
        replacement (reduce (fn [m {:keys [keep merge]}]
                              (let [canonical (get m keep keep)] (assoc m merge canonical))) {} near)
        resolve-id (fn resolve-id [id] (if-let [next (get replacement id)]
                                        (if (= next id) id (resolve-id next)) id))
        rewritten-edges (into {} (map (fn [[id e]]
                                        [id (-> e (update :edge/start resolve-id) (update :edge/end resolve-id))])
                                      (:brep/edges body)))
        degenerate (vec (for [[id e] rewritten-edges :when (= (:edge/start e) (:edge/end e))]
                          {:diagnostic :degenerate-edge-after-heal :edge id :vertex (:edge/start e)}))]
    (when (seq degenerate) (throw (ex-info "B-rep healing produced degenerate edges" {:diagnostics degenerate})))
    (let [removed (set (keys replacement))
          healed (assoc body :brep/vertices (apply dissoc (:brep/vertices body) removed)
                             :brep/edges rewritten-edges
                             :brep/healing {:tolerance tolerance :merged (count removed)})
          errors (validation-errors healed)]
      (when (seq errors) (throw (ex-info "B-rep healing produced invalid topology" {:errors errors})))
      healed)))

(defn box-body
  "Create a closed analytic six-face B-rep box with stable topology IDs."
  [namespace width depth height tolerance]
  (when-not (every? pos? [width depth height tolerance])
    (throw (ex-info "box dimensions and tolerance must be positive" {})))
  (let [uid #(document/stable-uuid namespace %)
        points [[0 0 0] [width 0 0] [width depth 0] [0 depth 0]
                [0 0 height] [width 0 height] [width depth height] [0 depth height]]
        vs (mapv (fn [i p] (vertex (uid (str "v" i)) p tolerance)) (range 8) points)
        pairs [[0 1] [1 2] [2 3] [3 0] [4 5] [5 6] [6 7] [7 4] [0 4] [1 5] [2 6] [3 7]]
        es (mapv (fn [i [a b]] (edge (uid (str "e" i)) (uid (str "v" a)) (uid (str "v" b))
                                      {:curve/kind :line})) (range 12) pairs)
        ;; Each loop follows its boundary. Edge orientation is explicit.
        rings [[[0 :forward] [1 :forward] [2 :forward] [3 :forward]]
               [[4 :forward] [5 :forward] [6 :forward] [7 :forward]]
               [[0 :forward] [9 :forward] [4 :reversed] [8 :reversed]]
               [[1 :forward] [10 :forward] [5 :reversed] [9 :reversed]]
               [[2 :forward] [11 :forward] [6 :reversed] [10 :reversed]]
               [[3 :forward] [8 :forward] [7 :reversed] [11 :reversed]]]
        ls (mapv (fn [i ring] (topology-loop (uid (str "l" i))
                                              (mapv (fn [[e o]] (coedge (uid (str "e" e)) o)) ring))) (range 6) rings)
        surfaces [(analytic-surface :plane {:origin [0 0 0] :normal [0 0 -1]})
                  (analytic-surface :plane {:origin [0 0 height] :normal [0 0 1]})
                  (analytic-surface :plane {:origin [0 0 0] :normal [0 -1 0]})
                  (analytic-surface :plane {:origin [width 0 0] :normal [1 0 0]})
                  (analytic-surface :plane {:origin [width depth 0] :normal [0 1 0]})
                  (analytic-surface :plane {:origin [0 depth 0] :normal [-1 0 0]})]
        fs (mapv (fn [i surface] (face (uid (str "f" i)) surface (uid (str "l" i)) [] :forward))
                 (range 6) surfaces)]
    (body (uid "body") vs es ls fs [(shell (uid "shell") (mapv :face/id fs) true)])))

(defn tessellate-box [body]
  (when-not (valid-body? body) (throw (ex-info "cannot tessellate invalid B-rep" {:errors (validation-errors body)})))
  (let [vertex-ids (vec (keys (:brep/vertices body))) id->index (zipmap vertex-ids (range))
        vertices (mapv #(get-in body [:brep/vertices % :vertex/point]) vertex-ids)
        face-ids (vec (keys (:brep/faces body)))
        faces (mapv (fn [face-id]
                      (let [loop-id (get-in body [:brep/faces face-id :face/outer-loop])]
                        (mapv (fn [{:coedge/keys [edge orientation]}]
                                (id->index (first (oriented-endpoints (get-in body [:brep/edges edge]) orientation))))
                              (get-in body [:brep/loops loop-id :loop/coedges])))) face-ids)]
    (assoc (modeling/mesh vertices faces) :mesh/source {:kind :brep :body (:brep/id body)
                                                        :face-ids face-ids})))
