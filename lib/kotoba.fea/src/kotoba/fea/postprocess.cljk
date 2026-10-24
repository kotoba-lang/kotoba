(ns kotoba.fea.postprocess
  "Post-processing — cljc port of kami-cae's `postprocess` module
  (kami-engine, retired per ADR-2607010000). Result fields are keywords:
  `:displacement` `:von-mises-stress` `:principal-stress` `:strain`
  `:temperature` `:mode-shape` `:safety-factor`, matching kami-cae's
  `ResultField` enum. No network, no I/O."
  (:require [kotoba.fea.vec3 :as v3]))

(def result-fields
  #{:displacement :von-mises-stress :principal-stress :strain
    :temperature :mode-shape :safety-factor})

(defn field-range
  "Compute `{:min :max :avg}` from a collection of scalar `values`.
  `{:min 0.0 :max 0.0 :avg 0.0}` for an empty collection."
  [values]
  (if (empty? values)
    {:min 0.0 :max 0.0 :avg 0.0}
    {:min (reduce min values)
     :max (reduce max values)
     :avg (/ (reduce + values) (count values))}))

(defn probe-point
  "Interpolate a displacement result at an arbitrary point.

  kami-cae's own implementation only had access to `AnalysisResult`
  (displacements, no node positions) at this call site, so instead of the
  documented inverse-distance weighting it fell back to returning the
  average displacement across all nodes (`_point` unused) — ported
  verbatim, including that limitation. For a real inverse-distance
  interpolation that uses the mesh's node positions, see
  `probe-point-idw`."
  [result _point]
  (if (empty? (:displacement result))
    v3/zero
    (let [ds (:displacement result)]
      (v3/scale (reduce v3/add v3/zero ds) (/ 1.0 (count ds))))))

(def provenance-required-keys
  "Keys that must be present (non-nil) in a provenance map handed to
  [[factor-of-safety]]: where the allowable came from and which failure
  mode it bounds. No default is ever substituted — an unprovenanced
  allowable is not an allowable (same rule as `kotoba.fea.convergence`,
  which requires a caller-owned `fs`)."
  [:source :basis])

