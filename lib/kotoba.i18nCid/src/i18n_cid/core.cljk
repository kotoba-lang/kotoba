(ns i18n-cid.core
  "The two seams between kotoba-lang/i18n catalogs and the content plane.

  Piece 1 (`catalog->dag` / `dag->catalog`): an i18n EDN catalog becomes an
  IPLD DAG-CBOR block addressed by CIDv1 — one block per locale catalog, and
  an index block linking every locale of one project. Translation diffs cost
  exactly one new block + a parent-link update; unchanged translations are
  shared block-for-block because their bytes are identical.

  Piece 2 (`lake-claim`): the catalog block is admitted to the kotobase-lake
  catalog plane, so Datalog/SQL/SPARQL/Cypher over the datom plane can ask
  what catalogs exist, for which locale/project, with which coverage —
  without a second index.

  Both pieces are pure: no HTTP, no sockets, no clock. Callers bring the
  put!/get-fn of their block store and ingest their own quads.

  Honesty boundary: this library encodes and addresses catalog bytes. It does
  not pin them (IPFS), announce them (IPNI), or authorize writes (Biscuit).
  Those are the caller's boundaries."
  (:require [kotoba.lang.text] [ipld.core :as ipld]
            [kotobase.lake.catalog :as lake]))

(def sniffer-note
  "lake.catalog/sniff classifies EDN by extension hint only when a prefix is
  supplied; we declare `application/edn` and pass the leading bytes so the
  declared-vs-observed verdict stays a comparison, not an assumption.")

(defn catalog->block
  "Encode `catalog` (flat keyword->string|select-map, i18n.core/register!
  shape) as canonical DAG-CBOR and return
  `{:cid .. :bytes .. :node <plain-data>}`. Keys are stringified (`:app/title`
  -> `\"app/title\"`) so the map is DAG-CBOR-legal (string keys only)."
  [catalog]
  (letfn [(key-str [k]
            (if (keyword? k)
              (if (namespace k)
                (str (namespace k) "/" (name k))
                (name k))
              (str k)))
          (walk [v]
            (cond
              (map? v) (into (sorted-map) (map (fn [[k x]] [(key-str k) (walk x)])) v)
              (sequential? v) (mapv walk v)
              (keyword? v) {"$kw" (if (namespace v)
                                    (str (namespace v) "/" (name v))
                                    (name v))}
              :else v))]
    (let [node (walk catalog)]
      (assoc (ipld/node->block node) :node node))))

(defn locale-index->block
  "Build the project index block: `{\"locales\" {\"ja\" <cid-string> ...}
  \"project\" <project> \"format\" \"i18n-catalog/1\"}`. `by-locale` maps a
  locale keyword to the `:cid` returned by [[catalog->block]]."
  [project by-locale]
  (let [node {"format"  "i18n-catalog/1"
              "project" (name project)
              "locales" (->> by-locale
                             (into (sorted-map)
                                   (map (fn [[loc cid]]
                                          [(name loc) (str cid)]))))}]
    (assoc (ipld/node->block node) :node node)))

(defn- index-links
  "Extract {locale-string -> link} from an index node, tolerating both the
  in-memory shape (Link records) and the decoded shape (link-wrapped maps
  already resolved to CID strings by the caller's get-node)."
  [index-node]
  (->> (get index-node "locales")
       (into {}
             (map (fn [[loc v]]
                    [loc (cond
                           (string? v) v
                           (map? v) (or (:cid v) (get v "/"))
                           :else (str v))])))))

(defn- unwrap [v]
  (cond
    (map? v) (if-let [kw (get v "$kw")]
               (if (re-find #"/" kw)
                 (let [[ns-n n] (kotoba.lang.text/split kw #"/" 2)]
                   (keyword ns-n n))
                 (keyword kw))
               (into {} (map (fn [[k x]]
                               [(if (re-find #"/" k)
                                  (let [[ns-n n] (kotoba.lang.text/split k #"/" 2)]
                                    (keyword ns-n n))
                                  (keyword k))
                                 (unwrap x)]))
                    v))
    (sequential? v) (mapv unwrap v)
    :else v))

(defn dag->catalog
  "Round-trip: fetch the locale catalog block by CID (via `get-fn`) and
  return the i18n.core/register! shape (keyword keys and keyword values,
  e.g. `{:select :count}`, restored via the `{\"$kw\" ..}` marker)."
  [get-fn cid]
  (let [node (ipld/get-node get-fn cid)]
    (->> node
         (into {}
               (map (fn [[k v]]
                      [(if (re-find #"/" k)
                         (let [[ns-n n] (kotoba.lang.text/split k #"/" 2)]
                           (keyword ns-n n))
                         (keyword k))
                        (unwrap v)]))))))

(defn index->locales
  "Read an index block back to `{:project .. :locales {\"ja\" \"bafk...\"}}`."
  [get-fn index-cid]
  (let [node (ipld/get-node get-fn index-cid)]
    {:project (get node "project")
     :locales (index-links node)}))

(defn lake-claim
  "Admit one catalog block into the kotobase-lake catalog plane. `cid` is the
  block's CID; the remaining descriptor keys follow `kotobase.lake.catalog/
  admit` (`:size` `:tenant` `:ingested-at` required). Returns admit's result
  unchanged (`:admitted?` + quads, or `:admitted? false` + `:refusals`)."
  [{:keys [cid size tenant ingested-at] :as descriptor}]
  (let [result (lake/admit
                (merge {:declared-media-type "application/edn"
                        :filename (str (name (or (:locale descriptor) :catalog))
                                       ".edn")}
                       descriptor))]
    result))

(defn lake-claim-index
  "Admit a project index block. Same contract as [[lake-claim]]."
  [{:keys [cid size tenant ingested-at project] :as descriptor}]
  (lake/admit
   (merge {:declared-media-type "application/edn"
           :filename (str (name (or project :project)) "-locales.edn")}
          descriptor)))
