# operator quickstart

**この表から「その手続きの期限はいつか」を実際に引き出すまでの手順。**
全コマンドは実行して出力を確認したもので、貼れば同じ答えが出る。

このライブラリの主張は「解けないことを解けたことにしない」なので、**この
quickstart の山場は step 4（答えを拒む 7 通り）である**。step 1〜3 だけ読んで
組み込むと、拒否を答えとして扱うコードが書ける。

---

## 0. 前提

依存ゼロの純 `.cljc`。要るのは `nbb` だけで、JVM も npm install も要らない。

```bash
# superproject から取る場合（west project 名は tetsuzuki）
west update --fetch smart tetsuzuki
cd orgs/kotoba-lang/tetsuzuki

kbb --backend sci --classpath src:test run_tests.cljk
```

```
Testing tetsuzuki.catalog-test

Testing tetsuzuki.deadline-test

Testing tetsuzuki.review-test

Ran 34 tests containing 198 assertions.
0 failures, 0 errors.

PASS — 34 tests, 198 assertions, 0 failures, 0 errors
```

これが通らないなら以降の答えを信用しない。以降のコマンドは repo ルートから
`--classpath src` で走らせる。

---

## 1. その手続きは表に在るか

**創作しないための最初の 1 手。** 表に無いものは無いと答える。

```bash
kbb --backend sci --classpath src -e '
(require (quote [tetsuzuki.catalog :as c]) (quote [tetsuzuki.procedure :as p]))
(doseq [j (sort (keys c/procedures))]
  (println j (vec (sort (keys (c/for-jurisdiction j))))))
(println)
(println (p/summary-line c/procedures))'
```

```
CAN [:ca-atip-extension :ca-atip-request :ca-judicial-review]
DEU [:de-genehmigungsfiktion :de-ifg-antrag :de-widerspruch]
GBR [:gb-foi-internal-review :gb-foi-request :gb-judicial-review]
JPN [:jp-joho-kokai :jp-public-comment :jp-shinsa-seikyu :jp-shinsei-shobun :jp-todokede]
USA [:us-foia-appeal :us-foia-request :us-license-application :us-notice-and-comment]

5 法域 / 18 手続き、うち 4 件は confidence が :high でない
```

`(c/procedure "XXX" :whatever)` は表に無ければ `nil` を返す。**`nil` を
「期限なし」に丸めない** —— それは step 4 の `:no-basis` であって
`:no-deadline` ではない。

---

## 2. 期限はいつか

epoch-day（1970-01-01 = 0）の整数で入れて、整数で受け取る。

```bash
kbb --backend sci --classpath src -e '
(require (quote [tetsuzuki.catalog :as c]) (quote [tetsuzuki.deadline :as d]))
(let [p (c/procedure "USA" :us-foia-request)
      ctx {:anchors {:filing-received 20460}}]
  (println (d/describe p))
  (println :deadline (d/resolve-deadline (:proc/deadline p) ctx))
  (println :status (d/status (:proc/deadline p) ctx 20495))
  (println :lapse (d/lapse-consequence p ctx 20495)))'
```

```
authority を縛る / 20 business-days after filing-received
:deadline 20488
:status :lapsed
:lapse :exhausts-remedy
```

### 暦日で数えると 8 日早い

上の例は 2026-01-07（epoch-day 20460）受理。米 FOIA は 20 **business days**
なので期限は **20488 = 2026-02-04**。暦日で 20 を足すと 20480 = 2026-01-27 で、
**8 日早い**。

```bash
kbb --backend sci --classpath src -e '
(require (quote [tetsuzuki.catalog :as c]) (quote [tetsuzuki.deadline :as d]))
(let [dl (:proc/deadline (c/procedure "USA" :us-foia-request))
      ctx {:anchors {:filing-received 20460}}]
  (println :business-days (d/resolve-deadline dl ctx))
  (println :naive-calendar (+ 20460 20))
  (println :status-on-20480 (d/status dl ctx 20480)))'
```