(defn- require-allowable!
  [{:keys [allowable-stress provenance] :as _opts}]
  (when-not (number? allowable-stress)
    (throw (ex-info "factor-of-safety: :allowable-stress [Pa] is required and must be a number"
                    {:type :missing-allowable})))
  (when-not (pos? allowable-stress)
    (throw (ex-info "factor-of-safety: :allowable-stress must be positive"
                    {:type :invalid-allowable :allowable-stress allowable-stress})))
  (when-not (and (map? provenance)
                 (every? #(contains? provenance %) provenance-required-keys)
                 (string? (:source provenance))
                 (seq (:source provenance)))
    (throw (ex-info (str "factor-of-safety: :provenance must carry "
                         provenance-required-keys
                         " — an unprovenanced allowable is not an allowable")
                    {:type :missing-provenance
                     :required provenance-required-keys
                     :provenance provenance}))))

(defn factor-of-safety
  "Per-element factor of safety against a **caller-supplied, provenance-carrying**
  allowable stress. This is the executable counterpart of
  [[export-color-map-data]]'s `:safety-factor` path, which keeps a
  hardcoded 250 MPa mild-steel placeholder for kami-cae parity — that
  placeholder must never be used to grade a real design.

      stresses (per-element, e.g. solver's von Mises values)
      opts    {:allowable-stress 570.0e6        ; Pa — e.g. AZ31B yield, from a
                                                ;      dated source the caller owns
               :provenance {:source \"AMS 4375, 2026-09 retrieval\"
                            :basis :yield}}

  Returns {:factors [...]                       ; allowable / stress per element,
                                                ; ##Inf where stress <= 0 (no load
                                                ; seen — matches export-color-map-data)
           :min-factor {:value v :element idx}  ; governing element (nil if all Inf)
           :allowable-stress a :provenance p}

  Fails closed with `ex-info` `:type` `:missing-allowable`
  `:invalid-allowable` or `:missing-provenance`. No physical constant is
  invented here; the allowable and its provenance are the caller's."
  [stresses {:keys [allowable-stress provenance] :as opts}]
  (require-allowable! opts)
  (when-not (sequential? stresses)
    (throw (ex-info "factor-of-safety: stresses must be a sequential collection"
                    {:type :invalid-stresses})))
  (let [factors (mapv (fn [s] (if (pos? s) (/ allowable-stress s) ##Inf)) stresses)
        governing (first (sort-by :value (keep-indexed
                                          (fn [i f] (when (< f ##Inf) {:value f :element i}))
                                          factors)))]
    {:factors factors
     :min-factor governing
     :allowable-stress allowable-stress
     :provenance provenance}))


(def default-idw-power
  "Default inverse-distance weighting exponent (Shepard's method)."
  2.0)

(defn probe-point-idw
  "Inverse-distance-weighted interpolation of a displacement result at an
  arbitrary 3-D `point`, using `mesh`'s node positions — the production
  implementation kami-cae's `probe_point` documented but never had the
  data for (see `probe-point`). Removes that limitation without changing
  `probe-point`'s behavior for existing callers.

  Assumptions preserved from the rest of this library (stated, not
  invented): `:displacement` is indexed by node id in `:nodes` order,
  positions and displacements share one length unit (SI: m), and the
  interpolation is a nodal field approximation — element shape functions
  are NOT used, so the interpolated value inside a coarse element can
  differ from the true FE solution there. This is a field probe, not a
  stress recovery.

  `opts` map (optional):
  - `:power`  — weighting exponent p in w_i = 1/d_i^p. Default
    `default-idw-power` (2.0, Shepard's method). Must be positive.
  - `:radius` — if given, only nodes within this distance contribute
    (length unit same as positions); nodes beyond it are ignored.

  Returns `{:displacement [x y z] :contributing-nodes n}` where
  `:contributing-nodes` reports how many nodes carried weight — call it
  an uncertainty signal: 1 means the point sits on (or is extrapolating
  from) a single node and the value is that node's displacement, not an
  interpolation.

  Edge behavior:
  - empty result / empty mesh → zero displacement, 0 contributing nodes.
  - `point` coincides with a node → that node's displacement exactly
    (d_i = 0 would blow up the weights, so it short-circuits).
  - fewer than 1 contributing node under `:radius` → zero displacement
    with `:contributing-nodes 0` (the probe is outside the sampled
    neighborhood; we do not silently extrapolate)."
  ([mesh result point] (probe-point-idw mesh result point {}))
  ([mesh result point {:keys [power radius] :or {power default-idw-power}}]
   (let [ds (:displacement result)
         nodes (:nodes mesh)]
     (if (or (empty? ds) (empty? nodes))
       {:displacement v3/zero :contributing-nodes 0}
       (let [weighted
             (reduce
              (fn [acc node]
                (let [d (v3/length (v3/sub (:position node) point))
                      ;; a mesh node with no matching result entry is
                      ;; skipped — never index-out-of-bounds on a
                      ;; partially-populated result
                      disp (nth ds (:id node) nil)]
                  (cond
                    (nil? disp) acc
                    ;; exact hit: d == 0 short-circuits the weight sum
                    (== d 0.0) (reduced {:exact disp})
                    (and radius (>= d radius)) acc
                    :else
                    (let [w (/ 1.0 (Math/pow d power))]
                      (-> acc
                          (update :wsum + w)
                          (update :dsum v3/add (v3/scale disp w))
                          (update :count inc))))))
              {:wsum 0.0 :dsum v3/zero :count 0}
              nodes)]
         (cond
           (:exact weighted) {:displacement (:exact weighted)
                              :contributing-nodes 1}
           (zero? (:count weighted)) {:displacement v3/zero
                                      :contributing-nodes 0}
           :else {:displacement (v3/scale (:dsum weighted)
                                          (/ 1.0 (:wsum weighted)))
                  :contributing-nodes (:count weighted)}))))))

(defn export-color-map-data
  "Build per-node/per-element scalar data suitable for rendering via a
  color-map pipeline (kami-cae targeted `kami-eng-render`; left as plain
  data here — rendering is a host-adapter concern, see README).

  For `:displacement` the scalar is the displacement magnitude at each
  node. For element-based fields (`:von-mises-stress` `:strain` etc.) the
  values are per element (caller may average to nodes)."
  [result field]
  (case field
    :displacement (mapv v3/length (:displacement result))
    (:von-mises-stress :principal-stress) (vec (:stress result))
    :strain (vec (:strain result))
    :safety-factor
    ;; Safety factor = yield / stress. Placeholder yield of 250 MPa (mild
    ;; steel), matching kami-cae.
    (let [yield-stress 250.0e6]
      (mapv (fn [s] (if (> s 0.0) (/ yield-stress s) ##Inf)) (:stress result)))
    (:temperature :mode-shape)
    ;; Not computed by the linear-static solver; return zeros.
    (vec (repeat (count (:displacement result)) 0.0))))
