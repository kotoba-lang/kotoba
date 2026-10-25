(ns rounds
  "What a table root costs, against what today's path costs, for the same answer.

  The unit is **requests**, not bytes and not wall-clock. On the hosts this
  stack ships to — a Worker ranging an object store, a browser ranging a
  bucket — a request is a round trip and bytes are nearly free by comparison;
  and this workstation runs many agents at once, so a timing number here
  would measure the load average. `kotobase-storage-pack` reports the same
  pair for the same reason.

  Both sides compute the answer and the answers are compared. A plan that
  fetched less and answered differently is not a faster plan."
  (:require [columnar.bytes :as cbytes]
            [columnar.aggregate]
            [columnar.plan :as cplan]
            [columnar.source :as csrc]
            [columnar.stats :as cstats]
            [columnar.vector :as cvec]
            [parquet.footer :as footer]
            [parquet.source :as psrc]
            [parquet.write :as pw]
            [tana.chunk-only-test :as chunk]
            [tana.member :as member]
            [tana.aggregate :as tagg]
            [tana.plan :as plan]
            [tana.shard :as shard]
            [tana.table :as table]))

(def ^:private hash-fn
  "Enough to address a value for a benchmark. Production injects sha2-256."
  (fn [s] (str "b" (hash s))))

(defn- object-bytes [rows]
  (pw/file {:fields (pw/fields-of (pw/columns-of-rows [["price" :int64]] rows))
            :batches (mapv (fn [b] (mapv second (pw/columns-of-rows [["price" :int64]] b)))
                           (partition-all 100 rows))}))

(defn- corpus
  "`n` objects of 300 rows each, in 3 row groups, with disjoint price ranges."
  [n]
  (mapv (fn [i]
          (let [base (* i 1000)
                rows (mapv (fn [j] {"price" (+ base j)}) (range 300))]
            {:object (str "obj:" i) :bytes (object-bytes rows)}))
        (range n)))