```
:business-days 20488
:naive-calendar 20480
:status-on-20480 :within
```

2026-01-27 時点で行政庁は**まだ遅れていない**。暦日で実装すると、この日に
遅延として扱う。

### 祝日は入っていない

既定カレンダーは**土日だけ**を休みにする。祝日は法域ごとに違うのでこの repo は
持たない。祝日を渡さない答えは**祝日ぶん早い**。

```bash
kbb --backend sci --classpath src -e '
(require (quote [tetsuzuki.catalog :as c]) (quote [tetsuzuki.deadline :as d]))
(let [dl (:proc/deadline (c/procedure "USA" :us-foia-request))
      ctx {:anchors {:filing-received 20460}}]
  (println :weekends-only (d/resolve-deadline dl ctx))
  (println :with-mlk (d/resolve-deadline dl (assoc ctx :calendar {:weekend #{2 3}
                                                                 :holidays #{20472}}))))'
```

```
:weekends-only 20488
:with-mlk 20489
```

20472 = 2026-01-19（Martin Luther King, Jr. Day）。窓の中にある祝日 1 日ぶん
期限が 1 日延びる。**拘束力のある期限管理をするなら `:holidays` を渡す。**

---

## 3. 遅れたら何が起きるか

`lapse-consequence` は**徒過して初めて**効果を返す。まだ期限内なら `nil`。

```bash
kbb --backend sci --classpath src -e '
(require (quote [tetsuzuki.coverage :as cov]))
(doseq [l (:lines (cov/contrast))] (println l))'
```

```
deemed-granted: DEU/de-genehmigungsfiktion
deemed-refused: CAN/ca-atip-extension, CAN/ca-atip-request
exhausts-remedy: GBR/gb-foi-request, JPN/jp-joho-kokai, USA/us-foia-appeal, USA/us-foia-request
forfeits-right: CAN/ca-judicial-review, DEU/de-widerspruch, GBR/gb-judicial-review, JPN/jp-shinsa-seikyu
none: GBR/gb-foi-internal-review, JPN/jp-public-comment, JPN/jp-shinsei-shobun, JPN/jp-todokede, USA/us-license-application, USA/us-notice-and-comment
unknown: DEU/de-ifg-antrag
```

**同じ「行政庁が答えなかった」に、ドイツは許可を、カナダは拒否を与える。**
効果を持たない設計ではこの 2 つが同じ「期限を過ぎた」に潰れる。

---

## 4. 答えないとき —— 7 通りの拒否

**ここが本体。** `resolve-deadline` / `status` の戻り値は整数か、
`d/unresolved-reasons` の 7 つのいずれか。**整数以外を「期限内」に丸めない。**

```bash
kbb --backend sci --classpath src -e '
(require (quote [tetsuzuki.catalog :as c]) (quote [tetsuzuki.deadline :as d]))
(println :count (count d/unresolved-reasons))
(println :reasons (vec (sort d/unresolved-reasons)))
(println)
(doseq [[j id ctx] [["JPN" :jp-todokede        {:anchors {:filing-received 20460}}]
                    ["JPN" :jp-shinsei-shobun  {:anchors {:filing-received 20460}}]
                    ["DEU" :de-widerspruch     {:anchors {:filing-received 20460}}]
                    ["JPN" :jp-shinsa-seikyu   {:anchors {:disposition-known 20460}}]
                    ["GBR" :gb-foi-request     {:anchors {:filing-received 20460} :calendar nil}]
                    ["USA" :us-foia-request    {:anchors {}}]]]
  (println (str j "/" (name id)) "->"
           (d/resolve-deadline (:proc/deadline (c/procedure j id)) ctx)))'
```

