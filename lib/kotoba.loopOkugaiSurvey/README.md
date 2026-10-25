# loop-denchu-survey

**電柱在庫の継続 survey orchestrator** — observe → evaluate → decide → act →
record-evidence。写真・地図データから電柱を特定し、`denchu` の在庫台帳
（datom 面に載る `*.datoms.edn`）に落とす。

`loop-*` は continuous orchestrator であって domain truth の持ち主ではない
（`manifest/repository-rules.edn` `:name-prefix`）。したがってこの repo は
**柱の定義も、窓口も、料金も、法令も持たない**:

| 委譲先 | 何を任せるか |
|---|---|
| [`denchu`](../denchu) | 柱の identity・束ね方・信頼度・面・窓口・料金・法令・出稿 |
| [`org-openstreetmap-overpass`](../org-openstreetmap-overpass) | OSM の QL と応答正規化（鍵なしで引ける） |
| [`com-mapillary-graph-api`](../com-mapillary-graph-api) | Mapillary の写真検出（token 必須、bbox タイル分割） |

ここが所有するのは『どの面をどの順で見て、何を証跡として残すか』だけ。

## 走らせる

```bash
kbb --backend sci --classpath "src:../denchu/src:../org-openstreetmap-overpass/src:../com-mapillary-graph-api/src" \
    bin/survey.cljk --area-id setagaya --jurisdiction JP-13 \
    --bbox 35.6200,139.6200,35.6600,139.6800 --sources osm --out data
```

`--bbox` は `south,west,north,east`（地図から読む順）。`--sources` は
`osm` / `mapillary` / `both`。`--jurisdiction` は **呼び出し側が宣言する** —
座標から逆引きして推測しない。

出力は 3 種:

```
data/denchu-inventory-<area>.datoms.edn   柱 + カバレッジ申告（area ごと）
data/denchu-catalog.datoms.edn            代理店・面種別の静的カタログ（共通1本）
data/survey-evidence-<area>.edn           入力・測定・閾値・落としたものの証跡
```

カタログを area shard に混ぜないのは、面をまたいで数えたときに代理店が area 数
だけ増えて見えるため（datom 面に upsert キーは無い）。同じ `denchu-inventory`
dataset なので join は従来どおりできる。

## survey 実測（2026-08-04、OSM のみ）

| area | 管轄 | 観測 | 柱 | 所有者判明 | 窓口確定 | **照会可（区域候補）** |
|---|---|---:|---:|---:|---:|---:|
| chiyoda-marunouchi | JP-13 | 0 | 0 | 0 | 0 | 0 |
| setagaya | JP-13 | 8 | 5 | 0 | 0 | **5** |
| kyoto-nakagyo | JP-26 | 55 | 55 | 0 | 0 | **55** |
| sapporo-chuo | JP-01 | 205 | 201 | 0 | 0 | **201** |
| 計 | | 268 | 261 | 0 | 0 | **261** |

**所有者判明が 0 なのは変わらない** — OSM に `operator` タグがほぼ付いていない
ため。`denchu` は所有者を推測しないので、これは黙って埋まらず
`:pole/owner "unknown"` として台帳に出る。

**しかし出稿導線は通る。** survey が宣言した管轄（`--jurisdiction`）を柱に刻む
ようになり、`denchu.area` が供給区域から候補所有者を出すので、261 本すべてが
`:pole/route-status "candidate-by-area"` になった。所有者はその照会（「この座標の
柱は御社の設備か」）で確定するのが実務であり、`denchu.order` はこの候補ルートでの
問い合わせを許す。**候補は柱ではなく経路に載る** — `:pole/owner` は unknown のまま。

丸の内が 0 件なのも実測値であって障害ではない（無電柱化の進んだ区域 + 中心部の
柱マッピングが薄い）。**area の外に柱が無いのではなく、見ていない。**

## 次に効く一手

1. **所有者の確定**: (a) 候補代理店への実照会（`denchu.order` の
   `:inquiry-proposed` → `:inquiry-sent`、`:external-send` risk）。(b) 現地の
   柱番号札を Mapillary の画像から読む経路 — `com-mapillary-graph-api` の
   `/images` + `detections` は実装済みだが **`MAPILLARY_ACCESS_TOKEN` が要る**
   （未取得。account 登録はオーナー作業）。
2. **Mapillary の併用**: `--sources both` で 2 source 一致が信頼度 +0.30。同上で token 待ち。
3. **電力側の窓口拡大**: 所有者 12 社中 5 社しか代理店を収録していない
   （未収録: 東北 / 中国 / 四国 / 九州 / 北海道 / 北陸 / 沖縄）。NTT 東西の窓口は
   全国を覆うので照会自体は全管轄で成立するが、電力柱だった場合の申込先は要調査。

## テスト

```bash
kbb --backend sci --classpath "src:test:../denchu/src" test/run.cljk    # 7 tests / 25 assertions
```

MIT。
