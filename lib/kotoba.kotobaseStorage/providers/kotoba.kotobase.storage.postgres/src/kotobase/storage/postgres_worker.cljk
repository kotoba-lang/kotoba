(ns kotobase.storage.postgres-worker
  "Promise-based PostgreSQL backend for Cloudflare Workers and Durable Objects.

  The JVM adapter in `kotobase.storage.postgres` takes a `javax.sql.DataSource`
  and cannot run on workerd. This namespace is its Worker twin: the same two
  tables, the same CAS semantics, the same capability set — reached through an
  injected query function instead of JDBC.

  Applications supply `:query`, a function of [sql-text params] returning a
  Promise of a row vector. The adapter imposes no driver, so the same code runs
  over Hyperdrive with postgres.js or node-postgres in a Worker, and over a
  plain client in Node for verification. Connection strings, Hyperdrive
  bindings and credentials stay in the host, never here."
  (:require [kotoba.lang.text :as str]
            [kotobase.storage.core :as storage]))

(def schema-statements
  ["CREATE TABLE IF NOT EXISTS kotobase_blocks (
      cid TEXT PRIMARY KEY, bytes BYTEA NOT NULL, byte_length BIGINT NOT NULL,
      created_at TIMESTAMPTZ NOT NULL DEFAULT now())"
   "CREATE TABLE IF NOT EXISTS kotobase_refs (
      name TEXT PRIMARY KEY, cid TEXT NOT NULL, revision BIGINT NOT NULL DEFAULT 1,
      updated_at TIMESTAMPTZ NOT NULL DEFAULT now())"])

(defn- ->bytes
  "Normalise a BYTEA column to Uint8Array. Drivers hand back Buffer (Node),
  Uint8Array (workerd), or a hex string, depending on which one the host
  injected; kotobase-peer only ever wants bytes."
  [value]
  (cond
    (nil? value) nil
    (instance? js/Uint8Array value) value
    (string? value) (js/Uint8Array.from
                     (map #(js/parseInt % 16)
                          (re-seq #".." (str/replace value #"^\\x" ""))))
    :else (js/Uint8Array. (.-buffer value)
                          (.-byteOffset value)
                          (.-byteLength value))))

(defn- same-bytes? [a b]
  (let [a (->bytes a) b (->bytes b)]
    (and a b
         (= (.-length a) (.-length b))
         (every? true? (map = (array-seq a) (array-seq b))))))

(defn- placeholders
  "$1,$2,... starting at `from`. PostgreSQL numbers its parameters, unlike JDBC."
  [n from]
  (str/join "," (map #(str "$" (+ from %)) (range n))))

(defrecord PostgreSQLWorkerStorage [query]
  storage/IBlockStore
  (-put-blocks! [_ blocks]
    (if (empty? blocks)
      (js/Promise.resolve [])
      ;; One statement for the whole batch: a Worker pays a network round trip
      ;; per statement, so a per-block loop would make write cost scale with
      ;; transaction size in latency, not just work.
      (let [rows (vec blocks)
            values (str/join ","
                             (map-indexed
                              (fn [i _] (str "(" (placeholders 3 (inc (* i 3))) ")"))
                              rows))
            params (into [] (mapcat (fn [{:keys [cid bytes]}]
                                      (let [b (->bytes bytes)]
                                        [cid b (.-length b)]))
                                    rows))]
        (-> (query (str "INSERT INTO kotobase_blocks(cid, bytes, byte_length)
                         VALUES " values " ON CONFLICT (cid) DO NOTHING")
                   params)
            (.then (fn [_]
                     ;; A CID whose bytes differ from what is already stored is a
                     ;; hash collision or a corrupted writer. Fail loudly rather
                     ;; than let DO NOTHING silently keep the wrong block.
                     (query (str "SELECT cid, bytes FROM kotobase_blocks WHERE cid IN ("
                                 (placeholders (count rows) 1) ")")
                            (mapv :cid rows))))
            (.then (fn [stored]
                     (let [by-cid (into {} (map (juxt #(get % "cid") #(get % "bytes"))
                                                (js->clj stored)))]
                       (doseq [{:keys [cid bytes]} rows]
                         (when-not (same-bytes? bytes (get by-cid cid))
                           (throw (ex-info "CID already has different bytes"
                                           {:type :kotobase.storage/cid-collision
                                            :cid cid}))))
                       (mapv :cid rows))))))))

  (-get-blocks [_ cids]
    (if (empty? cids)
      (js/Promise.resolve {})
      (-> (query (str "SELECT cid, bytes FROM kotobase_blocks WHERE cid IN ("
                      (placeholders (count cids) 1) ")")
                 (vec cids))
          (.then (fn [rows]
                   (into {} (map (fn [row]
                                   [(get row "cid") (->bytes (get row "bytes"))])
                                 (js->clj rows))))))))

  storage/IRefStore
  (-read-ref [_ name]
    (-> (query "SELECT cid, revision FROM kotobase_refs WHERE name = $1" [name])
        (.then (fn [rows]
                 (when-let [row (first (js->clj rows))]
                   {:cid (get row "cid")
                    :version (js/Number (get row "revision"))})))))

  (-compare-and-set-ref! [this name expected next]
    ;; The whole design rests on this being one atomic server-side statement.
    ;; Genesis is an INSERT that loses to any existing row; an advance is an
    ;; UPDATE guarded by the expected CID. Neither reads-then-writes, so two
    ;; concurrent writers cannot both win.
    (-> (if (nil? expected)
          (query "INSERT INTO kotobase_refs(name, cid) VALUES ($1, $2)
                  ON CONFLICT (name) DO NOTHING RETURNING cid, revision"
                 [name next])
          (query "UPDATE kotobase_refs
                  SET cid = $1, revision = revision + 1, updated_at = now()
                  WHERE name = $2 AND cid = $3 RETURNING cid, revision"
                 [next name expected]))
        (.then (fn [rows]
                 (if-let [row (first (js->clj rows))]
                   {:published? true
                    :current (get row "cid")
                    :version (js/Number (get row "revision"))}
                   ;; Lost the race. Report the winner so the caller can retry
                   ;; against the CID that actually won.
                   (-> (storage/-read-ref this name)
                       (.then (fn [current]
                                {:published? false
                                 :current (:cid current)
                                 :version (:version current)}))))))))

  storage/IBackendCapabilities
  (-capabilities [_]
    #{:immutable-blocks :cid-addressed-read :conditional-ref
      :linearizable-ref :batch-get :batch-put :server-transaction}))

(defn initialize!
  "Apply the schema. Same DDL as migrations/001_storage.sql and the JVM adapter,
  so a database created by either side is readable by the other."
  [query]
  (reduce (fn [p statement] (.then p (fn [_] (query statement []))))
          (js/Promise.resolve nil)
          schema-statements))

(defn open
  "Open a Worker-side PostgreSQL backend.

  `:query` — (fn [sql-text params] -> Promise<vector-of-row-objects>), required.
  `:initialize?` — apply the schema first; returns a Promise of the backend."
  [{:keys [query initialize?] :or {initialize? true}}]
  (when-not (ifn? query)
    (throw (ex-info "Worker PostgreSQL storage requires a :query function"
                    {:type :kotobase.storage/invalid-configuration
                     :backend :postgresql-worker})))
  (let [backend (->PostgreSQLWorkerStorage query)]
    (if initialize?
      (.then (initialize! query) (fn [_] backend))
      (js/Promise.resolve backend))))