```
:count 7
:reasons [:authority-published :needs-business-calendar :needs-calendar-date :no-basis :no-deadline :unknown-anchor :unknown-unit]

JPN/jp-todokede -> :no-deadline
JPN/jp-shinsei-shobun -> :authority-published
DEU/de-widerspruch -> :unknown-anchor
JPN/jp-shinsa-seikyu -> :needs-calendar-date
GBR/gb-foi-request -> :needs-business-calendar
USA/us-foia-request -> :unknown-anchor
```

| 戻り値 | 意味 | 打つ手 |
|---|---|---|
| 整数 | 解けた（epoch-day） | — |
| `:no-deadline` | 期限の定めが無い（調べた結果） | 無し。**期限管理の対象から外す** |
| `:authority-published` | 数値は各行政庁が定めて公表する | 当該庁の公表を見る。**`:no-deadline` に丸めない** |
| `:unknown-anchor` | 基準日が渡されていない | その手続きが要る `:anchor` を `:anchors` に入れる |
| `:needs-business-calendar` | 営業日単位だがカレンダーが nil | `:calendar` を渡す |
| `:needs-calendar-date` | **月**単位。epoch-day では解けない | 実日付で計算する。**30 日で近似しない** |
| `:unknown-unit` | 語彙外の `:unit` | 表の側の欠陥。`valid-deadline?` で先に弾く |
| `:no-basis` | 手続きが表に無い | 表に足す（**要件を創作しない**） |

`:needs-calendar-date` は珍しい話ではない —— **18 手続きのうち 5 件が月単位**
（不服申立期間）で、そこは epoch-day では答えが出ない。

```bash
kbb --backend sci --classpath src -e '
(require (quote [tetsuzuki.coverage :as cov]))
(println :units (cov/units-in-use))
(println :binds (cov/who-is-bound))'
```

```
:units {:calendar-days 5, :months 5, :business-days 2, :working-days 1}
:binds {:authority 13, :filer 4}
```

**`case` を 6 分岐で書かない。** 上の 7 つ全部に分岐を書くか、`(integer? r)` で
先に振り分けて残りを 1 箇所で受ける。

---

## 5. 書類は揃っているか（形式審査）

形式審査は「記載事項が埋まっているか」であって「許可してよいか」ではない。
**実質判断はこの層が扱わない。**

```bash
kbb --backend sci --classpath src -e '
(require (quote [tetsuzuki.catalog :as c]) (quote [tetsuzuki.review :as r]))
(let [p (c/procedure "USA" :us-foia-request)]
  (println :items (:proc/formal-review p))
  (println :empty (r/outcome p []))
  (println :outstanding (r/outstanding p []))
  (println :all (r/outcome p (:proc/formal-review p))))
(println :todokede (r/outcome (c/procedure "JPN" :jp-todokede) []))
(println :unknown-blocks? (r/blocking? (r/outcome nil [])))
(println :unknown-complete? (r/complete? nil []))'
```

```
:items [reasonable description of records fee agreement proper component received the request]
:empty :deficient
:outstanding [reasonable description of records fee agreement proper component received the request]
:all :complete
:todokede :not-reviewable
:unknown-blocks? true
:unknown-complete? nil
```

3 つとも意図的な形:

- **届出は `:not-reviewable`。** 日本の行政手続法 §37 は届出が到達した時点で
  義務が履行されたものとする。行政庁に諾否の余地が無いので、申請と同じ
  完了判定を当ててはならない。
- **`complete?` は `:unknown` に `nil` を返す**（`false` ではない）。「未充足」と
  「判定できない」を同じ偽値にすると、知らないことが不備として通知される。
- **`blocking?` は `:unknown` を止める。** 知らないまま次へ進めない。

---

## 6. 表を信じる前に

```bash
kbb --backend sci --classpath src -e '
(require (quote [tetsuzuki.catalog :as c]) (quote [tetsuzuki.procedure :as p])
         (quote [tetsuzuki.coverage :as cov]))
(println (p/conform-report c/procedures :core))
(println (p/conform-report c/procedures :full))
(println :needs-source-check (:needs-source-check (cov/report)))
(println :uncovered-large (count (:uncovered-large (cov/report))))'
```

