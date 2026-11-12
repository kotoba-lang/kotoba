(ns oracle.fs-datom-adapter
  "Filesystem-shaped oracle over a datom plane (one-shot measurement only).

  Shape mirrors `kotoba.lang.fs` IFilesystem (read/write/list/exists?/delete
  over named paths), but every read is servable from a verified,
  range-pruned index -- never a full hydration.

  Production wiring (NOT in this file, documented so the oracle stays honest):
  `ayatori.remote/open-snapshot` + `ayatori.remote/q` (and `q-async` on the
  Worker path). A file at PATH becomes datoms
    {:s PATH :p :fs/path    :o PATH}
    {:s PATH :p :fs/content :o CONTENT}
  and a read is the Datalog query
    {:find [?c] :where [[?e :fs/path PATH] [?e :fs/content ?c]]}
  evaluated with an explicit `visible?` (e.g. `(constantly true)` for the
  oracle). A directory listing is a prefix range scan over the :fs/path
  index. This matches the supported contract in
  `kotobase.query.bridge` (Datalog is the right frontend when the caller's
  language IS Datalog-shaped, as here) and the fitness judge in
  `bench/fitness.cljk` (round trips + bytes, rows must agree or exit 2).

  Discipline, per ADR-2608160100 carried by bench/fitness.cljk:
  the scored metric is operation/round-trip counts (primary) plus bytes;
  wall clock is reported with a loaded-machine caveat, never scored.

  Oracle rules: this file lives under project-top `oracle/` and is a one-shot
  measurement. Never wire it into CI, gates, builds, packaging, or execution
  paths. No silent fallback: callers handle nil/errors explicitly."
  (:require [clojure.string :as str]))

(def path-sep "/")

(defn- blank? [s] (or (nil? s) (and (string? s) (str/blank? s))))

(defn normalize
  "Lexical normalize. Refuses escapes (.. above root), like fs-host."
  [p]
  (let [s (str p)
        segs (remove str/blank? (str/split s #"/"))
        absolute? (str/starts-with? s path-sep)]
    (when (some #(= % "..") segs)
      (throw (ex-info "fs-datom: path escapes root"
                      {:type :fs/escape :path s})))
    (when (blank? s)
      (throw (ex-info "fs-datom: empty path"
                      {:type :fs/empty-path :path s})))
    (let [stack (reduce (fn [acc seg]
                          (cond (= seg ".") acc
                                :else (conj acc seg)))
                        [] segs)
          joined (str/join path-sep stack)]
      (cond absolute? (str path-sep joined)
            (empty? stack) "."
            :else joined))))

(defn- parent-dir [norm-path]
  (let [segs (remove str/blank? (str/split norm-path #"/"))]
    (if (<= (count segs) 1)
      ""
      (str/join path-sep (butlast segs)))))

(defn make-store
  "Create an empty datom-plane store. Stats count logical round trips:
  one per read/write/list/exists?/delete op (each servable by one
  range-pruned index read or one commit)."
  ([] (make-store {}))
  ([_opts]
   (atom {:datoms []        ;; vector of {:s :p :o}
          :by-path {}       ;; PATH -> {:content ... :size ...} (the :fs/path index)
          :stats {:reads 0 :writes 0 :round-trips 0 :bytes 0}})))

(defn- bump! [store k n-bytes]
  (swap! store update :stats
         (fn [st]
           (-> st
               (update :reads + (if (= k :reads) 1 0))
               (update :writes + (if (= k :writes) 1 0))
               (update :round-trips inc)
               (update :bytes + (or n-bytes 0))))))

(defn fs-write!
  "Write CONTENT (string) at PATH. Upserts :fs/path + :fs/content datoms.
  Returns nil, like kotoba.lang.fs/write."
  [store path content]
  (let [p (normalize path)
        text (str content)
        n (count text)]
    (swap! store
           (fn [s]
             (-> s
                 (update :datoms
                         (fn [ds]
                           (let [kept (remove #(= (:s %) p) ds)]
                             (conj (vec kept)
                                   {:s p :p :fs/path :o p}
                                   {:s p :p :fs/content :o text}))))
                 (assoc-in [:by-path p] {:content text :size n}))))
    (bump! store :writes n)
    nil))

(defn fs-read
  "Read PATH, or nil when absent. One indexed lookup (one round trip)."
  [store path]
  (let [p (normalize path)
        entry (get (:by-path @store) p)
        text (:content entry)]
    (bump! store :reads (if text (count text) 0))
    text))

(defn fs-exists?
  "True when PATH names a file. One indexed lookup."
  [store path]
  (let [p (normalize path)
        hit (contains? (:by-path @store) p)]
    (bump! store :reads 0)
    hit))

(defn fs-list
  "List immediate children of DIR (sorted). One prefix range scan.
  DIR \"\" or \"/\" lists top-level names."
  [store dir]
  (let [d (if (or (nil? dir) (blank? (str dir))) "" (normalize (str dir)))
        prefix (if (or (= d "") (= d path-sep)) "" (str d path-sep))
        names (->> (keys (:by-path @store))
                   (filter #(str/starts-with? % prefix))
                   (map #(subs % (count prefix)))
                   (remove #(str/includes? % path-sep))
                   (remove str/blank?)
                   (sort)
                   (vec))]
    (bump! store :reads 0)
    names))

(defn fs-delete!
  "Delete PATH when present. One commit. Returns nil."
  [store path]
  (let [p (normalize path)]
    (swap! store
           (fn [s]
             (-> s
                 (update :datoms (fn [ds] (vec (remove #(= (:s %) p) ds))))
                 (update :by-path dissoc p))))
    (bump! store :writes 0)
    nil))

(defn stats
  "Snapshot of {:reads :writes :round-trips :bytes}."
  [store] (:stats @store))

(defn reset-stats!
  "Reset counters, keep data. Returns nil."
  [store]
  (swap! store assoc :stats {:reads 0 :writes 0 :round-trips 0 :bytes 0})
  nil)

(defn snapshot
  "Sorted [path content] pairs, for the answer-equivalence gate."
  [store]
  (->> (:by-path @store)
       (map (fn [[p {:keys [content]}]] [p content]))
       (sort-by first)
       (vec)))
