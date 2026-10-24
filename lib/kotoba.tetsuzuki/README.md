# tetsuzuki

**一般行政手続き（手続き）の型と算法。純 `.cljc`、依存ゼロ。**

「その手続きは誰を、いつまで縛るのか。期限を過ぎたら**何が起きるのか**」を、
法域を跨いで同じ形で答える。分野固有の手続き（選挙は
[`senkyo`](../senkyo)）はこの形に載る側であって、この repo の中身ではない。

| 問い | ns |
|---|---|
| 手続きを法域跨ぎで書くための**閉じた語彙** | `tetsuzuki.vocabulary` |
| 期限の算法（誰を縛る・何日単位・徒過効果） | `tetsuzuki.deadline` |
| entry の**形**と、その形への適合検査 | `tetsuzuki.procedure` |
| 形式審査（書類が揃っているか） | `tetsuzuki.review` |
| 5 法域の一般行政手続きカタログ | `tetsuzuki.catalog` |
| `ooyake` の手続き seed を写すアダプタ | `tetsuzuki.ooyake` |
| 正直なカバレッジ報告 | `tetsuzuki.coverage` |

## なぜ「期限」に効果が要るのか

**同じ「行政庁が期限内に応答しなかった」に、法域は正反対の効果を与える。**

| 徒過効果 | 実例 |
|---|---|
| `:deemed-granted` | **DEU** VwVfG §42a — 期間内に決定しなければ**許可されたものとみなす** |
| `:deemed-refused` | **CAN** ATIA s.10(3) — 期限内に開示しなければ**拒否したものとみなす** |
| `:exhausts-remedy` | **USA** FOIA §552(a)(6)(C) / **GBR** FOIA s.50 — 救済を尽くしたものとして次へ進める |
| `:none` | **JPN** 行政手続法 §6 標準処理期間 — **自動的な法的効果は無い** |
| `:forfeits-right` | 各法域の不服申立期間 — 徒過すれば争えなくなる |

ドイツとカナダは同じ沈黙に**許可**と**拒否**を与えています。期限に効果を
持たせない設計では、この 4 つが同じ「期限を過ぎた」に潰れ、許可を拒否と、
拒否を許可と取り違えます。

```clojure
(require '[tetsuzuki.deadline :as d] '[tetsuzuki.catalog :as c])

(d/lapse-consequence (c/procedure "CAN" :ca-atip-request)
                     {:anchors {:filing-received 20460}} 20500)
;; => :deemed-refused          ← 30 日を過ぎた

(d/lapse-consequence (c/procedure "CAN" :ca-atip-request)
                     {:anchors {:filing-received 20460}} 20470)
;; => nil                      ← 効果は徒過して初めて生じる
```

## `senkyo` から一般化した 3 点

`kotoba-lang/senkyo`（選挙）は同じ形で手続きを書きましたが、選挙では要らず
一般行政では要るものが 3 つありました。

**1. 期限が誰を縛るのか（`:binds`）。** 選挙の手続きは**全部が提出側**を
縛る期限でした。一般行政では行政庁を縛る期限が主役です:

```clojure
(tetsuzuki.coverage/who-is-bound)   ;; => {:authority 13, :filer 4}
```

**2. 日の単位（`:unit`）。** 選挙は暦日で足りました。米 FOIA は 20
**business days**、英 FOIA は 20 **working days**、独英日の不服申立ては **月**。

暦日 20 日として計算すると実際の期限より約 8 日早い日を返し、**遅れていない
行政庁を遅れていると判定します**。休日カレンダーが無いなら近似せず止まります:

```clojure
(d/resolve-deadline (:proc/deadline (c/procedure "GBR" :gb-foi-request))
                    {:anchors {:filing-received 20460} :calendar nil})
;; => :needs-business-calendar     ← 暦日に落とさない
```

**月**も同様に epoch-day では解けないので `:needs-calendar-date` を返します
（1 か月を 30 日で近似しません）。

**3. 徒過効果（`:lapse-effect`）。** 上記のとおり。

## 解けないことを解けたことにしない

`resolve-deadline` の戻り値は整数か、`unresolved-reasons` の **7 つ**の
いずれかで、**それぞれ別の理由で**解けていません。

| 戻り値 | 意味 | 打つ手 |
|---|---|---|
| 整数 | 解けた | — |
| `:no-deadline` | 期限の定めが無い（調べた結果） | 無し |
| `:authority-published` | 数値は**各行政庁が定めて公表する** | 当該庁の公表を見る |
| `:unknown-anchor` | 基準日が与えられていない | 基準日を渡す |
| `:needs-business-calendar` | 営業日単位だがカレンダーが無い | カレンダーを渡す |
| `:needs-calendar-date` | **月**単位。epoch-day では解けない | 実日付で計算する（30 日で近似しない） |
| `:unknown-unit` | 語彙外の `:unit` | 表の側の欠陥。`valid-deadline?` で先に弾く |
| `:no-basis` | 手続きが表に無い | 表に足す（**創作しない**） |