```
OK  core 適合 — 18 手続き / 違反 0 件
OK  full 適合 — 18 手続き / 違反 0 件
:needs-source-check [CAN/ca-atip-extension CAN/ca-judicial-review DEU/de-ifg-antrag GBR/gb-foi-internal-review]
:uncovered-large 12
```

`:needs-source-check` の 4 件は `:proc/confidence` が `:high` でない ——
**適合はしているが原文確認が済んでいない。** 拘束力のある期限管理に使う前に
`:proc/source-urls` を引く。

`:uncovered-large` の 12 は人口 1 億超で未収録の法域。**未収録は「手続きが
無い」ではなく spec-basis が無いという意味**で、要件を創作して埋めてはならない。

---

## 7. ooyake の seed を写す（昇格させない）

`kotoba-lang/ooyake` の手続き seed は**全件が `:unverified-seed`** で、期限も
徒過効果も形式審査項目も持たない。写せるが、写しただけでは適合しない。

**この step だけ `kotoba-lang/ooyake` の checkout が要る**（他は依存ゼロ）。

```bash
# 既定は sibling（superproject の orgs/kotoba-lang/ooyake）。別の場所なら OOYAKE= で渡す
OOYAKE=../ooyake/registry kbb --backend sci --classpath src -e '
(require (quote [tetsuzuki.ooyake :as o]) (quote [clojure.edn :as edn]) (quote ["fs" :as fs]))
(def base (str (or js/process.env.OOYAKE "../ooyake/registry") "/"))
(def seeds (vec (mapcat (fn [f] (:procedures (edn/read-string (fs/readFileSync (str base f) "utf8"))))
                        ["gov-units.toritsugi-procedures.seed.edn"
                         "gov-units.intl-procedures.seed.edn"
                         "gov-units.seed.edn"])))
(def r (o/promotion-report seeds))
(println :seeds (count seeds))
(println :jurisdictions (count (:jurisdictions r)))
(println :verification-status (:verification-status r))
(println :core-violations (:core-violations r))
(println :missing-fields (:missing-fields r))
(println :promotable (count (filter #(o/promotable? % {:legal-basis "x"}) seeds)))'
```

```
:seeds 157
:jurisdictions 50
:verification-status {:unverified-seed 157}
:core-violations 471
:missing-fields [:proc/confidence :proc/deadline :proc/formal-review :proc/kind :proc/lapse-effect]
:promotable 0
```

**471 件の違反は不具合ではなく現在地。** 昇格の唯一の経路は条文を確認して
`tetsuzuki.catalog` へ書くことで、`promotable?` は検証済みかつ根拠法が判明して
いる seed しか通さない —— 今日その条件を満たす seed は **0 件**である。

> ⚠ **seed を数えるのに `grep -c ':gov.procedure/id'` を使わない。**
> `gov-units.seed.edn` はその属性を `:schema-tx` の中でも 1 度宣言している
> （30 行目、`:db/ident :gov.procedure/id`）ので、grep は **158** を返すが
> 実際の seed は **157** 件である。EDN を読んで `:procedures` を数える。

---

## この quickstart が答えないこと

- **許可を与えてよいか。** 実質判断はこの repo の外。
- **実日付。** 扱うのは epoch-day の整数だけで、月の加算は解かずに返す。
- **祝日。** 呼び出し側が `:holidays` で渡す。
- **分野固有の手続き。** ここに在るのは行政手続法制の一般層だけ。選挙は
  [`kotoba-lang/senkyo`](https://github.com/kotoba-lang/senkyo)。
- **法的助言。** これは表であって助言ではない。拘束力のある期限管理の前に
  `:proc/source-urls` の原文へ当たること。
