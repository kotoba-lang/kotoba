(ns audio.runtime
  "Portable game-audio control plane.

  Owns deterministic bus gain/mute, ducking, cue selection, crossfade plans,
  listener/source projection and voice admission. Browser/native hosts execute
  the returned actions; this namespace never owns a device or clock.")

(def buses [:master :music :sfx :voice :ambient :ui])
(def bus-set (set buses))

(def default-duck-rules
  {:voice {:targets {:music 0.35 :ambient 0.5} :attack-ms 80 :release-ms 280}
   :ui-modal {:targets {:music 0.6 :sfx 0.7 :ambient 0.6} :attack-ms 60 :release-ms 180}})

(defn clamp-gain [gain]
  (when (number? gain) (max 0.0 (min 1.0 (double gain)))))

(defn runtime
  ([] (runtime {}))
  ([{:keys [master buses-config duck-rules max-voices]
     :or {master 1.0 buses-config {} duck-rules default-duck-rules max-voices 32}}]
   {:audio/version 1
    :audio/master (or (clamp-gain master) 1.0)
    :audio/buses (reduce (fn [m bus]
                           (assoc m bus
                                  (merge {:gain 1.0 :muted? false}
                                         (select-keys (get buses-config bus) [:gain :muted?]))))
                         {} buses)
    :audio/duck-rules duck-rules
    :audio/duck-active #{}
    :audio/scenes {}
    :audio/scene nil
    :audio/music nil
    :audio/transition nil
    :audio/listener {:position [0.0 0.0 0.0]
                     :forward [0.0 0.0 -1.0] :up [0.0 1.0 0.0]}
    :audio/sources {}
    :audio/max-voices max-voices}))

(defn valid-cue?
  [{:cue/keys [id uri bus loop? gain] :as cue}]
  (and id (string? uri) (seq uri) (contains? bus-set (or bus :music))
       (or (nil? loop?) (boolean? loop?))
       (or (nil? gain) (some? (clamp-gain gain)))
       cue))

(defn valid-scene?
  [{:scene/keys [id music ambient transition-ms] :as scene}]
  (and id
       (or (nil? music) (valid-cue? music))
       (every? valid-cue? (or ambient []))
       (or (nil? transition-ms) (and (integer? transition-ms) (not (neg? transition-ms))))
       scene))

(defn register-scene [state scene]
  (if (valid-scene? scene)
    [:ok (assoc-in state [:audio/scenes (:scene/id scene)] scene)]
    [:error :invalid-audio-scene state]))

(defn set-master [state gain]
  (if-some [gain (clamp-gain gain)]
    [:ok (assoc state :audio/master gain)]
    [:error :invalid-gain state]))

(defn set-bus-gain [state bus gain]
  (if (and (contains? bus-set bus) (some? (clamp-gain gain)))
    [:ok (assoc-in state [:audio/buses bus :gain] (clamp-gain gain))]
    [:error :invalid-bus-gain state]))

(defn set-bus-muted [state bus muted?]
  (if (and (contains? bus-set bus) (boolean? muted?))
    [:ok (assoc-in state [:audio/buses bus :muted?] muted?)]
    [:error :invalid-bus-mute state]))

(defn begin-duck [state reason]
  (if (contains? (:audio/duck-rules state) reason)
    [:ok (update state :audio/duck-active conj reason)]
    [:error :unknown-duck-reason state]))

(defn end-duck [state reason]
  [:ok (update state :audio/duck-active disj reason)])

(defn duck-gain [state bus]
  (reduce (fn [gain reason]
            (* gain (get-in state [:audio/duck-rules reason :targets bus] 1.0)))
          1.0 (:audio/duck-active state)))

(defn effective-gain
  ([state bus] (effective-gain state bus 1.0))
  ([state bus source-gain]
   (let [{:keys [gain muted?]} (get-in state [:audio/buses bus])]
     (if (or (not (contains? bus-set bus)) muted?)
       0.0
       (* (:audio/master state) gain (duck-gain state bus)
          (or (clamp-gain source-gain) 1.0))))))

(defn transition-scene
  "Select a registered scene. Returns a host action plan with explicit clock
   boundaries; hosts may implement equal-power ramps but may not invent timing."
  [state scene-id now]
  (let [scene (get-in state [:audio/scenes scene-id])]
    (cond
      (nil? scene) [:error :audio-scene-not-found state]
      (not (integer? now)) [:error :invalid-clock state]
      (= scene-id (:audio/scene state)) [:duplicate [] state]
      :else
      (let [from (:audio/music state)
            to (:scene/music scene)
            duration (or (:scene/transition-ms scene) 300)
            transition {:transition/from from :transition/to to
                        :transition/started-at now :transition/ends-at (+ now duration)}
            actions (cond-> []
                      from (conj {:audio/action :fade-out :cue from :duration-ms duration})
                      to (conj {:audio/action :fade-in :cue to :duration-ms duration})
                      true (into (map (fn [cue] {:audio/action :ensure-loop :cue cue})
                                      (:scene/ambient scene))))]
        [:ok actions (assoc state :audio/scene scene-id :audio/music to
                            :audio/transition transition)]))))

(defn advance
  [state now]
  (let [transition (:audio/transition state)]
    (if (and transition (>= now (:transition/ends-at transition)))
      [:ok [{:audio/action :transition-complete
             :cue (:transition/to transition)}]
       (assoc state :audio/transition nil)]
      [:waiting [] state])))

(defn set-listener [state listener]
  (if (and (= 3 (count (:position listener))) (= 3 (count (:forward listener)))
           (= 3 (count (:up listener))))
    [:ok (assoc state :audio/listener listener)]
    [:error :invalid-listener state]))

(defn upsert-source
  [state {:source/keys [id bus position gain max-distance priority] :as source}]
  (if (and id (contains? bus-set bus) (= 3 (count position))
           (some? (clamp-gain (or gain 1.0)))
           (number? max-distance) (pos? max-distance) (integer? priority))
    [:ok (assoc-in state [:audio/sources id] source)]
    [:error :invalid-audio-source state]))

(defn remove-source [state source-id]
  [:ok (update state :audio/sources dissoc source-id)])

(defn admitted-source-ids [state]
  (->> (:audio/sources state)
       (sort-by (fn [[id source]] [(- (:source/priority source)) (str id)]))
       (take (:audio/max-voices state))
       (mapv first)))
