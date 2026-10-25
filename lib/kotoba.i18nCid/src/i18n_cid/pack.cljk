(ns i18n-cid.pack
  "Piece 4: pack the catalog blocks of one project into a single CARv2.

  `i18n-cid.core` builds one DAG-CBOR block per locale plus one project index
  block, and `i18n-cid.pin` asks a Pinning Service to hold a CID. A Pinning
  Service is a remote node that fetches by CID, and each block currently lives
  at its own CID — so the caller pays one round trip per block. A CARv2 makes
  a project's whole catalog set one object: a byte container whose header
  says exactly which byte range each block lives in, so a Worker can serve any
  locale with a single ranged read once it has the archive.

  `pack` is the write side: encode every locale catalog and the project index
  with `i18n-cid.core`, then bundle them with `kotoba-lang/io-ipld-car`'s
  `ipld.car.v2/pack`. `unpack` is the inverse: `v2/read-all` over the archive
  bytes, resolve the index from the roots, and hand each locale block back to
  `i18n-cid.core/dag->catalog` so string CIDs and keyword maps round-trip.

  Like the rest of i18n-cid this is pure: no sockets, no store. `pack` returns
  the archive bytes and the caller's `put!` (in whatever object store they
  choose) decides where those bytes live. `unpack` holds the bytes in memory —
  the single-range reader is the caller's, per io-ipld-car's contract."
  (:require [i18n-cid.core :as ic]
            [ipld.car.v2 :as v2]))

(defn pack
  "Bundle `by-locale` (`{locale-keyword catalog}`, `i18n.core/register!`
  shape) and a project `project` index into one CARv2.

  Each catalog becomes a DAG-CBOR block via [[i18n-cid.core/catalog->block]];
  the project index is built with [[i18n-cid.core/locale-index->block]] and
  is the archive's only root (it links every locale CID). All blocks — index
  last — are handed to `ipld.car.v2/pack` with `:index?` on, so the archive
  carries an index a ranged reader can use.

  Returns `{:car-bytes .. :entries [...] :index-cid .. :locale-cids {locale
  cid-string}}`. `:entries` are the archive's frame records from
  `v2/pack` (what a ranged reader needs); `:index-cid` and `:locale-cids` name
  the blocks so the caller can pin, announce or store just the roots."
  [project by-locale]
  (let [locale-blocks (->> by-locale
                           (map (fn [[loc catalog]]
                                   [loc (ic/catalog->block catalog)]))
                           (into {}))
        index (ic/locale-index->block
               project
               (into {} (map (fn [[loc {:keys [cid]}]] [loc cid]) locale-blocks)))
        blocks (conj (mapv (fn [[_ {:keys [cid bytes]}]]
                             {:cid cid :bytes bytes})
                           locale-blocks)
                     {:cid (:cid index) :bytes (:bytes index)})
        packed (v2/pack {:roots [(:cid index)] :blocks blocks})]
    {:car-bytes (:bytes packed)
     :entries (:entries packed)
     :index-cid (:cid index)
     :locale-cids (into {} (map (fn [[loc {:keys [cid]}]] [loc cid]) locale-blocks))}))

(defn unpack
  "Read a CARv2's `car-bytes` back to catalogs.

  `v2/read-all` decodes the archive in memory (`{:roots :entries :blocks}`)
  where `:blocks` is `{cid bytes}`. The first root is the index block, resolved
  with [[i18n-cid.core/index->locales]] to the set of locale CIDs, and each
  locale block is decoded back through
  [[i18n-cid.core/dag->catalog]].

  Returns `{:index-cid .. :project .. :locales {locale cid} :catalogs {locale
  catalog}}` — the catalog maps restore string keys to keywords, so the result
  of `unpack` is `=` to the `:catalogs` that produced the archive."
  [car-bytes]
  (let [{:keys [roots blocks]} (v2/read-all car-bytes)
        get-fn (fn [cid] (get blocks cid))
        index-cid (first roots)
        {:keys [project locales]} (ic/index->locales get-fn index-cid)
        by-kw (into {} (map (fn [[loc cid]] [(keyword loc) cid]) locales))]
    {:index-cid index-cid
     :project (keyword project)
     :locales by-kw
     :catalogs (into {} (map (fn [[loc cid]] [loc (ic/dag->catalog get-fn cid)]) by-kw))}))