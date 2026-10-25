(ns atprotocol.projection
  "record ⇄ datom codec の契約 (ADR-2607071500)。

  atproto record は kotoba graph の投影に過ぎない。この ns は codec の
  **形** (契約) を定義するだけで、変換の実装は消費側が注入する — 参照実装は
  aozora の本番コード (下記 reference-implementation) で、移植はしない。
  langchain の :db-api map と同じ『protocol は map、実装は差し替え』流儀。")

(def reference-implementation
  "この契約を既に本番実装しているコードへのポインタ (as data)。"
  {:record->datoms "aozora.pds.encode/record->entity (app.bsky.feed.post / graph.follow / actor.profile → :yoro.* entity)"
   :datoms->view "aozora.appview.scan/scan + post-row->feed-view-post (datoms → bsky view)"
   :generic-record "aozora.pds.encode/generic-entity (:atproto.record/* — 未知 collection の保全)"})

(defn codec
  "codec 実装 map を検証して返す。
  {:record->datoms (fn [{:keys [collection uri cid value]}] → tx-data)
   :datoms->view   (fn [datoms] → view)
   :collections    #{nsid…} — この codec が投影を持つ collection}
  未知 collection は generic 保全 (:atproto.record/*) に落ちるのが契約 —
  投影が無いことはデータを失う理由にならない。"
  [{:keys [record->datoms datoms->view collections] :as impl}]
  (let [problems (cond-> []
                   (not (fn? record->datoms)) (conj :record->datoms)
                   (not (fn? datoms->view)) (conj :datoms->view)
                   (not (set? collections)) (conj :collections))]
    (if (seq problems)
      {:error :invalid-codec :missing problems}
      impl)))

(defn projects?
  "codec が collection の一級投影を持つか (false = generic 保全に落ちる)。"
  [{:keys [collections]} collection]
  (contains? collections collection))