**`case` を 6 分岐で書かないでください。** `:needs-calendar-date` は珍しい話では
なく、**18 手続きのうち 5 件が月単位**（不服申立期間）です。分岐を落とすと、
争える期間が残っているのに「解けた」として扱われます。分岐の網羅は
`d/unresolved-reasons` を数えれば確認できます。

`:authority-published` を `:no-deadline` に丸めると、「各庁が公表している
はずの数値をこの表が持っていない」が「期限が無い」に化けます。日本の標準
処理期間（行政手続法 §6）と米 APA §558(c) の "reasonable time" がここです。

## 届出は申請ではない

日本の行政手続法 §37 は、届出が到達したときに手続上の義務が履行されたものと
定めます。**行政庁に諾否の余地がありません。** 申請と同じ受領モデルで扱うと、
行政庁が審査できるかのように書けてしまうので、型で止めています:

```clojure
(review/outcome (c/procedure "JPN" :jp-todokede) [])   ;; => :not-reviewable
```

## `ooyake` の seed は写すが、昇格させない

[`ooyake`](../ooyake) は手続き seed を 157 件持ちますが、**全件が
`:unverified-seed`** で、期限も徒過効果も形式審査項目も持ちません（実測
2026-09-03）。`tetsuzuki.ooyake` はこれを**写します**が、写しただけで適合
させません。3 つの registry の `:procedures` を全件読ませた実測:

```clojure
(ooyake/promotion-report seeds)
;; => {:procedures 157
;;     :verification-status {:unverified-seed 157}
;;     :core-violations 471
;;     :missing-fields [:proc/confidence :proc/deadline :proc/formal-review
;;                      :proc/kind :proc/lapse-effect]
;;     :note "...昇格の唯一の経路は条文を確認して tetsuzuki.catalog へ書くこと..."}
```

> ⚠ **seed を数えるのに `grep -c ':gov.procedure/id'` を使わないこと。**
> `gov-units.seed.edn` はその属性を `:schema-tx` の中でも 1 度宣言している
> （30 行目、`:db/ident :gov.procedure/id`）ので、grep は **158** を返しますが
> 実際の seed は **157** 件です。EDN を読んで `:procedures` を数えてください。
> 手順は [`docs/operator-quickstart.md`](docs/operator-quickstart.md) の step 7。

`core` 適合検査に**通らないことが正しい状態**です。「取り込んだから使える」
という嘘をつかないための設計で、昇格には検証済みであることと根拠法が判明して
いることの両方が要ります（`promotable?`）。

## 2 段階の適合

- **`core`** — 名前・根拠法・確度・形式審査項目・期限が縛る相手。行政手続きの
  カタログを名乗るなら最低限。
- **`full`** — さらに種類・徒過効果・出典 URL・確認日。

```clojure
(procedure/conform-report catalog/procedures :full)
;; => "OK  full 適合 — 18 手続き / 違反 0 件"
```

`conform` は**違反を全部返します**（最初の 1 件で止めません）。1 件ずつ
直させると直す側が全体像を持てないためです。

## カバレッジ（正直に）

収録は **5 法域 / 18 手続き**（JPN / USA / GBR / DEU / CAN）。`coverage/report`
は収録数だけでなく、`:proc/confidence` が `:high` でない手続きを名指しし、
人口 1 億超で未収録の 12 法域を返します。

**未収録は「手続きが無い」ではなく spec-basis 無しです。** 要件を創作しては
なりません。この表が持つのは行政手続法制の一般層だけで、分野固有の手続きは
別カタログにあります。

## この repo が意図的に持たないもの

- **実質判断。** 許可を与えてよいか、この人に資格があるかは扱いません。
- **祝日データ。** 法域ごとに違い、持てば必ず古くなります。カレンダーは
  呼び出し側が渡します（既定は土日のみで、**祝日ぶん早い日**を返しうる）。
- **暦日付演算。** epoch-day の整数だけを扱い、月の加算は解かずに返します。
- **法的助言。** これは表であって助言ではありません。拘束力のある期限管理の
  前に `:proc/source-urls` の原文へ当たること。

```bash
kbb --backend sci --classpath src:test run_tests.cljk    # 34 tests / 198 assertions
```

**この表から実際に期限を引き出すまでの手順は
[`docs/operator-quickstart.md`](docs/operator-quickstart.md)。** 全コマンドを
実行して出力を確認したもので、山場は step 4（答えを拒む 7 通り）です。

MIT License.
