(ns vehicle.jbeam
  "JBeam-subset loader.
   Restored from kami-vehicle (kotoba-lang/kami-engine, deleted PR #82),
   ADR-2607010930.

   The original Rust module parses a JSON dialect via `serde_json` derive
   macros. There is no portable serde-macro equivalent in CLJC, so this
   port implements the equivalent parsing by hand against a Clojure map /
   EDN-compatible structure: callers pass an already-parsed Clojure map
   (e.g. the result of `clojure.data.json/read-str :key-fn keyword` or a
   hand-authored EDN literal) rather than a raw JSON string, keeping this
   namespace free of any JSON-library dependency (zero-dependency
   requirement per ADR-2607010930). `load-edn` performs exactly the
   validation, defaulting, and node/beam/wheel construction that
   `load_str` did in Rust."
  (:require [vehicle.vec3 :as v3]
            [vehicle.beam :as beam]
            [vehicle.node :as node]
            [vehicle.vehicle :as veh]
            [vehicle.wheel :as wheel]))

;; ---- errors ----
;; Represented as `{:error :unknown-node|:unknown-group|:unknown-beam-type|
;;                          :unknown-tire|:malformed, :detail ...}`
;; `load-edn` returns either `[:ok vehicle]` or `[:error error-map]`.

(defn- parse-group [s]
  (case s
    "body" [:ok :body]
    "wheel_hub" [:ok :wheel-hub]
    "hub" [:ok :wheel-hub]
    "wheel_tire" [:ok :wheel-tire]
    "tire" [:ok :wheel-tire]
    "cargo" [:ok :cargo]
    "anchor" [:ok :anchor]
    [:error {:error :unknown-group :detail s}]))

(defn- parse-beam-type [s min-ratio max-ratio hydro-factor]
  (case s
    "normal" [:ok beam/beam-type-normal]
    "support" [:ok beam/beam-type-support]
    "bounded" [:ok (beam/beam-type-bounded (or min-ratio 0.85) (or max-ratio 1.15))]
    "hydro" [:ok (beam/beam-type-hydro (or hydro-factor 0.10) 0.0)]
    "pressured" [:ok (beam/beam-type-pressured 0.05 2.4)]
    [:error {:error :unknown-beam-type :detail s}]))

(defn- parse-tire [s]
  (case s
    "road_dry" [:ok (wheel/pacejka-road-dry)]
    "road_wet" [:ok (wheel/pacejka-road-wet)]
    [:error {:error :unknown-tire :detail s}]))

(defn load-edn
  "Load a Vehicle from an already-parsed JBeam-subset EDN/map structure:
   `{:name \"sedan\"
     :nodes [{:id \"fl_lower\" :pos [x y z] :mass m :group \"body\" ...} ...]
     :beams [{:n1 \"a\" :n2 \"b\" :spring s :damping d :type \"normal\" ...} ...]
     :wheels [{:axle [\"a\" \"b\"] :radius r :width w :tire \"road_dry\" ...} ...]}`

   Returns `[:ok vehicle]` or `[:error error-map]`, mirroring Rust's
   `Result<Vehicle, JBeamError>`."
  [file]
  (let [nodes (:nodes file [])
        beams (:beams file [])
        wheels (:wheels file [])
        v0 (veh/new-vehicle (:name file))]
    (loop [i 0 id-map {} v v0]
      (if (>= i (count nodes))
        ;; -- nodes done, process beams --
        (loop [bi 0 v v]
          (if (>= bi (count beams))
            ;; -- beams done, process wheels --
            (loop [wi 0 v v]
              (if (>= wi (count wheels))
                [:ok v]
                (let [w (nth wheels wi)
                      [ax1 ax2] (:axle w)]
                  (if-let [a1 (get id-map ax1)]
                    (if-let [a2 (get id-map ax2)]
                      (let [tire-preset (:tire w "road_dry")]
                        (let [[status tire] (parse-tire tire-preset)]
                          (if (= status :error)
                            [:error tire]
                            (let [wh (-> (wheel/new-wheel wi a1 a2 (:radius w) (:width w))
                                         (assoc :tire tire)
                                         (cond-> (:pressure w) (#(assoc % :pressure (:pressure w) :reference-pressure (:pressure w))))
                                         (cond-> (:max-steer-deg w) (assoc :max-steer-angle (Math/toRadians (double (:max-steer-deg w)))))
                                         (update :hub-nodes conj a1)
                                         (update :hub-nodes conj a2))
                                  tire-node-ids (:tire-nodes w [])
                                  missing (first (remove #(contains? id-map %) tire-node-ids))]
                              (if missing
                                [:error {:error :unknown-node :detail missing}]
                                (let [resolved (mapv id-map tire-node-ids)
                                      wh (assoc wh :tire-nodes resolved)
                                      wh (if (>= (count resolved) 8) (assoc wh :contact-mode :tire-ring) wh)]
                                  (recur (inc wi) (veh/add-wheel v wh))))))))
                      [:error {:error :unknown-node :detail ax2}])
                    [:error {:error :unknown-node :detail ax1}]))))
            (let [b (nth beams bi)
                  n1id (:n1 b) n2id (:n2 b)]
              (if-let [n1 (get id-map n1id)]
                (if-let [n2 (get id-map n2id)]
                  (let [p1 (:position (nth (:nodes v) n1))
                        p2 (:position (nth (:nodes v) n2))
                        rest (max (v3/length (v3/sub p2 p1)) 1e-3)
                        [status bt] (parse-beam-type (:type b "normal") (:min-ratio b) (:max-ratio b) (:hydro-factor b))]
                    (if (= status :error)
                      [:error bt]
                      (let [bm (-> (beam/new-beam bi n1 n2 rest (:spring b) (:damping b))
                                   (beam/with-type bt)
                                   (beam/with-deform {:deform-limit (:deform-limit b 0.10)
                                                       :break-limit (:break-limit b 0.45)
                                                       :max-plastic-strain 0.40})
                                   (assoc :break-group (:break-group b)))]
                        (recur (inc bi) (veh/add-beam v bm)))))
                  [:error {:error :unknown-node :detail n2id}])
                [:error {:error :unknown-node :detail n1id}]))))
        ;; -- process one node --
        (let [n (nth nodes i)
              [status group] (parse-group (:group n "body"))]
          (if (= status :error)
            [:error group]
            (let [nid i
                  pos (apply v3/v3 (:pos n))
                  nd (cond-> (node/with-group (node/new-node nid pos (:mass n)) group)
                       (:friction n) (assoc :friction (:friction n))
                       (:drag n) (assoc :drag (:drag n)))
                  nd (if (= group :anchor) (node/anchor nid pos) nd)]
              (recur (inc i) (assoc id-map (:id n) nid) (veh/add-node v nd)))))))))