(defn baseline
  "Today's path: open every object, let each one prune its own row groups.

  This is what `net-kotobase/lake`'s trampoline does per object — leading
  magic, the 8-byte tail, the footer, then surviving column chunks — and it
  is what any Parquet reader must do when the only thing it holds is a list
  of objects."
  [objects predicates]
  (reduce (fn [acc {:keys [bytes]}]
            (let [{:keys [log source]} (cbytes/counting (cbytes/of-vector bytes))
                  {:keys [rows]} (cplan/scan (psrc/open source)
                                             {:columns ["price"] :predicates predicates})]
              (-> acc
                  (update :requests + (count (:ranges @log)))
                  (update :bytes + (:bytes @log))
                  (update :rows into (map #(get % "price")) rows))))
          {:requests 0 :bytes 0 :rows []} objects))

(defn with-tana
  "One root, then one ranged GET per surviving chunk."
  [objects root predicates]
  (let [by-object (into {} (map (juxt :object :bytes)) objects)
        p (plan/plan root {:columns ["price"] :predicates predicates
                           :trust :from-footers :coalesce-gap 0})
        rows (mapcat
              (fn [f]
                (let [[s e] (:range f)
                      raw (subvec (vec (get by-object (:object f))) s e)
                      member (first (filter #(= (:object f) (:object %)) (:members root)))
                      d (->> (:chunks member)
                             (keep #(let [c (get-in % [:columns "price"])]
                                      (when (= (:range c) [s e]) c)))
                             first)
                      col (chunk/decode-chunk raw d)]
                  (keep (fn [i]
                          (when (every? #(cstats/matches? col i %) predicates)
                            (cvec/value-at col i)))
                        (range (cvec/count col)))))
              (:fetch p))]
    ;; The root is a real object and its bytes are a real cost. Counting the
    ;; request and not the bytes would be the same dishonesty as a plan that
    ;; reports rows without reporting what it read.
    {:requests (:rounds p)
     :bytes (+ (:bytes p) (count (table/canonical root)))
     :root-bytes (count (table/canonical root))
     :rows (vec rows) :plan p}))

(defn with-shards
  "Two levels: the top, the manifests it could not rule out, then chunks."
  [objects root predicates per]
  (let [{:keys [top manifests]} (shard/split hash-fn root per)
        sel (plan/select-manifests top {:predicates predicates :trust :from-footers})
        fetched (mapv manifests (:fetch sel))
        merged (table/table (assoc root :members (vec (mapcat :members fetched))))
        below (with-tana objects merged predicates)]
    {:requests (+ 1 (count fetched) (dec (:requests below)))
     :bytes (+ (count (table/canonical top))
               (reduce + 0 (map (comp count table/canonical) fetched))
               (- (:bytes below) (:root-bytes below)))
     :rows (:rows below)
     :manifests (:manifests sel)}))

(defn aggregate-comparison
  "`max(price)` over the whole table, both ways.

  Parquet answers `max` from a footer with `:read 0` — so the baseline reads
  no column data either. What it cannot avoid is **opening every object** to
  reach those footers: 3 metadata requests each. The root already holds them."
  [objects root]
  (let [base (reduce (fn [acc {:keys [bytes]}]
                       (let [{:keys [log source]} (cbytes/counting (cbytes/of-vector bytes))
                             r (columnar.aggregate/aggregate (psrc/open source)
                                                             {:agg :max :column "price"})]
                         (-> acc
                             (update :requests + (count (:ranges @log)))
                             (update :values conj (:value r)))))
                     {:requests 0 :values []} objects)
        t (tagg/aggregate root {:agg :max :column "price" :trust :from-footers})]
    {:baseline-requests (:requests base)
     :baseline-value (reduce (fn [a b] (if (pos? (compare b a)) b a)) (:values base))
     :tana-requests (:requests t)
     :tana-value (:value t)
     :tana-read (:read t)}))

(defn- row [label {:keys [requests bytes]}] (str label "\t" requests "\t" bytes))

(defn run [n]
  (let [objects (corpus n)
        members (mapv (fn [{:keys [object bytes]}]
                        (member/from-parquet-footer {:object object :size (count bytes)}
                                                    (footer/parse bytes)))
                      objects)
        root (table/table {:table "prices" :columns ["price"]
                           :bounds-authority :from-footers :members members})
        ;; A predicate one object can satisfy. This is the shape a lake query
        ;; has: a point or a narrow range over a partitioned column.
        predicates [[:= "price" (+ (* (quot n 2) 1000) 205)]]
        b (baseline objects predicates)
        t (with-tana objects root predicates)
        s2 (with-shards objects root predicates 32)]
    (when-not (= (sort (:rows b)) (sort (:rows t)) (sort (:rows s2)))
      (println "ANSWERS DIFFER" (pr-str (:rows b)) (pr-str (:rows t)) (pr-str (:rows s2)))
      (js/process.exit 1))
    (when (empty? (:rows b))
      ;; Evidence floor: a query that matched nothing would make both sides
      ;; cheap and the comparison meaningless.
      (println "no rows matched — the comparison would be vacuous")
      (js/process.exit 2))
    (println (str "objects=" n
                  "  answer=" (pr-str (:rows b))
                  "  chunks total=" (get-in t [:plan :chunks :total])
                  " pruned=" (get-in t [:plan :chunks :pruned])
                  " read=" (get-in t [:plan :chunks :read])))
    (println "path\trequests\tbytes")
    (println (row "baseline (footer per object)" b))
    (println (str (row "tana (root + ranged GETs)" t)
                  "\t(root " (:root-bytes t) " of those)"))
    (println (str (row "tana sharded (top + manifests + GETs)" s2)
                  "\t(manifests " (pr-str (:manifests s2)) ")"))
    (println (str "sharded / baseline\t"
                  (/ (Math/round (* 10 (/ (:requests b) (:requests s2)))) 10.0) "x requests\t"
                  (/ (Math/round (* 10 (/ (:bytes b) (:bytes s2)))) 10.0) "x bytes  (>1 = tana cheaper; below the crossover it is not)"))
    (let [a (aggregate-comparison objects root)]
      (when-not (= (:baseline-value a) (:tana-value a))
        (println "AGGREGATE DIFFERS" (pr-str a))
        (js/process.exit 1))
      (println (str "max(price)\tbaseline " (:baseline-requests a) " requests"
                    "\ttana " (:tana-requests a) " request, :read " (:tana-read a)
                    "\tvalue " (:tana-value a))))
    (println)))

(doseq [n [1 3 10 50 200 1000]] (run n))
