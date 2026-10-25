(ns arrangement.read-scaling-bench
  "How does READ cost scale with the number of partitions?

  The write benchmark answered `many writers stop contending`. It said nothing
  about what the reader then pays, and that is the number that decides whether
  a partitioned root is a real design or a trade that moves the cost somewhere
  it was not measured.

  Total facts are held CONSTANT while the partition count varies, so any
  change is attributable to partitioning alone and not to having more data.

  Three read strategies:

  - `:eager-merge`   what `arrangement.partitioned/restore-all` does today:
                     hydrate every partition, merge, then answer. O(N) in
                     total facts AND O(k) in partition hydrations.
  - `:single`        the same facts in ONE snapshot (what a single-lane
                     writer produces). The floor.
  - `:compacted`     partitions folded into one snapshot ONCE, then queried
                     many times. This is what background compaction buys, and
                     the point is the amortization: the fold is paid per
                     compaction, the query is paid per query.

  Reported: fold/hydrate cost, and the per-query cost after it. A design that
  is fast to write and slow to read has not solved anything; this shows which
  one this is."
  (:require [arrangement.core :as arr]
            [arrangement.partitioned :as part]
            [arrangement.core-test :refer [test-blind-fn test-encrypt-fn test-decrypt-fn]]))

(defn- mem-store []
  (let [store (atom {})
        reads (atom 0)]
    {:put! (fn [cid bytes] (swap! store assoc cid bytes))
     :get-fn (fn [cid] (swap! reads inc) (get @store cid))
     :reads reads}))

(defn- commit! [put! db prev]
  (arr/commit! put! db prev arr/current-schema-version test-blind-fn test-encrypt-fn))

(defn- facts [n]
  (for [i (range n)]
    {:s (str "0x" (format "%06x" i)) :p "paid" :o (str (* 10 (inc (mod i 7))))}))

(defn- ms-since [t0] (Math/round (double (/ (- (System/nanoTime) t0) 1e6))))

;; the query every strategy has to answer identically
(defn- q [db] (arr/by-predicate-value db "paid" "30"))

(defn- build-partitioned [{:keys [put!]} total k]
  (let [per (quot total k)]
    (into {}
          (map (fn [p]
                 [(str "p" p)
                  (commit! put! (reduce arr/assert-quad (arr/empty-db)
                                        (take per (drop (* p per) (facts total))))
                           nil)]))
          (range k))))

(defn- run-k [total k queries]
  (let [{:keys [put! get-fn reads] :as s} (mem-store)
        parts (build-partitioned s total k)
        root (part/put-root! put! parts nil)
        single-cid (commit! put! (reduce arr/assert-quad (arr/empty-db) (facts total)) nil)

        ;; :eager-merge — pay the hydrate on EVERY query
        _ (reset! reads 0)
        t0 (System/nanoTime)
        eager-answers (doall (for [_ (range queries)]
                               (q (part/restore-all get-fn root test-decrypt-fn))))
        eager-ms (ms-since t0)
        eager-reads @reads

        ;; :single — one snapshot, hydrate once, query many
        _ (reset! reads 0)
        t1 (System/nanoTime)
        single-db (arr/restore get-fn single-cid test-decrypt-fn)
        single-hydrate (ms-since t1)
        t2 (System/nanoTime)
        single-answers (doall (for [_ (range queries)] (q single-db)))
        single-q-ms (ms-since t2)
        single-reads @reads

        ;; :compacted — fold the k partitions ONCE, then query many
        _ (reset! reads 0)
        t3 (System/nanoTime)
        folded (part/restore-all get-fn root test-decrypt-fn)
        fold-ms (ms-since t3)
        t4 (System/nanoTime)
        folded-answers (doall (for [_ (range queries)] (q folded)))
        folded-q-ms (ms-since t4)
        fold-reads @reads]
    {:k k
     :eager-ms eager-ms :eager-reads eager-reads
     :single-hydrate single-hydrate :single-q single-q-ms :single-reads single-reads
     :fold-ms fold-ms :compacted-q folded-q-ms :fold-reads fold-reads
     :same? (= (set eager-answers) (set single-answers) (set folded-answers))}))

(defn -main [& args]
  (let [total (Integer/parseInt (or (first args) "2000"))
        queries (Integer/parseInt (or (second args) "20"))
        ks (map #(Integer/parseInt %) (or (seq (drop 2 args)) ["1" "10" "50" "200"]))]
    (println (format "\n%d facts held constant, %d queries per strategy\n" total queries))
    (println (format "%5s | %12s %10s | %12s %8s | %10s %10s %10s | %s"
                     "k" "eager ms" "eager rd" "single hyd" "q ms" "fold ms" "cmpct q" "fold rd" "same?"))
    (doseq [k ks]
      (let [r (run-k total k queries)]
        (println (format "%5d | %12d %10d | %12d %8d | %10d %10d %10d | %s"
                         (:k r) (:eager-ms r) (:eager-reads r)
                         (:single-hydrate r) (:single-q r)
                         (:fold-ms r) (:compacted-q r) (:fold-reads r)
                         (if (:same? r) "yes" "NO")))))
    (println)
    (shutdown-agents)))
