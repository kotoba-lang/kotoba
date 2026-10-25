(ns game.liveops
  "Portable, deterministic LiveOps contracts shared by game hosts.

  Persistence, authentication and wall clocks belong to the host. This layer
  validates revisions and evaluates remote config, targeting, rollouts and
  scheduled campaigns identically in CLJ and CLJS.")

(def contract-version 1)
(def max-config-bytes 65536)
(def operators #{:eq :not-eq :in :not-in :gte :lte})

(defn- bounded-string? [value n]
  (and (string? value) (seq value) (<= (count value) n)))

(defn valid-window? [{:keys [starts-at ends-at]}]
  (and (integer? starts-at) (integer? ends-at) (< starts-at ends-at)))

(defn active-window? [{:keys [starts-at ends-at]} now]
  (and (integer? now) (<= starts-at now) (< now ends-at)))

(defn valid-condition? [{:keys [attribute operator value]}]
  (and (keyword? attribute) (contains? operators operator)
       (if (contains? #{:in :not-in} operator) (coll? value) (some? value))))

(defn condition-matches? [attributes {:keys [attribute operator value]}]
  (let [actual (get attributes attribute)]
    (case operator
      :eq (= actual value)
      :not-eq (not= actual value)
      :in (boolean (some #(= actual %) value))
      :not-in (not (some #(= actual %) value))
      :gte (and (number? actual) (number? value) (>= actual value))
      :lte (and (number? actual) (number? value) (<= actual value))
      false)))

(defn segment-matches? [{:keys [all any none]} attributes]
  (and (every? #(condition-matches? attributes %) (or all []))
       (or (empty? any) (some #(condition-matches? attributes %) any))
       (not-any? #(condition-matches? attributes %) (or none []))))

(defn stable-bucket
  "Stable 0..9999 allocation. Salt includes the flag and revision so operators
  can intentionally reshuffle a rollout by publishing a new revision."
  [salt subject]
  (let [s (str salt "\u0000" subject)
        hash (reduce (fn [acc ch]
                       (mod (+ (* acc 31) #?(:clj (int ch)
                                             :cljs (.charCodeAt ch 0)))
                            2147483647))
                     7 s)]
    (mod hash 10000)))

(defn valid-variant? [{:keys [id weight value]}]
  (and (bounded-string? id 64) (integer? weight) (<= 0 weight 10000)
       (some? value)))

(defn valid-flag? [{:keys [key revision enabled default rollout variants
                            segment starts-at ends-at]}]
  (and (bounded-string? key 128) (integer? revision) (pos? revision)
       (boolean? enabled)
       (or (nil? rollout) (and (integer? rollout) (<= 0 rollout 10000)))
       (or (nil? segment)
           (every? valid-condition? (mapcat #(get segment % []) [:all :any :none])))
       (or (and (nil? starts-at) (nil? ends-at))
           (valid-window? {:starts-at starts-at :ends-at ends-at}))
       (or (nil? variants)
           (and (seq variants) (every? valid-variant? variants)
                (= 10000 (reduce + (map :weight variants)))))
       (some? default)))

(defn- choose-variant [variants bucket]
  (loop [remaining variants edge 0]
    (when-let [{:keys [weight value id]} (first remaining)]
      (let [next-edge (+ edge weight)]
        (if (< bucket next-edge)
          {:value value :variant id}
          (recur (next remaining) next-edge))))))

(defn evaluate-flag
  "Evaluate one flag. Overrides are host-authorized, time-bounded records keyed
  by subject. The result includes a reason and revision for telemetry/audits."
  [flag {:keys [subject attributes now override]}]
  (cond
    (not (valid-flag? flag)) {:value (:default flag) :reason :invalid :revision (:revision flag)}
    (and override (= subject (:subject override))
         (or (nil? (:expires-at override)) (> (:expires-at override) now)))
    {:value (:value override) :reason :override :revision (:revision flag)}
    (not (:enabled flag)) {:value (:default flag) :reason :disabled :revision (:revision flag)}
    (and (:starts-at flag) (not (active-window? flag now)))
    {:value (:default flag) :reason :outside-window :revision (:revision flag)}
    (and (:segment flag) (not (segment-matches? (:segment flag) attributes)))
    {:value (:default flag) :reason :segment-miss :revision (:revision flag)}
    :else
    (let [bucket (stable-bucket (str (:key flag) ":" (:revision flag)) subject)]
      (if (and (:rollout flag) (>= bucket (:rollout flag)))
        {:value (:default flag) :reason :rollout-miss :bucket bucket :revision (:revision flag)}
        (if-let [chosen (and (:variants flag) (choose-variant (:variants flag) bucket))]
          (assoc chosen :reason :variant :bucket bucket :revision (:revision flag))
          {:value (:value flag) :reason :enabled :bucket bucket :revision (:revision flag)})))))

(defn valid-campaign? [{:keys [id revision starts-at ends-at priority grants]}]
  (and (bounded-string? id 128) (integer? revision) (pos? revision)
       (valid-window? {:starts-at starts-at :ends-at ends-at})
       (integer? priority) (<= -1000 priority 1000)
       (vector? grants) (<= (count grants) 100)))

(defn active-campaigns [campaigns attributes now]
  (->> campaigns
       (filter valid-campaign?)
       (filter #(active-window? % now))
       (filter #(or (nil? (:segment %)) (segment-matches? (:segment %) attributes)))
       (sort-by (juxt (comp - :priority) :starts-at :id))
       vec))

(defn publish-revision
  "Monotonic, optimistic publication. `expected-revision` prevents operators
  from silently overwriting a concurrent edit."
  [current candidate expected-revision]
  (let [current-revision (or (:revision current) 0)]
    (cond
      (not= current-revision expected-revision) [:error :revision-conflict current]
      (not= (inc current-revision) (:revision candidate)) [:error :non-monotonic-revision current]
      :else [:ok candidate])))
