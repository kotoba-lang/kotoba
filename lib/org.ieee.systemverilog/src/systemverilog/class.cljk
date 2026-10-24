(ns systemverilog.class
  "SystemVerilog (IEEE 1800) minimal class modeling: fields plus
  method *signatures* (no bodies -- this is a data model, not an
  interpreter), and single-inheritance (`extends`) resolution
  (IEEE 1800 clause 8).")

(defn make-class
  ([name fields methods] (make-class name nil fields methods))
  ([name extends fields methods]
   {:name name :extends extends :fields (vec fields) :methods (vec methods)}))

(defn- ancestry
  "Walk the `:extends` chain from `class-name` through `registry`
  (a map of class-name -> class map), most-derived first. Stops if a
  name is missing from the registry or a cycle is detected, so a
  dangling/cyclic `:extends` degrades to \"just this class\" instead
  of looping forever."
  [registry class-name]
  (loop [chain [] current class-name seen #{}]
    (if (or (nil? current) (contains? seen current))
      chain
      (if-let [cls (get registry current)]
        (recur (conj chain cls) (:extends cls) (conj seen current))
        chain))))

(defn- merge-by-name
  "Layer `derived` members onto `base` members: a derived member with
  the same `:name` as a base member overrides it in place (SystemVerilog
  method/field override), and a derived member with a new `:name` is
  appended."
  [base derived]
  (let [index-of (into {} (map-indexed (fn [i m] [(:name m) i]) base))]
    (reduce
     (fn [acc m]
       (if-let [i (get index-of (:name m))]
         (assoc acc i m)
         (conj acc m)))
     (vec base)
     derived)))

(defn resolve-members
  "Flatten the `:fields`/`:methods` of `class-name` by walking its
  single-inheritance chain through `registry`, base class first so
  that more-derived classes override same-named members (single-
  inheritance MRO)."
  [registry class-name]
  (let [base-to-derived (reverse (ancestry registry class-name))]
    (reduce
     (fn [acc cls]
       (-> acc
           (update :fields merge-by-name (:fields cls))
           (update :methods merge-by-name (:methods cls))))
     {:fields [] :methods []}
     base-to-derived)))
