# okugai

**屋外広告物（physical / out-of-home advertising）の一般ドメイン。純 `.cljc`、依存ゼロ。**

「おくがい」= 屋外。電柱広告（[`denchu`](../denchu)）はこの体系の中の **1 媒体**でしか
ない。この repo が答えるのは、媒体を問わず共通の 5 つ:

| 問い | ns |
|---|---|
| どんな物理媒体があり、**どの観測タグで見つかるか** | `okugai.medium` |
| その座標に掲出地点があるか（複数の観測源をどう束ねるか） | `okugai.site` |
| **どの法令が実際に効くか**（管轄別・媒体別・寸法別） | `okugai.facts` |
| 誰に照会できるか（媒体非依存の部分） | `okugai.route` |
| いくらか（**常に参考値**）／出稿はどう進むか | `okugai.pricing` `okugai.order` |

媒体固有の知識 — 電柱の供給区域・指定代理店・巻付/袖の面・公開料金表 — は媒体 repo
が持つ。観測の収集は [`loop-okugai-survey`](../loop-okugai-survey) が
[`org-openstreetmap-overpass`](../org-openstreetmap-overpass) と
[`com-mapillary-graph-api`](../com-mapillary-graph-api) を叩いて行う。

## 媒体タクソノミー（14 媒体、うち観測で見つかるのは 10）

```
utility-pole  電柱広告        power=pole / man_made=utility_pole   → denchu
billboard     野立看板        advertising=billboard
board         広告板（小型）  advertising=board      ← 実測で最多
screen        屋外ビジョン    advertising=screen
poster-box    ポスターボックス advertising=poster_box
column        円柱広告        advertising=column
totem         トーテム        advertising=totem
sign          広告サイン      advertising=sign
wall          壁面広告        advertising=wall_painting
banner        バナー・幕      advertising=flag / tarp
─────────────────────────────────────────────── 以下は観測では見つからない
rooftop                 屋上看板（点検出から『屋上にある』は判定できない）
expressway-service-area SA/PA 内広告（施設内の媒体は地図にも写真にも出ない）
expressway-roadside     高速道路沿道（billboard と同一タグ。距離での後付け分類）
transit-shelter         シェルター広告（停留所の位置はあるが広告面の有無は無い）
```

**観測タグを持たない媒体を `observable-media` から外して申告する。** 隠すと
「survey に出なかった＝存在しない」と読まれる。これらは媒体社カタログか現地調査
からしか入らない。

OSM タグの値は**実測に基づく**（2026-08-04、都心 bbox で 46 件: board 25 / billboard 9
/ screen 7 / poster_box 2 / column 1 / totem 1 / sign 1）。推測した値を混ぜると、
空応答が「媒体が無い」に見える。

## 規制は「効きうる」と「効く」を分ける（`okugai.facts`）

日本の屋外広告物は屋外広告物条例だけでは終わらない。**形状と場所**で上に載る:

| 規制 | 根拠 | 発動条件 |
|---|---|---|
| 屋外広告物条例の許可 | 屋外広告物法 → 各自治体条例 | 原則すべて（許可主体は**自治体**、国ではない） |
| 道路占用許可 | 道路法32条 | 道路上空・路上に出る |
| 道路使用許可 | 道路交通法 | 道路に工作物を設ける |
| **工作物確認申請** | 建築基準法88条1項（令138条1項3号） | **高さ4m超**の広告塔・広告板（屋上も広告塔部分が4m超なら対象）。確認済証前の着工は1年以下の懲役または100万円以下の罰金 |
| 看板等の防火措置 | 建築基準法64条 | **防火地域内**で建物屋上、または高さ3m超 → 主要部分を不燃材料 |
| 高速道路 | 道路法 + 沿道ガイドライン | 道路区域内は道路管理者（NEXCO 系媒体社）、沿道は条例の禁止区域指定が上乗せされうる |

**高さは媒体種別からは決まらない。** 同じ `:billboard` でも 3m と 6m がある。だから
`applicable` は `{:required :undetermined :not-applicable}` の 3 値を返し、
**寸法や区域が不明なら `:undetermined`** —— 不明を「不要」に倒すと、確認申請なしで
着工する提案が governor を通ってしまう。`okugai.order` は `:undetermined` が残る限り
`:permit-filed` に進めない。

必要証跡も**実際に効く規制から導出する**（固定リストにすると電柱に工作物確認済証を
要求するような嘘になる）。

## この repo が意図的に持たないもの

- **空き在庫を推定する関数**（`denchu` と同じ理由。推定した空き数は必ず嘘になる）
- **確定価格**（`quote-order` は常に `:quote/confidence :indicative`）
- **掲出可否の推定**（`:site/ad-eligible` は全件 `:unknown` から始まる）
- **高さの推定**（`:site/height-m` は常に nil から。88 条の判定に直結する）
- **所有者の推測**（`operator` タグに実名がある時だけ。媒体固有の候補導出は媒体 repo）

## 使う

```clojure
(require '[okugai.medium :as medium] '[okugai.facts :as facts] '[okugai.site :as site])

(medium/osm-selectors [:billboard :board :screen])
;; => [["advertising" "billboard"] ["advertising" "board"] ["advertising" "screen"]]

(facts/applicable {:medium :billboard :height-m 5.2 :fire-prevention-district? false
                   :overhangs-road? false :expressway-adjacent? false})
;; => {:required #{:outdoor-ad-permit :building-code-88} :undetermined #{} :not-applicable #{...}}

(facts/applicable {:medium :billboard})          ; 高さ不明
;; => {:required #{:outdoor-ad-permit} :undetermined #{:building-code-88 :building-code-64 ...}}
```

## テスト

```bash
kbb --backend sci --classpath src:test test/run.cljk     # 29 tests / 155 assertions
```

第一の runtime は ClojureScript / nbb。`.kotoba` に載せていないのは、地点→観測列→
タグ map という入れ子の値が要るのに recursive logical values が W4 待ちであるため。

MIT。
