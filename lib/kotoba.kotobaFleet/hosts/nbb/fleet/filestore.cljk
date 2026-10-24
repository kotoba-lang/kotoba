(ns fleet.filestore
  "File-backed append-only :db-api store (nbb host).

  `kotoba.fleet.store/mem-store` is process-local, so two agent processes on two
  machines cannot see each other's leases. This host implements the SAME
  `:db-api` contract on a single append-only file — one `pr-str`'d [e a v t]
  datom per line — so `kotoba.fleet.lease` / `governor` / `agent` / `view` run
  unchanged across processes.

  The one invariant that must survive the move off an atom is the one
  `store.cljc`'s docstring is built around: **t is assigned atomically WITH the
  append**. `swap!` gave MemStore that for free; here it comes from an exclusive
  lock file (`open(path, 'wx')` — atomic create-or-fail on POSIX), held across
  read-length → append. Without it two racing processes both compute the same t
  and `lease/holder` (earliest active claim wins) hands the same exclusive lease
  to both.

  Host-owned I/O only: the coordination logic stays in the portable `.cljc`."
  (:require ["node:fs" :as fs]
            ["node:path" :as path]
            [kotoba.lang.text :as str]
            [cljs.reader :as reader]))

(def ^:private lock-stale-ms
  "A lock older than this is treated as abandoned (holder crashed) and broken."
  30000)

(defn- spin-ms [ms]
  (let [end (+ (js/Date.now) ms)]
    (while (< (js/Date.now) end) nil)))

(defn- acquire! [lock-path]
  (loop [tries 0]
    (let [fd (try (fs/openSync lock-path "wx")
                  (catch :default _ nil))]
      (cond
        fd fd

        (> tries 4000)
        (throw (ex-info "filestore: lock acquisition timed out" {:lock lock-path}))

        :else
        (do
          ;; break an abandoned lock (holder died before unlink)
          (try
            (let [age (- (js/Date.now) (.getTime (.-mtime (fs/statSync lock-path))))]
              (when (> age lock-stale-ms) (fs/unlinkSync lock-path)))
            (catch :default _ nil))
          (spin-ms 3)
          (recur (inc tries)))))))

(defn- with-lock [lock-path f]
  (let [fd (acquire! lock-path)]
    (try (f)
         (finally
           (try (fs/closeSync fd) (catch :default _ nil))
           (try (fs/unlinkSync lock-path) (catch :default _ nil))))))

(defn- read-log [log-path]
  (if-not (fs/existsSync log-path)
    []
    (->> (str/split-lines (fs/readFileSync log-path "utf8"))
         (remove str/blank?)
         (mapv reader/read-string))))

(defn- append-lines! [log-path datoms]
  (fs/appendFileSync log-path (str (str/join "\n" (map pr-str datoms)) "\n")))

(defn file-store
  "Append-only `:db-api` store backed by `log-path`. Creates parent dirs."
  [log-path]
  (fs/mkdirSync (path/dirname log-path) #js {:recursive true})
  (let [lock-path (str log-path ".lock")]
    {:transact!
     (fn [datoms]
       (let [ds (vec datoms)]
         (with-lock lock-path #(append-lines! log-path ds))
         {:added (count ds)}))

     ;; t := current log length, computed and appended under the SAME lock —
     ;; the file analogue of MemStore's swap!.
     :transact-with-t!
     (fn [build-fn]
       (with-lock lock-path
         (fn []
           (let [t  (count (read-log log-path))
                 ds (vec (build-fn t))]
             (append-lines! log-path ds)
             {:t t :added (count ds)}))))

     :datoms (fn [] (read-log log-path))

     :by (fn [a v]
           (filterv (fn [[_ da dv]] (and (= da a) (= dv v))) (read-log log-path)))

     :entity (fn [e]
               (reduce (fn [m [de a v]] (if (= de e) (assoc m a v) m))
                       {:db/id e}
                       (read-log log-path)))}))
