(ns kotoba.ontology.connector
  "Registry of external-data connectors, and the pure step that tags a
  normalized fact with ontology provenance before it lands in a
  cloud-itonami-* activity/artifact graph.

  Fetch/parse stays where kotoba-lang/goyoukiki already put it: a per-source
  JVM-only adapter (goyoukiki.jp.kkj, goyoukiki.jp.geps) that does the actual
  HTTP call and maps the raw response to the domain's own pure-data model.
  This namespace does not fetch anything — it only records which connectors
  exist, what object type they produce, and how to stamp their output with
  :ontology/* provenance so it can be told apart from every other source."
  (:require [kotoba.ontology :as ontology]))

(def registry
  {:kotoba.registry/id :kotoba/ontology-connectors
   :kotoba.registry/version 1
   :connectors
   [{:id :jp.kkj
     :name "kkj.go.jp 官公需情報ポータル 検索API"
     :object-type :tender
     :repo "https://github.com/kotoba-lang/goyoukiki"
     :status :implemented}
    {:id :jp.geps
     :name "GEPS 落札実績オープンデータ"
     :object-type :tender
     :repo "https://github.com/kotoba-lang/goyoukiki"
     :status :implemented}]})

(defn connectors
  ([] (connectors registry))
  ([reg] (:connectors reg)))

(defn by-id
  ([] (by-id registry))
  ([reg] (into {} (map (juxt :id identity) (connectors reg)))))

(defn get-connector
  ([id] (get-connector registry id))
  ([reg id] (get (by-id reg) id)))

(defn tag
  "Attach ontology provenance to an already-normalized fact map. Pure — the
  live fetch stays in the connector's own adapter; this only marks where a
  fact came from and what object type it claims to satisfy.

  Fails closed rather than producing a quietly-wrong fact. Three refusals,
  each carrying its own `:reason` in `ex-data` so a caller can tell them
  apart without matching on the message:

  - `:unregistered-connector` — no registry entry for `connector-id`.
  - `:connector-without-object-type` — the entry exists but declares no
    `:object-type` (a `:status :planned` id reserved ahead of its adapter).
    Stamping it would write `:ontology/type nil`: a label that names a
    source but claims no type is not provenance, and it makes
    `tagged-conforms?` on the result ambiguous instead of false.
  - `:provenance-overwrite` — `fact` already carries an `:ontology/source`
    naming a *different* connector. Re-stamping it would launder where the
    fact came from, which is the one thing this registry exists to record.
    Re-tagging with the same id is allowed and idempotent.

  Every caller in this fleet tags a freshly-normalized map with an id it
  registered itself, so none of these can fire from correct code — they
  exist to catch a typo'd id, a half-registered connector, or a re-stamp
  loudly instead of silently."
  [connector-id fact & {:keys [reg fetched-at confidence]
                        :or {reg registry}}]
  (let [{:keys [object-type] :as connector} (get-connector reg connector-id)
        prior-source (:ontology/source fact)]
    (when-not connector
      (throw (ex-info (str "unregistered connector: " connector-id)
                      {:reason :unregistered-connector
                       :connector-id connector-id :known-ids (mapv :id (connectors reg))})))
    (when-not object-type
      (throw (ex-info (str "connector declares no object-type: " connector-id)
                      {:reason :connector-without-object-type
                       :connector-id connector-id :connector connector})))
    (when (and prior-source (not= prior-source connector-id))
      (throw (ex-info (str "fact already tagged by a different connector: " prior-source)
                      {:reason :provenance-overwrite
                       :connector-id connector-id :prior-source prior-source})))
    (cond-> (assoc fact :ontology/type object-type :ontology/source connector-id)
      fetched-at (assoc :ontology/fetched-at fetched-at)
      confidence (assoc :ontology/confidence confidence))))

(defn tagged-conforms?
  "True when `fact` both conforms to its connector's declared object type
  and carries :ontology/* provenance from a registered connector."
  ([connector-id fact] (tagged-conforms? registry ontology/registry connector-id fact))
  ([conn-reg onto-reg connector-id fact]
   (let [{:keys [object-type]} (get-connector conn-reg connector-id)]
     (boolean
      (and object-type
           (= object-type (:ontology/type fact))
           (= connector-id (:ontology/source fact))
           (ontology/conforms? onto-reg object-type (dissoc fact :ontology/type :ontology/source
                                                             :ontology/fetched-at :ontology/confidence)))))))
