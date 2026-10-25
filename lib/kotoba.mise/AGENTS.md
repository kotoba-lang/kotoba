# mise — 共有 EC システム（catalog / cart / pricing / inventory / checkout / order）

**Status: R2**

純粋な `.cljc` の EC ライブラリ。ネットワーク・I/O・時計への依存を持たず、
ホストが port を注入する。runtime dep は `shitsuke`（design system）/
`chobo`（audit ledger / subscription / invoice）/ `kessai`（決済 rail 抽象 ——
`mise.redirect` だけが使う）。

## 成熟度の梯子（この repo における R-tier の意味）

| tier | 意味 | 現在地 |
|---|---|---|
| R0 | 契約のスケッチのみ | — |
| R1 | 純粋な契約 + テスト | — |
| **R2** | **ドメイン契約が一通り揃い、test / lint / CI が緑。git 座標で消費可能。ただし本番の消費者で実証されていない** | **← いまここ** |
| R3 | 実際の消費者が本番でこれを叩いている | 未達 |
| R4 | 本番負荷で実証され、運用記録がある | 未達 |
| R5 | API が安定し、非互換変更に廃止手順がある | 未達 |

**R3 に上がるための不足**: 契約の穴は塞がった（下記 `mise.redirect`）が、
**本番でこれを叩く消費者がまだ無い**。最短の候補は murakumo.cloud の storefront
（現在は Stripe Checkout を直接呼んでいる）を `mise.redirect` 経由に寄せること。
ただし ADR-2608040100 のとおり本番稼働中の経路なので、動いているものを壊さない
順序で行う。

## 2 つの決済経路 —— 順序が逆であることが本質

    checkout/place-order : authorize → 成功なら Order を作る（card-present 由来）
    redirect/begin→confirm : Order(:pending) を作る → payer を送る → webhook で :paid

**`IPaymentPort` は hosted redirect を表現できない。** `authorize` が同期に成否を
返す前提で、`place-order` はその戻り値で注文を作る。リダイレクト決済では merchant は
authorization を発行せず、成否はあとから webhook で届くので、**注文は支払いの前に
作られていなければならない** —— でなければ webhook が「どの注文の話か」を引く先が無い。

`mise.redirect`（`kotoba.kessai.redirect` に依存する唯一の ns。`mise.checkout` は
素のまま）が守る不変条件:

- **戻り URL に success で戻ってきても注文は `:paid` にならない。** kessai 側で
  `observe-return` が構造上 settle できないので、この層に届く時点で必ず webhook を
  通っている。
- **注文対 session の突き合わせはここだけ。** kessai の金額照合は session 対 event
  なので、正しい金額の session を*別の注文*に当てるのはここでしか止められない。
- **通貨の minor unit を推測しない。** `minor-amount` は 3 桁小数通貨（KWD/BHD…）を
  拒否する —— ×100 で作ると 10 分の 1 の金額で session ができ、しかも決済は通る
  （少なく請求されるだけ）ので誰も気付かない。`:->minor` を明示的に渡させる。
- **`confirm` は `:pending` 以外を動かさない。** webhook 再送で二重に `:paid` に
  しない。

## 触るときの注意（実測で分かっていること）

- **`pricing/multiply` の nil 許容は仕様**。`cart/net-total` が「割引なし」を
  `(multiply nil -1)` で表現しており、ここで例外を投げると割引のない
  カートが全部落ちる。一方 `pricing/line-total` は nil 単価を**拒否する** ——
  明細行に単価が無いのはデータ不整合で、¥0 として描画すると「正当な無料商品」と
  区別がつかないまま代金が動く。
- **`inventory/reserve` は在庫不足を拒否して nil を返す**（2026-08-04 に変更）。
  以前は 0 に clamp していて、在庫割れを黙って吸収していた。clamp が要る用途には
  `reserve-clamped` を明示的に呼ぶ。`reserve-many` は all-or-nothing。
- **`checkout/postal-required?`** は郵便番号制度を持たない国（HK / AE / 香港・
  UAE 等）を知っている。郵便番号を無条件必須にすると、それは厳しい検証ではなく
  「誰も書いていない国別ブロックリスト」になる。
- テストは意図を日本語のコメントで持っている。**古い挙動を守っているテストを
  見つけたら、意図ごと書き換えてよい**（実例: `reserve-many` の旧テストは
  oversell を仕様として固定していた）。

## 検証

```bash
kbb -M:test   # 81 tests / 234 assertions
kbb -M:lint   # errors 0（warning は既存分が残っている）
```
