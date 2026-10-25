(ns arrangement.writer-contention-bench
  "Measure what the partitioned root actually buys: single-lane CAS vs
  partition-per-writer, with real threads and a real compare-and-set.

  Three disciplines, same facts, same store:

  - `:single-naive`   read the root, restore, assert, commit, CAS. What a
                      stateless Worker does. Every retry discards a restore
                      AND a commit.
  - `:single-cached`  keep the db in memory and only re-read after a lost CAS.
                      What a WARM Durable Object does. This is the strong
                      baseline and the one worth beating; comparing only
                      against `:single-naive` would be a strawman.
  - `:partitioned`    commit your own partition uncontended, then swap one
                      pointer. `:partitioned-batched` additionally lets one
                      root update carry every writer's advance.

  Reported per run: wall-clock, `commit!` calls performed, `commit!` calls
  DISCARDED by a lost CAS, and CAS attempts. Wasted commits are the number
  the design argument rests on -- the claim is not that CAS gets cheaper but
  that what a lost CAS throws away gets smaller.

  Fairness notes, stated rather than buried:
  - The store is an in-memory atom with no I/O. Real storage would make the
    payload far more expensive relative to the pointer swap, which favours
    the partitioned side MORE than this measures. These numbers are a lower
    bound on the gap, not an upper one.
  - Every discipline is verified to produce the same set of triples before
    any timing is reported. A faster answer that is a different answer is
    not a result."
  (:require [arrangement.core :as arr]
            [arrangement.partitioned :as part]
            [arrangement.core-test :refer [test-blind-fn test-encrypt-fn test-decrypt-fn]]))

(def ^:private commits (atom 0))
(def ^:private wasted (atom 0))
(def ^:private cas-attempts (atom 0))

(defn- mem-store []
  (let [store (atom {})]
    {:put! (fn [cid bytes] (swap! store assoc cid bytes))
     :get-fn (fn [cid] (get @store cid))}))

(defn- commit! [put! db prev]
  (swap! commits inc)
  (arr/commit! put! db prev arr/current-schema-version test-blind-fn test-encrypt-fn))

(defn- quads-for [w m]
  (for [i (range m)] {:s (str "w" w "-" i) :p "paid" :o (str (* 10 (inc i)))}))

;; ── discipline 1: one lane, stateless (restore every attempt) ────────

(defn- run-single-naive [{:keys [put! get-fn]} root writers per-writer]
  (->> (for [w (range writers)]
         (future
           (doseq [q (quads-for w per-writer)]
             (loop []
               (swap! cas-attempts inc)
               (let [cur @root
                     db (arr/restore get-fn cur test-decrypt-fn)
                     cid (commit! put! (arr/assert-quad db q) cur)]
                 (when-not (compare-and-set! root cur cid)
                   (swap! wasted inc)
                   (recur)))))))
       doall (run! deref)))

;; ── discipline 2: one lane, warm (db cached; re-read only on loss) ───

(defn- run-single-cached [{:keys [put! get-fn]} root writers per-writer]
  (->> (for [w (range writers)]
         (future
           (loop [qs (quads-for w per-writer)
                  cur @root
                  db (arr/restore get-fn cur test-decrypt-fn)]
             (when (seq qs)
               (swap! cas-attempts inc)
               (let [db' (arr/assert-quad db (first qs))
                     cid (commit! put! db' cur)]
                 (if (compare-and-set! root cur cid)
                   (recur (rest qs) cid db')
                   ;; lost: the commit we just paid for is discarded and the
                   ;; whole db has to be re-read from whoever won.
                   (do (swap! wasted inc)
                       (let [cur' @root]
                         (recur qs cur' (arr/restore get-fn cur' test-decrypt-fn))))))))))
       doall (run! deref)))

;; ── discipline 3: partition per writer ───────────────────────────────

(defn- cas-ops [{:keys [put! get-fn]} root]
  {:read-current (fn [] @root)
   :cas! (fn [expected new]
           (swap! cas-attempts inc)
           ;; a lost CAS here discards a pointer swap, not a payload --
           ;; which is the entire point, so nothing is added to `wasted`.
           (compare-and-set! root expected new))
   :put! put! :get-fn get-fn})

(defn- run-partitioned
  "`mode` :per-write (advance the root after every commit), :deferred (advance
  once per writer), or :batched (every writer's advance in ONE root update)."
  [{:keys [put!] :as s} root writers per-writer mode]
  (let [tips (atom {})
        fs (doall
            (for [w (range writers)]
              (future
                (let [ops (cas-ops s root) pkey (str "w" w)]
                  (loop [qs (quads-for w per-writer) db (arr/empty-db) prev nil]
                    (if (seq qs)
                      (let [db' (arr/assert-quad db (first qs))
                            cid (commit! put! db' prev)]   ; UNCONTENDED
                        (when (= mode :per-write) (part/advance-root! ops pkey cid))
                        (recur (rest qs) db' cid))
                      (case mode
                        :deferred (part/advance-root! ops pkey prev)
                        :batched  (swap! tips assoc pkey prev)
                        nil)))))))]
    (run! deref fs)
    (when (= mode :batched)
      (part/advance-root-batched! (cas-ops s root) @tips))))

;; ── harness ──────────────────────────────────────────────────────────

(defn- facts-in-root [get-fn root partitioned?]
  (set (part/db->quads
        (if partitioned?
          (part/restore-all get-fn @root test-decrypt-fn)
          (arr/restore get-fn @root test-decrypt-fn)))))

(defn- bench-run [label writers per-writer f partitioned?]
  (reset! commits 0) (reset! wasted 0) (reset! cas-attempts 0)
  (let [s (mem-store)
        root (atom nil)
        t0 (System/nanoTime)
        _ (f s root writers per-writer)
        ms (/ (- (System/nanoTime) t0) 1e6)]
    {:discipline label
     :ms (Math/round (double ms))
     :commits @commits
     :wasted-commits @wasted
     :cas-attempts @cas-attempts
     :facts (facts-in-root (:get-fn s) root partitioned?)}))

(defn -main [& args]
  (let [writers (Integer/parseInt (or (first args) "8"))
        per-writer (Integer/parseInt (or (second args) "25"))
        expected (set (mapcat #(quads-for % per-writer) (range writers)))
        runs [(bench-run :single-naive writers per-writer run-single-naive false)
              (bench-run :single-cached writers per-writer run-single-cached false)
              (bench-run :partitioned writers per-writer
                         #(run-partitioned %1 %2 %3 %4 :per-write) true)
              (bench-run :partitioned-deferred writers per-writer
                         #(run-partitioned %1 %2 %3 %4 :deferred) true)
              (bench-run :partitioned-batched writers per-writer
                         #(run-partitioned %1 %2 %3 %4 :batched) true)]]
    (println (format "\n%d writers x %d writes = %d facts\n" writers per-writer (count expected)))
    (println (format "%-22s %8s %9s %9s %9s  %s"
                     "discipline" "ms" "commits" "wasted" "cas" "facts-correct?"))
    (doseq [{:keys [discipline ms commits wasted-commits cas-attempts facts]} runs]
      (println (format "%-22s %8d %9d %9d %9d  %s"
                       (name discipline) ms commits wasted-commits cas-attempts
                       (if (= facts expected) "yes" (str "NO (" (count facts) "/" (count expected) ")")))))
    (println)
    (shutdown-agents)))
