# torihiki-chart

[`torihiki`](https://github.com/kotoba-lang/torihiki) の取引所チャート。
データ → SVG 幾何の純関数群。ADR-2608040300（com-junkawasaki/root）。

**Tier**: `T2` **Role**: `library` **Status**: candle / depth / axis 実装済み、
38 tests / 1,568 assertions（JVM と nbb の両方）。

## 足は時間ではなくブロック

これがこの repo で唯一覚えておくべきこと。

`torihiki` は決定性のために **wall clock を持たない** —— エンジンの README が
『No wall clock. Logical time arrives in the block header』と書いているとおり、
時刻はブロックヘッダから来る。node の `/trades` が返す tape の要素は
`{:level :qty :side :h}` で、**`:h`（block height）が唯一の時間軸**。

なので足は **N ブロック単位**で、x 軸は block height。これを「時間足に見える
ように」時刻へ変換して描くことはしない —— 変換に使える真実がどこにも無く、
作れば嘘になる。**1 ブロックの実時間は一定でない**（validator は 200ms tick を
目標に走るが、view change や Durable Object の eviction で伸びる。復旧直後の
実測で tip 10 → 33 が約 1 分）ので、等間隔のブロック足を等間隔の時間として
読まれると誤読になる。

だから軸ラベルは `#4218` の形にしてある。`12:04` は時刻に見えるが `#4218` は
見えない —— 見た目でそれを防ぐのが軸の責任。

## 整数のまま集計する

価格は tick、数量は lot の整数で、`torihiki` は i53 の整数演算で閉じている
（`torihiki.fixed`）。OHLCV の集計にも軸の目盛りにも **float を使わない**。

理由は表示の綺麗さではなく **同一性**。tape は誰でも読めるので、二つの
クライアントが同じ tape から同じ足を出せることには意味がある —— チャートが
食い違えば、どちらかが嘘をついている。float に落ちるのは `d3` の scale に渡す
最後の一段だけで、そこは画素座標なので差が出ても値ではなく 1px に留まる。

ドル表記も整数で作る。`(/ cents 100.0)` は 2 進小数なので `$67,989.99` のような
1 セントずれた価格を平気で出す。

**1 tick = 10 セント。** live の mark `68000` tick は `$6,800.00` であって
`$68,000.00` ではない。`torihiki-terminal` の `view/dollars` には、この換算を
呼び出し側でやって 10 倍間違えた記録が docstring として残っている。

## scale と shape は再発明しない

[`kotoba-lang/d3`](https://github.com/kotoba-lang/d3) が d3-scale / d3-shape の
native cljc 再実装（JS interop ではない、外部依存ゼロ）を既に持っている。
その `band-scale` が返す `{:start :end :width}` は、ちょうど candle の body が
要る形。この repo が所有するのはその差分だけ:

| ns | 何を持つか |
|---|---|
| `torihiki-chart.candle` | tape → ブロック足 OHLCV、向き、レンジ |
| `torihiki-chart.axis` | 目盛り（1/2/5 × 10^k）、USD / height / lot のラベル |
| `torihiki-chart.view` | 足 → `[:svg …]` hiccup（ヒゲ・実体・出来高・グリッド） |
| `torihiki-chart.depth` | 板 snapshot → 深度図（階段、両側） |

SVG の**描画側**には依存しない。出力は hiccup の
`[:tag {:attrs} & children]` で、文字列にするかは消費者が決める。`d3` が
`svg` に依存しないのと同じ理由 —— 依存を減らすためではなく、出力が「文字列」
ではなく「データ」であることを保つため。

## 色を書かない。しかも `--hig-*` で書く

`view` と `depth` に色の literal は 1 つも無い。参照するのは **`--hig-*`** で
あって DADS の `--color-*` ではない。

`--hig-*` はこのワークスペース共通の token 契約（`shitsuke.hig` が発行し、
`jp-go-dds.tokens/hig->dads` が DADS primitive へ橋渡しする）なので、**skin が
kotoba-ui でも jp-go-dds でも同じチャートが正しく出る**。DADS の `--color-*` を
直に参照すると kotoba-ui skin のページでチャートだけ色を失い、しかも
**エラーにならない** —— 未定義の custom property はその宣言だけが黙って無効に
なる。

jp-go-dds skin では bridge の先が DADS primitive なので、
[`jp-go-dds.dark`](https://github.com/kotoba-lang/jp-go-digital-design-system) の
反転層に**無改造で追従する**。テストが hex の混入で落ちる。

## 描かないと決めたもの

- **空のバケットに横ばいの足を作らない。** 約定の無いブロック区間に足を
  置くのは、起きていないことを描くこと。
- **足が無いとき、空の枠ではなく `nil` を返す。** 空の軸だけの枠は「データが
  無い」ではなく「価格が無い」に見え、後者は嘘。呼び出し側が「まだ約定が
  ありません」と書く方が正しい。
- **深度は階段で描く。折れ線で結ばない。** 板の深さは価格の連続関数ではなく、
  注文の無い価格帯では平ら。折れ線は存在しない価格に存在しない流動性を描く
  ことになり、それは「薄い板でも滑らかに約定できそうに見える」という一番
  高くつく嘘。
- **累積を数え直さない。** `/book` の `:cum` は `torihiki.api/book-snapshot` が
  数える。同じ量を二箇所で計算すれば、いつか食い違う。

## テストが実際に捕まえたもの

書いた側の想定が間違っていた 3 件。どれも「エラーにならず、絵だけが静かに
違う」種類:

- **3 桁区切りを左から切っていた。** `$1234,567.80`。右から数えないと、桁数が
  3 の倍数でないときにずれる。
- **`peek` を LazySeq に当てていた**（深度図の面を閉じる箇所）。`ClassCastException`。
- **始値 = 終値の足の高さが 0** で、SVG が rect を描かない。動かなかった
  ブロックだけがチャートから消える、という一番読み違えやすい欠け方。下限 1px。

## 既知の制約

- **履歴は 200 件。** node の `/trades` は ring buffer で、それ以上の足を出すには
  node 側に集計が要る（ADR-2608040300 の未決事項）。
- **深度図は tape の制約を受けない** —— 板 snapshot から描くので。

## Test

```bash
kbb -M:test                                                   # JVM
kbb --backend sci --classpath "src:test:<path-to>/d3/src" test/run_tests.cljk   # ClojureScript
```

38 tests / 1,568 assertions、**両方で**。片方だけでは足りない —— `.cljc` は
両方で動くという主張であって、JVM で通ったことは主張の半分しか証明しない。
実際 `:candle-padding 3/10` は JVM で全部 green のまま ClojureScript の
コンパイルを落とした（Clojure の Ratio は cljs の定数になれない）。ブラウザ向けの
bundle を作った瞬間に初めて出る種類のずれで、`torihiki` 本体が `:parity` を
持っているのと同じ理由。

## なぜ `.kotoba` ではないのか

`torihiki` が `.kotoba` を退けた理由（native backend が record を関数境界越しに
運べない / capability 機構が無い / recursive value 未着地）がそのまま当てはまる。
加えて chart は hiccup という**任意深度の入れ子**を返すので、ADR-2607279200 の
W4（recursive logical values）が着地するまで `.kotoba` では表現できない。

中身は純関数（データ → 幾何）で capability を一切要求しないので、W4 後の
移行先としては第一候補。そのためにその形を保ってある。
