(ns cae.interchange
  "Case provenance for CAD, BIM, equipment, and OpenUSD simulation inputs.

  This namespace deliberately transports references rather than parsing CAD or
  USDA files. Format parsers remain the authority for their own standards;
  CAE needs a small, validated reference that makes a result reproducible and
  tells an orchestration host exactly which scene asset and prim were used."
  (:require [kotoba.lang.text :as str]))

(def supported-sources #{:cad :bim :equipment :openusd})
(def supported-up-axes #{:y-up :z-up})

(defn- nonblank-string? [value]
  (and (string? value) (not (str/blank? value))))

(defn- positive-finite? [value]
  (and (number? value)
       #?(:clj (Double/isFinite (double value))
          :cljs (js/isFinite value))
       (pos? (double value))))

(defn validate-provenance
  "Validate and return portable source provenance.

  Required keys are `:source` (`:cad`, `:bim`, `:equipment`, or `:openusd`)
  and `:asset-uri`. `:openusd` additionally requires an absolute `:prim-path`.
  Optional `:revision`, `:up-axis`, and `:meters-per-unit` make a source
  revision and coordinate conversion explicit."
  [{:keys [source asset-uri prim-path revision up-axis meters-per-unit] :as provenance}]
  (when-not (contains? supported-sources source)
    (throw (ex-info "unsupported simulation provenance source"
                    {:field :source :value source :supported supported-sources})))
  (when-not (nonblank-string? asset-uri)
    (throw (ex-info "simulation provenance requires a non-blank asset URI"
                    {:field :asset-uri :value asset-uri})))
  (when (and revision (not (nonblank-string? revision)))
    (throw (ex-info "simulation provenance revision must be a non-blank string"
                    {:field :revision :value revision})))
  (when (and prim-path (or (not (nonblank-string? prim-path))
                           (not (str/starts-with? prim-path "/"))))
    (throw (ex-info "OpenUSD prim path must be an absolute non-blank path"
                    {:field :prim-path :value prim-path})))
  (when (and (= :openusd source) (nil? prim-path))
    (throw (ex-info "OpenUSD provenance requires :prim-path"
                    {:field :prim-path :source source})))
  (when (and up-axis (not (contains? supported-up-axes up-axis)))
    (throw (ex-info "unsupported provenance up axis"
                    {:field :up-axis :value up-axis :supported supported-up-axes})))
  (when (and meters-per-unit (not (positive-finite? meters-per-unit)))
    (throw (ex-info "meters-per-unit must be finite and positive"
                    {:field :meters-per-unit :value meters-per-unit})))
  provenance)

(defn attach-provenance
  "Return `case` with validated, versioned source provenance.

  Existing physics fields and `:case/id` are preserved. Solvers copy this map
  into their result envelope, allowing CAD/BIM → OpenUSD handoff to remain
  inspectable without coupling the CAE contract to any parser implementation."
  [case provenance]
  (when-not (map? case)
    (throw (ex-info "CAE case must be a map" {:case case})))
  (assoc case :case/provenance (validate-provenance provenance)))
