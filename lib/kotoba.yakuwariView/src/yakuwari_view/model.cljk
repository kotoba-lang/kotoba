(ns yakuwari-view.model
  "Roles + their live runs -> one display model, for any surface.

  Pure and portable: `runs` and `now-ms` arrive from the caller, nothing is
  fetched and nothing is rendered. The same projection therefore feeds a
  Cloudflare-hosted cockpit and a JVM local-first app without two copies
  drifting apart — which is the whole reason this namespace is separate from
  either of them.

  It owns no domain truth. Validation is `yakuwari.spec`, the HIL vocabulary
  is `yakuwari.policy`, and capacity arithmetic is `yakuwari.reconcile`. What
  this namespace adds is only the shaping and the aggregation those three do
  not do: grouping roles under the thing they serve, deriving a health label,
  and totalling. If a number here disagrees with `reconcile/plan`, this
  namespace is wrong.

  ## An invalid role is displayed as invalid, never dropped

  `reconcile/plan` calls `spec/validate!`, which throws. A projection that
  let that propagate would fail the whole page for one malformed file; one
  that caught it and skipped the role would render a fleet that looks
  complete and silently lacks a role. Both are worse than a role card that
  says what is wrong with it, so every role appears, and `:fleet/problems`
  carries the details. This is the same reasoning as the superproject query
  plane's `warn-skipped!`: a corpus that hides what it could not read reads
  as a corpus that had nothing to hide."
  (:require [yakuwari.spec :as spec]
            [yakuwari.policy :as policy]
            [yakuwari.reconcile :as reconcile]))

;; ---------------------------------------------------------------------------
;; Health
;; ---------------------------------------------------------------------------

(def health-precedence
  "Most to least urgent. A role can satisfy several of these at once, and the
  label shown must be the one an operator needs to act on first — so this is
  an ordered list rather than a set of independent predicates."
  [:invalid :stalled :starved :saturated :idle :healthy])

(defn health
  "One label for how a role is doing, from its plan.

  `:stalled` outranks `:starved` because they look identical from the outside
  — nothing is running — but have opposite fixes. Stalled work is waiting on
  a human and needs an approval; starved work is waiting on nothing at all
  and needs a dispatcher. Collapsing them into one 'not running' state would
  hide which."
  [{:keys [valid? desired running queued blocked at-max?]}]
  (cond
    (not valid?) :invalid
    (and (pos? blocked) (zero? running)) :stalled
    (and (pos? desired) (zero? running) (zero? queued) (zero? blocked)) :starved
    at-max? :saturated
    (and (zero? desired) (zero? running) (zero? queued) (zero? blocked)) :idle
    :else :healthy))

;; ---------------------------------------------------------------------------
;; One role
;; ---------------------------------------------------------------------------

(defn- capabilities-needing-human
  "Which capabilities this role could not act on alone — computed from the
  policy, so it is what the role *is*, independent of whether anything is
  waiting right now.

  Distinct from the `:blocked` run count, which is what is waiting *now*.
  Reporting only the latter would make a role with sweeping approval
  requirements look identical to one with none whenever its queue is empty."
  [effective]
  (->> effective
       (filter (fn [[cap _]] (policy/needs-human? effective cap)))
       (map (fn [[cap d]] {:capability cap :decision d}))
       (sort-by (comp str :capability))
       vec))

