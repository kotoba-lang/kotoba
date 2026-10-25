(ns kotoba.live.director
  "Director — EDN-declared reactions to show events.

  The choreography (poses, lighting, crowd) is data; so are the *reactions*
  a scene triggers. Rather than a host hard-coding \"confetti on the drop\",
  the scene author declares it in `:dance/triggers`, and the director
  resolves, per show event, the action maps a host (native or web) should
  apply. Action keys are free-form data (`:fx`, `:sound`, `:camera`, ...) so
  new reactions need no engine code, only EDN.

  ```edn
  :dance/triggers
  [{:on :drop      :fx :confetti :sound :coin :camera :punch}
   {:on :breakdown :fx :dim      :sound :whoosh}
   {:on :callout   :tag \"intro\" :camera :closeup}
   {:on :phrase    :vj-cut true}
   {:on :bar :every 8 :fx :pyro}]
  ```")

(def trigger-on-values
  #{:drop :breakdown :callout :custom :beat :bar :phrase :track})

(def ^:private control-keys #{:on :tag :every})

(defn- trigger-on-by-name [name]
  (let [k (keyword name)]
    (when (contains? trigger-on-values k) k)))

(defn parse-trigger
  "Parse one `:dance/triggers` entry map into a trigger, or `nil` if it has
  no valid `:on`."
  [m]
  (when-let [on (trigger-on-by-name (clojure.core/name (:on m)))]
    {:on on
     :tag (:tag m)
     :every (when-let [n (:every m)] (max 0 (long n)))
     ;; action keys are stored by their bare *string* name (not the keyword),
     ;; so `action` can be looked up with a plain string like `"fx"`.
     :actions (into {} (keep (fn [[k v]] (when-not (contains? control-keys k) [(clojure.core/name k) v]))) m)}))

(defn action
  "Look up an action's value as an identifier (keyword/string name), or
  `nil`. `key` is the action's bare string name (e.g. `\"fx\"`)."
  [trigger key]
  (let [v (get (:actions trigger) key)]
    (cond
      (keyword? v) (name v)
      (string? v) v
      :else nil)))

(defn from-root
  "Parse `:dance/triggers` from a scene root map. Missing -> empty director."
  [root]
  {:triggers (vec (keep parse-trigger (get root :dance/triggers [])))})

(defn- tag-ok? [trigger tag]
  (or (nil? (:tag trigger)) (= (:tag trigger) tag)))

(defn- every-ok? [trigger index]
  (let [n (:every trigger)]
    (if (and n (pos? n)) (zero? (mod index n)) true)))

(defn- matches? [trigger event]
  (case [(:on trigger) (:type event)]
    [:drop :cue] (and (= :drop (get-in event [:cue :kind])) (tag-ok? trigger (get-in event [:cue :tag])))
    [:breakdown :cue] (and (= :breakdown (get-in event [:cue :kind])) (tag-ok? trigger (get-in event [:cue :tag])))
    [:callout :cue] (and (= :callout (get-in event [:cue :kind])) (tag-ok? trigger (get-in event [:cue :tag])))
    [:custom :cue] (and (= :custom (get-in event [:cue :kind])) (tag-ok? trigger (get-in event [:cue :tag])))
    [:beat :beat] (and (= :beat (get-in event [:beat :type])) (every-ok? trigger (get-in event [:beat :beat-index])))
    [:bar :beat] (and (= :bar (get-in event [:beat :type])) (every-ok? trigger (get-in event [:beat :bar-index])))
    [:phrase :beat] (and (= :phrase (get-in event [:beat :type])) (every-ok? trigger (get-in event [:beat :phrase-index])))
    [:track :track-changed] true
    false))

(defn resolve-event
  "The triggers that fire for `event`, in author order. `event` is a show
  event map (see `kotoba.live.show`): `{:type :cue :cue {...}}`,
  `{:type :beat :beat {...}}`, `{:type :track-changed ...}`, etc."
  [director event]
  (filterv #(matches? % event) (:triggers director)))
