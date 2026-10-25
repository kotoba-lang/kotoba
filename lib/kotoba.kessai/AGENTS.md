# kessai — rail 非依存の決済ゲートウェイ抽象（純粋データ契約）

**Status: R2**

ISIC 縦割りの actor（信用・証券・保険…）が、actor ごとに決済統合を書く代わりに
1 つの port を持つための capability library。ネットワーク・I/O・時計なし。
金額は取引通貨の**最小単位の整数**（BigDecimal を前提にしない = `.cljc` として
JVM / cljs / SCI / GraalVM で可搬）。

## 3 つの rail と、それぞれの形

| rail | 実体 | 形 |
|---|---|---|
| `:card` | ISO 8583（`kessai.card` → `kotoba.card`） | authorize → capture / void / refund |
| `:wire` | ISO 20022 pain.001 + BIC（`kessai.wire` → `kotoba.banking`） | authorize → capture / refund |
| **`:redirect`** | **PSP ホスト型 checkout（Stripe Checkout / PayPal / Adyen HPP）** | **session → redirect → webhook 確定** |

**`IPaymentPort` は全 rail を覆っていない。それは意図的。** `:redirect` は
`kessai.redirect` に独自のライフサイクルを持ち、確定したときだけ
`redirect/->payment-ref` で PaymentRef に射影する（既存の台帳結線
`settlement-entries` はそのまま動く）。

### なぜ `:card` に押し込まないか

hosted redirect では **merchant は instrument を一度も持たず、authorization を
発行せず、capture もできない**。session を作り、payer を送り出し、あとから結果を
*知る*だけ。authorize/capture は card-present 由来の 2 段モデルで、リダイレクト
決済にはその 2 段が存在しない —— 押し込むと「誰も実装できない capture」が残り、
台帳がそれを待ち続ける。

この不一致が原因で、murakumo.cloud の物販は kessai を経由せず Stripe Checkout を
直接呼んだ（com-junkawasaki/root ADR-2608040100）。`:redirect` rail はその穴を
塞ぐために足した。

## `:redirect` を触るときに壊してはいけない不変条件

- **戻り URL は支払いの証拠ではない。** `observe-return` は**構造上 `:succeeded`
  に到達できない** —— どんな引数を渡しても settle しない。payer は URL を
  書き換えられるし、払わずに到達もできるし、はるかに多くは**払ってからタブを
  閉じて戻ってこない**。`confirm`（webhook）だけが唯一の門。
- **`confirm` は金額と通貨を session と照合する。** 改竄されたクライアント・
  使い回された session id・通貨換算の取り違えを捕まえる唯一の場所で、
  **happy path では一度も通らないので最も省略されやすい。**
- **`confirm` は event id で冪等。** PSP は同じ event を再送する仕様なので、
  これは「起きるかもしれない」ではなく必ず起きる。
- **`confirm` は例外を投げない。** webhook ハンドラが投げると 5xx になり、PSP は
  同じ壊れた event を永久に再送する。`{:error reason}` を返す。
- **終端状態は復活しない。** 期限切れ後に遅れて届いた `succeeded` は履行できる
  支払いではない（商品は解放されたか価格が動いている）。
- **時計を読まない。** `expire-if-due` は `now` を呼び出し側から受け取る ——
  「期限切れ」は常に呼び出し側の判断を明示したもので、裏で起きることではない。

## 成熟度の梯子（この repo における R-tier の意味）

| tier | 意味 | 現在地 |
|---|---|---|
| R0 | 契約のスケッチのみ | — |
| R1 | 純粋な契約 + テスト | — |
| **R2** | **ドメイン契約が揃い test / lint / CI 緑。git 座標で消費可能。本番の消費者で未実証** | **← いまここ** |
| R3 | 実際の消費者が本番でこれを叩いている | 未達 |
| R4 | 本番負荷で実証され運用記録がある | 未達 |
| R5 | API 安定 + 廃止手順あり | 未達 |

**R3 の不足**: `:redirect` の契約は揃ったが、これを実際に叩く消費者がまだ無い。
最短の候補は murakumo.cloud の storefront（現在は Stripe Checkout を直接呼んで
いる）を `kessai.redirect` 経由に寄せること —— ただし ADR-2608040100 のとおり
本番稼働中の経路なので、置き換えは動いているものを壊さない順序で行う。
`:card` / `:wire` 側も同様に実決済の消費者が無い。

## 検証

```bash
kbb -M:test   # 21 tests / 139 assertions
kbb -M:lint   # errors 0 / warnings 0
```
