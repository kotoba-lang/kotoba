(ns kami-engine.cfd.contract)

(def solvers #{:lbm :rom-buildup :rans :les :dns :external})
(def dims #{2 3})
(def geometries #{:block :teardrop :box3d :fastback3d :ahmed :stl :mesh})
(def statuses #{:ok :denied :failed})

(def request-keys
  #{:kami.cfd/solver
    :kami.cfd/dim
    :kami.cfd/geometry
    :kami.cfd/reynolds
    :kami.cfd/steps
    :kami.cfd/mesh
    :kami.cfd/options})

(def result-keys
  #{:kami.cfd/solver
    :kami.cfd/dim
    :kami.cfd/geometry
    :kami.cfd/sectional-cd
    :kami.cfd/vehicle-cd
    :kami.cfd/frontal-cells
    :kami.cfd/steps
    :kami.cfd/status
    :kami.cfd/message})

(defn- positive-number? [x]
  (and (number? x) (pos? x) (= x x)))

(defn- positive-int? [x]
  (and (int? x) (pos? x)))

(defn- err [path code message]
  {:path path :code code :message message})

(defn validate-request [request]
  (let [unknowns (remove request-keys (keys request))
        errors (cond-> []
                 (not (map? request))
                 (conj (err [] :not-map "request must be a map"))

                 (not (contains? solvers (:kami.cfd/solver request)))
                 (conj (err [:kami.cfd/solver] :invalid "unknown CFD solver"))

                 (not (contains? dims (:kami.cfd/dim request)))
                 (conj (err [:kami.cfd/dim] :invalid "dimension must be 2 or 3"))

                 (not (contains? geometries (:kami.cfd/geometry request)))
                 (conj (err [:kami.cfd/geometry] :invalid "unknown geometry"))

                 (not (positive-number? (:kami.cfd/reynolds request)))
                 (conj (err [:kami.cfd/reynolds] :invalid "Reynolds number must be positive"))

                 (not (positive-int? (:kami.cfd/steps request)))
                 (conj (err [:kami.cfd/steps] :invalid "steps must be a positive integer"))

                 (and (= :stl (:kami.cfd/geometry request))
                      (not (string? (:kami.cfd/mesh request))))
                 (conj (err [:kami.cfd/mesh] :required "STL geometry requires a mesh path"))

                 (seq unknowns)
                 (into (map #(err [%] :unknown "unknown kami.cfd request key") unknowns)))]
    {:valid? (empty? errors) :errors errors}))

(defn request? [request]
  (:valid? (validate-request request)))

(defn validate-result [result]
  (let [unknowns (remove result-keys (keys result))
        has-cd? (or (positive-number? (:kami.cfd/sectional-cd result))
                    (positive-number? (:kami.cfd/vehicle-cd result)))
        errors (cond-> []
                 (not (map? result))
                 (conj (err [] :not-map "result must be a map"))

                 (not (contains? solvers (:kami.cfd/solver result)))
                 (conj (err [:kami.cfd/solver] :invalid "unknown CFD solver"))

                 (not (contains? dims (:kami.cfd/dim result)))
                 (conj (err [:kami.cfd/dim] :invalid "dimension must be 2 or 3"))

                 (not (contains? geometries (:kami.cfd/geometry result)))
                 (conj (err [:kami.cfd/geometry] :invalid "unknown geometry"))

                 (not (contains? statuses (:kami.cfd/status result)))
                 (conj (err [:kami.cfd/status] :invalid "status must be known"))

                 (and (= :ok (:kami.cfd/status result)) (not has-cd?))
                 (conj (err [:kami.cfd/vehicle-cd] :required "successful result needs a positive Cd"))

                 (and (contains? result :kami.cfd/steps)
                      (not (positive-int? (:kami.cfd/steps result))))
                 (conj (err [:kami.cfd/steps] :invalid "steps must be a positive integer"))

                 (seq unknowns)
                 (into (map #(err [%] :unknown "unknown kami.cfd result key") unknowns)))]
    {:valid? (empty? errors) :errors errors}))

(defn result? [result]
  (:valid? (validate-result result)))

(defn same-run? [request result]
  (and (request? request)
       (result? result)
       (= (select-keys request [:kami.cfd/solver :kami.cfd/dim :kami.cfd/geometry])
          (select-keys result [:kami.cfd/solver :kami.cfd/dim :kami.cfd/geometry]))))

(defn cd [result]
  (or (:kami.cfd/vehicle-cd result)
      (:kami.cfd/sectional-cd result)))

(defn lower-drag? [a b]
  (and (result? a)
       (result? b)
       (< (cd a) (cd b))))
