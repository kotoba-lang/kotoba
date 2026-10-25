# com-mapillary-graph-api

**Mapillary Graph API v4 クライアント**（純 `.cljc` のリクエスト組み立て・応答
正規化 + nbb の I/O アダプタ）。

origin 面の repo。名前は authority の登録可能ドメイン `mapillary.com` を逆順に
した `com-mapillary` + 主題 `graph-api`（API host は `graph.mapillary.com`）。

## なぜ在るか

**写真データから電柱を特定する経路**。Mapillary はストリートレベル画像と、その
上の物体検出（Mapillary Vistas 由来の taxonomy）を公開している。`map_features`
は複数画像から三角測量された地物を座標付きで返すので、`denchu`（電柱広告）の
在庫候補を画像側から起こせる。OSM（`org-openstreetmap-overpass`）が人手の
マッピングに依存するのに対し、こちらは実際に撮られた道路の見え方から来る —
`loop-denchu-survey` が両方を束ねて、2 source 一致を信頼度に反映する。

## API の実測制約（公式ドキュメント、2026-08-04 確認）

| 項目 | 値 |
|---|---|
| host | `https://graph.mapillary.com` |
| 認証 | `?access_token=` または `Authorization: OAuth <token>`（**必須**） |
| endpoints | `/images` `/map_features` `/:image_id/detections` `/:map_feature_id/detections` |
| bbox | **0.01 度四方より小さいこと** → `split-bbox` でタイル分割が必須 |
| limit | 最大 2000 |
| 絞り込み | `map_features` は `object_values` |

## taxonomy（実文字列。推測した値を混ぜない）

```
object--support--utility-pole      ← 電柱の第一候補
object--support--pole
object--support--traffic-sign-frame
object--street-light
object--banner                     ┐
object--sign--advertisement        │ 掲出物が「実在した」観測
object--sign--store                │ （空き在庫の証拠ではない）
object--sign--information          ┘
```

存在しない object_value で絞ると空応答が返り、それは「柱が無い」ではなく
「間違った値で聞いた」である。だから値は定数として持ち、テストで固定している。

## 設計上の約束

- **token をコードに焼かない。** `fetch.cljs` は `MAPILLARY_ACCESS_TOKEN`
  環境変数からしか読まず、未設定なら**明示的に落ちる** — 空文字で叩いた 401 を
  「データが無い」と誤読させないため。
- **token は既定でヘッダに載せる**（`authorization-header`）。query string に
  置くとログ・履歴・Referer に残る。
- **bbox 超過は黙って切り詰めず投げる。** 広い面は `split-bbox` が決定論的に
  タイル化し、`fetch-poles` が**直列に**舐める（共有 API を並列で叩かない）。
- **読めなかった件数を返す**（`:unclassified`）。
- **`ad-presence` は在庫の主張ではない。** 掲出物が写っていることは、そこが
  売られていることも空いていることも意味しない。

## 使う

```clojure
(require '[com-mapillary-graph-api.core :as mly])
(mly/map-features-request {:west 139.765 :south 35.680 :east 139.769 :north 35.683}
                          {:object-values mly/pole-object-values})
;; => {:url "https://graph.mapillary.com/map_features" :query-params {...}}

;; nbb から（MAPILLARY_ACCESS_TOKEN が要る）
(require '[com-mapillary-graph-api.fetch :as f])
(-> (f/fetch-poles bbox) (.then (fn [r] (count (:observations r)))))
```

## テスト

```bash
kbb --backend sci --classpath src:test test/run.cljk     # 8 tests / 32 assertions
```

画像および検出データは Mapillary / その contributors のもので、利用は Mapillary の
利用規約に従う。

MIT。
