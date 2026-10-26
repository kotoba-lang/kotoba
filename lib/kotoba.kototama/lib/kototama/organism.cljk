(ns kototama.organism
  "kototama · organism — the artificial-organism heartbeat, distilled from ibuki
  autorun + organism.cljc. An organism is a long-lived actor whose entire inner
  state lives on its append-only kotoba log; each `beat` is the deterministic
  cycle

    replay → perceive → feel (fold mood/metabolism) → decide → narrate
           → act (gated, member-leashed publish) → persist (append tx)

  Beats are idempotent-by-content: an unchanged decision on an unchanged head
  appends nothing, so crash-resume is byte-identical and the loop is safe to
  re-run. Publication is autonomous-by-default (種をまく / etzhayyim
  ADR-2606281500) but bounded by the seed: valid member leash + §2 content scan
  + append-only public log. PUBLICATION ≠ ACTUATION — high-stakes actuation
  stays behind `kototama.gates/may-actuate?`.

  Hooks (all pure, caller-supplied):
    :perceive (fn [ctx] perception)            default {}
    :decide   (fn [ctx] {:events [..] :post-text str|nil :act? bool})
    :narrate  (fn [ctx] text)                  optional; fills :post-text"
  (:require [kototama.kotoba :as kt]
            [kototama.life :as life]
            [kototama.leash :as leash]
            [kototama.gates :as gates]
            [kototama.emit :as emit]))

(defn organism
  "Construct an organism runtime. opts:
    :id :baseline(mood int) :leash :target(emit target kw)
    :journal (seed log vec) :perceive :decide :narrate"
  [{:keys [id baseline leash target journal perceive decide narrate]
    :or {baseline 0 target :app-aozora perceive (constantly {})
         decide (constantly {}) }}]
  {:id id :baseline baseline :leash leash :target target
   :conn (kt/connect {:log journal})
   :perceive perceive :decide decide :narrate narrate})

(defn beat
  "Run one heartbeat. opts: :now (unix-s int) :created-at (ISO str). Returns
  {:beat :mood :metabolism :perception :post-text :envelope :head-cid :appended?}."
  [{:keys [conn baseline leash target perceive decide narrate id]} & [{:keys [now created-at] :or {now 0}}]]
  (let [n          (count (kt/log conn))
        mood       (life/fold-mood conn baseline)
        metab      (life/metabolism conn)
        ctx        {:beat n :mood mood :metabolism metab :conn conn
                    :now now :created-at created-at}
        perception (perceive ctx)
        decision   (decide (assoc ctx :perception perception))
        post-text  (or (:post-text decision)
                       (when (and (:act? decision) narrate)
                         (narrate (assoc ctx :perception perception))))
        ;; gate publication: leashed + drafting allowed + content clears §2 scan
        may?       (and (:act? decision) post-text
                        (gates/leashed? {:leash leash})
                        (leash/valid? leash now)              ; expiry/scope, not just presence
                        (:ok? (gates/scan post-text)))
        record     (when may? (emit/post-record {:text post-text :actor-did id
                                                 :mood mood :created-at created-at}))
        env        (when record (emit/envelope record leash {:target target :now now}))
        ;; datoms: the felt events + (if published) the post intent, content-addressed
        evts       (mapv (fn [e] [:db/add (str id "-beat-" n) :organism/event e])
                         (:events decision []))
        post-datom (when env [[:db/add (str id "-post-" n) :organism/post
                               {:text post-text :target target :status :dry-run
                                :writeAuthor (:writeAuthor env)}]])
        datoms     (vec (concat evts post-datom))
        {:keys [head-cid appended?]} (if (seq datoms)
                                       (kt/transact conn datoms {:as-of now})
                                       {:head-cid (kt/head-cid conn) :appended? false})]
    {:beat n :mood mood :metabolism metab :perception perception
     :post-text post-text :envelope env :head-cid head-cid :appended? appended?}))

(defn autorun
  "Run `beats` heartbeats (the bb-runnable loop; production scheduling is a
  LaunchAgent). Returns the vector of beat results. now/created-at are passed
  through (no wall-clock in the lib)."
  [org {:keys [beats now created-at] :or {beats 1 now 0}}]
  (mapv (fn [_] (beat org {:now now :created-at created-at})) (range beats)))
