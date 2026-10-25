(ns kakeibo.core
  "The one entry point: statement rows in, ledger postings and a report out.

  Consumers require `kakeibo.core` and nothing else. The stage namespaces
  (`kakeibo.tx`, `kakeibo.dedup`, `kakeibo.category`, `kakeibo.ledger`,
  `kakeibo.rollup`) stay public for testing and for a caller that genuinely
  needs one stage, but a personal-finance app should not be assembling the
  pipeline itself — that is how two consumers end up de-duplicating
  differently and disagreeing about how much was spent.

      (ingest {:mapping  <institution mapping>
               :rows     [<statement row> ...]
               :rules    [<category rule> ...]
               :existing [<already-ledgered tx> ...]   ; optional
               :budget   {<category> <minor units>}})  ; optional

  Pure: no clock, no filesystem, no network, no model. Given the same inputs
  it returns the same result, which is what lets it run as a deterministic
  `tamaki exec` tick whose receipt means something."
  (:require [kakeibo.tx :as tx]
            [kakeibo.dedup :as dedup]
            [kakeibo.category :as category]
            [kakeibo.ledger :as ledger]
            [kakeibo.rollup :as rollup]))

(defn ingest
  "Run the full pipeline. Returns a map with, in pipeline order:

  | key                      | meaning                                        |
  |--------------------------|------------------------------------------------|
  | `:kakeibo/read`          | rows offered                                   |
  | `:kakeibo/rejected`      | rows that could not be read, with reasons      |
  | `:kakeibo/mapping-problems` | mapping refused outright                    |
  | `:kakeibo/suppressed`    | duplicate rows removed by overlap de-dup       |
  | `:kakeibo/txs`           | canonical, de-duplicated, categorized          |
  | `:kakeibo/new`           | of those, absent from `:existing`              |
  | `:kakeibo/postings`      | balanced double-entry postings for the new ones|
  | `:kakeibo/unpostable`    | transactions that could not be posted          |
  | `:kakeibo/category-coverage` | how much the rules explained               |
  | `:kakeibo/report`        | totals / per-period / per-category / coverage   |
  | `:kakeibo/budget`        | budget comparison, when a period is given      |

  Nothing is dropped silently at any stage: every count above has a
  corresponding list, so `read` can always be reconciled against
  `txs + rejected + suppressed`."
  [{:keys [mapping rows rules existing budget budget-period]}]
  (let [normalized (tx/normalize-rows mapping (or rows []))
        merged     (dedup/merge-batches [(or existing []) (:kakeibo/txs normalized)])
        categorized (category/categorize (or rules []) (:kakeibo/txs merged))
        known-ids  (into #{} (map :tx/id) (dedup/assign-ids (or existing [])))
        fresh      (vec (remove #(contains? known-ids (:tx/id %)) categorized))
        projected  (ledger/project fresh)]
    (cond-> {:kakeibo/read             (:kakeibo/read normalized)
             :kakeibo/rejected         (:kakeibo/rejected normalized)
             :kakeibo/mapping-problems (:kakeibo/mapping-problems normalized)
             :kakeibo/suppressed       (:kakeibo/suppressed merged)
             :kakeibo/txs              categorized
             :kakeibo/new              fresh
             :kakeibo/postings         (:kakeibo/postings projected)
             :kakeibo/unpostable       (:kakeibo/rejected projected)
             :kakeibo/category-coverage (category/coverage categorized)
             :kakeibo/report           (rollup/report categorized)}
      (and budget budget-period)
      (assoc :kakeibo/budget (rollup/budget-report budget categorized budget-period)))))

(defn summary
  "One-screen counts from an `ingest` result, for an operator or a tick log.

  Deliberately includes the failure counts. A summary that shows only what
  succeeded is how a half-broken ingest survives for weeks."
  [result]
  {:summary/read        (:kakeibo/read result)
   :summary/rejected    (count (:kakeibo/rejected result))
   :summary/suppressed  (:kakeibo/suppressed result)
   :summary/txs         (count (:kakeibo/txs result))
   :summary/new         (count (:kakeibo/new result))
   :summary/postings    (count (:kakeibo/postings result))
   :summary/unpostable  (count (:kakeibo/unpostable result))
   :summary/uncategorized (get-in result [:kakeibo/category-coverage :category/uncategorized])
   :summary/mapping-problems (vec (:kakeibo/mapping-problems result))})

(defn clean?
  "True when an ingest produced no rejections, no unpostable transactions and
  no mapping problems. A tick should treat false as a failure exit rather than
  reporting success with a footnote."
  [result]
  (and (empty? (:kakeibo/mapping-problems result))
       (empty? (:kakeibo/rejected result))
       (empty? (:kakeibo/unpostable result))))
