(ns kotoba.lang.kami-nv-compat.e7m-shugyo.managers
  "e7m-shugyo — clean-room Isaac Lab manager framework (RL env managers).
  Portable .cljc port of src/e7m-shugyo/managers.ts. Wave 34.

  The canonical KAMI implementation behind nv-compat/isaaclab-envs. NVIDIA
  Isaac Lab drives manager-based RL environments from declarative term
  groups; this module reproduces the documented manager API
  (isaaclab.managers.{Observation,Reward,Termination,Event}Manager) so
  Isaac Lab task configs port to KAMI via import-path-only changes.

  Each manager is generic over the env value; terms are plain 2-arity
  functions `(fn [env params] ...)`, so the same managers drive any KAMI
  env (the cartpole env ships in cartpole.cljc). `env` is expected to be
  an atom (mutable per-step state) — reading terms deref it, event terms
  swap! it — matching the TS source's mutable-object env semantics.

  RewardManager and EventManager carry per-instance mutable bookkeeping
  (episode sums, interval-fire timestamps) and are atoms; ObsGroup /
  ObservationManager / TerminationManager are pure data + functions.

  Clean-room: from-spec manager semantics. No Isaac Lab source/binaries.
  ADR-2605261800 SD6 / D10.4 e7m-shugyo."
  )

;; Term = {:func (fn [env params] ...) ...}. func always takes 2 args
;; (env, params) — params may be nil when a term doesn't use it.

;; ── observation manager ──────────────────────────────────────────────────

(defn make-obs-group [terms] {:kind :obs-group :terms terms})

(defn obs-group-evaluate
  [group env]
  (vec (mapcat (fn [[_ term]]
                 (let [v ((:func term) env (:params term))
                       scale (or (:scale term) 1)]
                   (if (sequential? v) (map #(* % scale) v) [(* v scale)])))
               (:terms group))))

(defn make-observation-manager
  ([] (make-observation-manager {}))
  ([groups] {:kind :observation-manager :groups (or groups {})}))

(defn obs-manager-compute
  [mgr env]
  (into {} (map (fn [[name group]] [name (obs-group-evaluate group env)]) (:groups mgr))))

(defn obs-manager-group-names [mgr] (vec (keys (:groups mgr))))

;; ── reward manager ───────────────────────────────────────────────────────

(defn make-rew-group [terms] {:kind :rew-group :terms terms})

(defn rew-group-evaluate
  [group env]
  (reduce + 0.0 (map (fn [[_ term]] (* (:weight term) ((:func term) env (:params term)))) (:terms group))))

(defn rew-group-evaluate-breakdown
  [group env]
  (into {} (map (fn [[name term]] [name (* (:weight term) ((:func term) env (:params term)))]) (:terms group))))

(defn make-reward-manager
  "A stateful reward manager (an atom): tracks the episode's cumulative
  reward + per-term breakdown + step count."
  [group]
  (atom {:kind :reward-manager :group group :episode-sum 0.0 :episode-breakdown {} :step-count 0}))

(defn reward-manager-compute!
  [mgr env]
  (let [group (:group @mgr)
        r (rew-group-evaluate group env)
        breakdown (rew-group-evaluate-breakdown group env)]
    (swap! mgr (fn [m] (-> m
                          (update :episode-sum + r)
                          (update :step-count inc)
                          (update :episode-breakdown #(merge-with + % breakdown)))))
    r))

(defn reward-manager-get-breakdown
  [mgr env]
  (rew-group-evaluate-breakdown (:group @mgr) env))

(defn reward-manager-log-episode-reward
  [mgr]
  (merge {:total (:episode-sum @mgr) :steps (:step-count @mgr)} (:episode-breakdown @mgr)))

(defn reward-manager-reset-episode-log!
  [mgr]
  (swap! mgr assoc :episode-sum 0.0 :step-count 0 :episode-breakdown {}))

;; ── termination manager ──────────────────────────────────────────────────

(defn make-termination-manager
  ([] (make-termination-manager {}))
  ([terms] {:kind :termination-manager :terms terms}))

(defn termination-manager-compute
  "Returns {:terminated :truncated :info}. A term with :time-out true marks
  truncation (e.g. a time-out) rather than a hard termination."
  [mgr env]
  (reduce (fn [acc [name term]]
            (let [v (boolean ((:func term) env (:params term)))]
              (cond-> (assoc-in acc [:info name] v)
                v (update (if (:time-out term) :truncated :terminated) (constantly true)))))
          {:terminated false :truncated false :info {}}
          (:terms mgr)))

;; ── event manager ────────────────────────────────────────────────────────
;;
;; EventMode = :startup | :reset | :interval

(defn make-event-manager
  "A stateful event manager (an atom): tracks the last-fired sim-time per
  interval-mode term."
  ([] (make-event-manager {}))
  ([terms] (atom {:kind :event-manager :terms terms :last-fired {}})))

(defn event-manager-apply!
  "Apply all terms matching `mode`. For :interval terms, sim-time gates
  firing by :interval-s."
  ([mgr env mode] (event-manager-apply! mgr env mode 0))
  ([mgr env mode sim-time]
   (doseq [[name term] (:terms @mgr)]
     (when (= (:mode term) mode)
       (if (= mode :interval)
         (let [last (get (:last-fired @mgr) name ##-Inf)]
           (when (>= (- sim-time last) (or (:interval-s term) 0))
             (swap! mgr assoc-in [:last-fired name] sim-time)
             ((:func term) env (:params term))))
         ((:func term) env (:params term)))))))

(defn event-manager-reset-intervals!
  [mgr]
  (swap! mgr assoc :last-fired {}))
