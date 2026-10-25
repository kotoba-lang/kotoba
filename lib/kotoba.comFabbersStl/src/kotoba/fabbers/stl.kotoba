(ns kotoba.fabbers.stl
  "Portable STL boundary: inspect and normalize geometry without a native CAD kernel.")

(defn- number* [s] #?(:clj (Double/parseDouble s) :cljs (js/parseFloat s)))
(defn- finite? [n] #?(:clj (Double/isFinite (double n)) :cljs (js/isFinite n)))

(defn payload-format [payload]
  (cond (string? payload) :ascii
        #?(:cljs (instance? js/Uint8Array payload) :clj (instance? (Class/forName "[B") payload)) :binary
        :else :unknown))

(defn- triples [xs] (mapv (fn [[x y z]] [(number* x) (number* y) (number* z)]) (partition 3 xs)))

(defn parse-ascii [source]
  (let [vertices (triples (mapcat rest (re-seq #"(?i)vertex\s+([-+0-9.eE]+)\s+([-+0-9.eE]+)\s+([-+0-9.eE]+)" source)))
        normals (triples (mapcat rest (re-seq #"(?i)facet\s+normal\s+([-+0-9.eE]+)\s+([-+0-9.eE]+)\s+([-+0-9.eE]+)" source)))]
    (cond
      (not= (count vertices) (* 3 (count normals))) {:stl/ok? false :stl/error :stl/facet-arity}
      (not-every? #(every? finite? %) (concat vertices normals)) {:stl/ok? false :stl/error :stl/non-finite}
      :else {:stl/ok? true :stl/format :ascii
             :stl/facets (mapv (fn [i] {:facet/normal (nth normals i) :facet/vertices (subvec vertices (* i 3) (+ (* i 3) 3)) :facet/attribute 0}) (range (count normals)))})))

(defn- bounds [points] {:min (mapv #(apply min %) (apply map vector points)) :max (mapv #(apply max %) (apply map vector points))})
(defn- sub [a b] (mapv - a b))
(defn- cross [[ax ay az] [bx by bz]] [(- (* ay bz) (* az by)) (- (* az bx) (* ax bz)) (- (* ax by) (* ay bx))])
(defn- norm [v] (#?(:clj Math/sqrt :cljs js/Math.sqrt) (reduce + (map #(* % %) v))))
(defn facet-area [{:facet/keys [vertices]}] (let [[a b c] vertices] (* 0.5 (norm (cross (sub b a) (sub c a))))))

(defn summary [{:stl/keys [ok? facets] :as model}]
  (if-not ok? model
    (let [points (vec (mapcat :facet/vertices facets))]
      (assoc model :stl/summary {:facet-count (count facets) :vertex-count (count points) :bounds (bounds points) :surface-area (reduce + 0.0 (map facet-area facets))}))))

(defn inspect [payload]
  (case (payload-format payload)
    :ascii (summary (parse-ascii payload))
    :binary {:stl/ok? false :stl/error :stl/binary-host-required :stl/message "Binary STL requires a byte-buffer adapter."}
    {:stl/ok? false :stl/error :stl/unsupported-payload}))
