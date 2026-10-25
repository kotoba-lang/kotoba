(ns importer.plan
  "One page, as a value, and the commit that ties the page to the cursor.

  The kernel does not parse anybody's JSON. Turning a Graph response into items
  is provider work and lives in the actor; what lives here is the shape that
  work must produce, and the single path from `we have a page` to `the cursor
  moved` -- so that path exists once rather than once per importer."
  (:require [importer.cursor :as cur]
            [importer.outcome :as out]
            [importer.receipt :as receipt]))

(defn plan
  "opts: {:stream :key :items :next-token :outcome :watermark :resync-required?}

  `:outcome` is required and is the page's own three-valued verdict: a page
  that could not be fetched is :unmeasured, not an empty :synced page."
  [{:keys [stream key items next-token outcome watermark resync-required? note]}]
  (cond-> {:importer.plan/stream stream
           :importer.plan/key key
           :importer.plan/items (vec items)
           :importer.plan/next-token next-token
           :importer.plan/outcome outcome}
    (some? watermark) (assoc :importer.plan/watermark watermark)
    resync-required? (assoc :importer.plan/resync-required? true)
    note (assoc :importer.plan/note note)))

(defn count-planned [p] (count (:importer.plan/items p)))
(defn last-page? [p] (nil? (:importer.plan/next-token p)))

(defn problems [p]
  (cond-> []
    (not (out/outcome? (:importer.plan/outcome p)))
    (conj {:importer/code :plan/no-outcome
           :importer/msg "plan has no three-valued :outcome"})

    (nil? (:importer.plan/stream p))
    (conj {:importer/code :plan/no-stream :importer/msg "plan names no stream"})

    ;; A page that reports items it did not fetch is the input side of the
    ;; same bug `cursor/advance` guards on the output side.
    (and (not= :synced (:importer.plan/outcome p))
         (seq (:importer.plan/items p)))
    (conj {:importer/code :plan/items-without-sync
           :importer/msg "plan carries items but did not report :synced"})))

(defn valid? [p] (empty? (problems p)))

(defn commit
  "Persist-then-move, as one function.

  `sink-report` is what `importer.ports/-persist!` returned -- the sink's own
  count, never the plan's. Returns

    {:importer/cursor  the next cursor (unchanged if the move was held)
     :importer/receipt evidence for this page
     :importer/outcome :synced | :failed | :unmeasured}

  A held move is :failed, not :synced. The page was read and not landed, and
  answering :synced there would be the whole bug in one keyword."
  [p c sink-report now]
  (let [ps (problems p)]
    (when (seq ps)
      (throw (ex-info "invalid plan" {:type :importer/invalid-plan :importer/problems ps}))))
  (let [planned (count-planned p)
        persisted (:importer.sink/persisted sink-report 0)
        rejected (:importer.sink/rejected sink-report [])
        move (cur/advance c {:outcome (:importer.plan/outcome p)
                             :next-token (:importer.plan/next-token p)
                             :planned planned
                             :persisted persisted
                             :watermark (:importer.plan/watermark p)
                             :at now})
        moved? (= :advanced (:importer.cursor/state move))
        c' (:importer.cursor/cursor move)
        outcome (cond
                  moved? (:importer.plan/outcome p)
                  (= :unmeasured (:importer.plan/outcome p)) :unmeasured
                  :else :failed)]
    {:importer/cursor c'
     :importer/outcome outcome
     :importer/receipt (receipt/receipt
                        {:cursor-in c :cursor-out c' :moved? moved?
                         :planned planned :persisted persisted
                         :rejected (count rejected)
                         :outcome outcome
                         :held-reason (when-not moved? (:importer.cursor/reason move))
                         :held-detail (when-not moved? (:importer.cursor/detail move))
                         :resync-required? (:importer.plan/resync-required? p)
                         :at now})}))
