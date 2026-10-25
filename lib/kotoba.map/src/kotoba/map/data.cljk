(ns kotoba.map.data
  "Data layer: resolve a tile key to its MVT bytes via kotoba's
  content-addressed graph (a `quad-store` tile index queried through `kqe`,
  fetched CID-verified through `kotoba-client`), then hand those bytes to
  `kotoba.map.mvt/decode-layer-features`.

  This is the client-side-first replacement for `kotoba.map.tile-url`'s
  `{z}/{x}/{y}` HTTP template: kotobase.net only ever serves `block.get`
  CID lookups (delivery-only); this namespace does the query and assembly
  client-side, per the owner directive recorded in
  `90-docs/adr/2607010930-clj-wgsl-migration.md` Phase 6 (kotoba-lang/root
  superproject). `kotoba.map.tile-url` is unaffected and still used for
  hosts that only have a conventional XYZ tile server -- this namespace is
  an alternative data source, not a replacement of that one.

  A tile's raw MVT bytes are a single content-addressed block (no
  child-CID tree to walk), so hydrating one is the degenerate case of
  `kotoba-client.core/hydrate-via-blocks`: `missing-cids` returns the CID
  itself when absent from `store`, or nothing when already present.

  Visible-tile computation (`visible_globe_tiles` in the original Rust
  `kami-map`) is NOT done here -- it depends on the not-yet-ported
  `kami-geo` crate (see this repo's README, 'Unported' section) and is out
  of scope for this namespace too. Callers supply tile keys; this
  namespace only resolves and fetches them."
  (:require [quad-store.core :as qs]
            [kqe.core :as kqe]
            [kotoba-client.core :as kc]
            [kotoba.map.mvt :as mvt]))

(defn tile-key
  "Canonical string key for a `{:z :x :y}` tile, used as the quad-store
  subject for that tile's index entries."
  [{:keys [z x y]}]
  (str z "/" x "/" y))

(defn index-tile-layer
  "Add `{tile layer -> cid}` to `db` (a `quad-store.core` db). This is how a
  tile index gets populated -- by whatever synced/committed the graph, not
  by this namespace's read path."
  [db tile layer cid]
  (qs/assert-quad db {:s (tile-key tile) :p (str "mvt-cid:" layer) :o cid}))

(defn resolve-tile-cid
  "Look up the CID of `layer`'s MVT bytes for `tile` in `db`. Returns nil if
  `tile`/`layer` is not indexed."
  [db tile layer]
  (:o (first (kqe/query db [(tile-key tile) (str "mvt-cid:" layer) nil]))))

(defn fetch-tile-layer
  "Resolve `tile`'s `layer` to a CID via `db`, hydrate its bytes (CID-verified,
  via the injected `fetch-block` port into `store`), and decode with
  `kotoba.map.mvt/decode-layer-features`. Returns nil if `tile` has no
  indexed CID for `layer` in `db`.

  `store` is `{:put! (cid bytes -> _), :get-fn (cid -> bytes-or-nil)}`."
  [{:keys [db fetch-block store]} tile layer]
  (when-let [cid (resolve-tile-cid db tile layer)]
    (kc/hydrate-via-blocks
     {:missing-cids (fn [cid {:keys [get-fn]}] (if (get-fn cid) [] [cid]))
      :fetch-block fetch-block
      :store store}
     cid)
    (mvt/decode-layer-features ((:get-fn store) cid) tile layer)))