(defn project-role
  "One role -> one card. `runs` may be the whole fleet's runs; `reconcile`
  filters to this role's own by `:agent.run/yakuwari`."
  [role runs now-ms]
  (let [{:keys [ok? problems]} (spec/validate role)
        scale (merge spec/default-scale (:yakuwari/scale role))
        effective (spec/effective-policy role)
        plan (when ok?
               (try (reconcile/plan role runs now-ms)
                    (catch #?(:clj Exception :cljs :default) _ nil)))
        ;; An invalid role still shows its live runs. The spec being
        ;; unreviewable does not make the executions it already spawned
        ;; invisible — those are the ones an operator most needs to see.
        own (reconcile/runs-for role runs)
        active (filterv #(contains? reconcile/active-statuses (:agent.run/status %)) own)
        running (or (:running plan)
                    (count (filterv #(contains? #{:leased :running :checkpointed}
                                                (:agent.run/status %)) active)))
        queued (or (:queued plan)
                   (count (filterv #(= :queued (:agent.run/status %)) active)))
        blocked (or (:blocked plan)
                    (count (filterv #(= :held (:agent.run/status %)) active)))
        desired (or (:desired plan) (:desired scale))]
    {:role/id (:yakuwari/id role)
     :role/objective (:yakuwari/objective role)
     :role/project (:yakuwari/project role)
     :role/scale scale
     :role/runners (vec (:yakuwari/runners role))
     :role/desired desired
     :role/running running
     :role/queued queued
     :role/blocked blocked
     :role/spawn (:spawn plan)
     :role/reap (vec (:reap plan))
     ;; Declared by the role, not inferred: whether a role corresponds
     ;; outward is a decision with a mailbox and a did:web attached to it,
     ;; not something to guess from its name.
     :role/outward? (boolean (:yakuwari/outward? role))
     :role/identity (:yakuwari/identity role)
     :role/needs-human (capabilities-needing-human effective)
     :role/valid? ok?
     :role/problems (vec problems)
     :role/health (health {:valid? ok? :desired desired :running running
                           :queued queued :blocked blocked
                           :at-max? (and (pos? (:max scale))
                                         (>= running (:max scale)))})}))

;; ---------------------------------------------------------------------------
;; Totals
;; ---------------------------------------------------------------------------

(defn- totals
  "Summed from the cards themselves, so a total can never disagree with the
  rows under it."
  [cards]
  {:roles (count cards)
   :running (reduce + 0 (map :role/running cards))
   :queued (reduce + 0 (map :role/queued cards))
   :blocked (reduce + 0 (map :role/blocked cards))
   :outward (count (filter :role/outward? cards))
   :invalid (count (remove :role/valid? cards))
   :by-health (frequencies (map :role/health cards))})

;; ---------------------------------------------------------------------------
;; The fleet
;; ---------------------------------------------------------------------------

(defn project
  "Roles + runs -> the display model both surfaces render.

  Options:
    :roles      yakuwari spec maps (plain authored maps; no :db/id)
    :runs       agent.run maps, any subset of the fleet's
    :groups     the things roles serve, in display order
    :group-key  key on a role naming its group (default :yakuwari/group)
    :group-id   key on a group naming itself (default :group/id)
    :now-ms     caller's clock; nil disables staleness reaping

  `:group-key` rather than `:group-by` on purpose — the latter would shadow
  `clojure.core/group-by` inside this very function.

  Groups are supplied rather than inferred from the roles so that a group
  with zero roles still appears. A business whose roles were all deleted is
  a fact worth showing; inferring groups would erase it."
  [{:keys [roles runs groups group-key group-id now-ms]}]
  (let [gkey (or group-key :yakuwari/group)
        gid (or group-id :group/id)
        runs (vec runs)
        cards (mapv #(project-role % runs now-ms) roles)
        card-of (zipmap (map :yakuwari/id roles) cards)
        by-group (group-by #(get % gkey) roles)
        grouped (mapv (fn [g]
                        (let [gv (get g gid)
                              members (mapv #(get card-of (:yakuwari/id %))
                                            (get by-group gv []))]
                          (assoc g
                                 :group/roles members
                                 :group/totals (totals members))))
                      groups)
        ;; Roles whose group is not in :groups. Surfaced rather than dropped:
        ;; a role pointing at a group nobody declared is a typo that would
        ;; otherwise make the role silently vanish from every surface.
        declared (set (map #(get % gid) groups))
        orphans (filterv #(not (contains? declared (get % gkey))) roles)]
    {:fleet/groups grouped
     :fleet/totals (totals cards)
     :fleet/orphan-roles (mapv (fn [r] {:role/id (:yakuwari/id r)
                                        :role/group (get r gkey)}) orphans)
     :fleet/problems (vec (for [c cards
                                p (:role/problems c)]
                            (assoc p :role/id (:role/id c))))}))

;; ---------------------------------------------------------------------------
;; Queries a surface asks repeatedly
;; ---------------------------------------------------------------------------

(defn hil-queue
  "Every run currently held for a human, newest first, flattened across
  groups — the local workspace app's primary view, where the operator's own
  approvals live and group boundaries matter less than recency."
  [projection runs]
  (let [held (filterv #(= :held (:agent.run/status %)) runs)
        role-of (into {} (for [g (:fleet/groups projection)
                               r (:group/roles g)]
                           [(:role/id r) (assoc r :role/group (:group/id g))]))]
    (->> held
         (map (fn [run]
                (let [r (get role-of (:agent.run/yakuwari run))]
                  {:run/id (:agent.run/id run)
                   :run/goal (:agent.run/goal run)
                   :run/updated-at (:agent.run/updated-at run)
                   :role/id (:agent.run/yakuwari run)
                   :role/group (:role/group r)
                   :role/objective (:role/objective r)})))
         (sort-by #(or (:run/updated-at %) 0) #(compare %2 %1))
         vec)))

(defn needs-attention
  "Roles an operator should look at, worst first. `:healthy`, `:idle` and
  `:saturated` are deliberately excluded — a cockpit that lists everything
  lists nothing."
  [projection]
  (let [rank (zipmap health-precedence (range))]
    (->> (for [g (:fleet/groups projection)
               r (:group/roles g)
               :when (contains? #{:invalid :stalled :starved} (:role/health r))]
           (assoc r :role/group (:group/id g)))
         (sort-by #(get rank (:role/health %) 99))
         vec)))
