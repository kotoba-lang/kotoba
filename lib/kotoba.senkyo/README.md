# senkyo

**選挙（senkyo）ドメインの一般ライブラリ。純 `.cljc`。**

手続きの型と期限の算法は [`tetsuzuki`](../tetsuzuki)（一般行政手続き）に
委譲しています —— 選挙だけが独自の期限算法を持つ理由が無く、持てば営業日・
暦月・徒過効果の扱いが分野ごとに分岐するためです（ADR-2608079500）。
tetsuzuki 自身は依存ゼロなので、依存は 1 本だけです。

選挙運動の手段が**その法域で適法か**、出すべき**手続きと期限**は何か、所管する
**選管はどこか** —— この 3 つを、法域を跨いで同じ形で答える。政党・陣営側
（[`cloud-itonami-isic-9492`](https://github.com/cloud-itonami/cloud-itonami-isic-9492)）と
選管・受領側
（[`cloud-itonami-isic-8411-electoral`](https://github.com/cloud-itonami/cloud-itonami-isic-8411-electoral)）が
**同じ表を読む**ための共有層である。

| 問い | ns |
|---|---|
| どんな運動手段があり、**どの普遍カテゴリ**に触れるか | `senkyo.medium` |
| **どの条文が実際に効くか**（法域別・手段別） | `senkyo.facts` |
| その手段を今この条件で**使ってよいか** | `senkyo.screen` |
| 誰が・どこへ・**いつまでに**何を出すか | `senkyo.procedure` |
| 所管の**選管はどこか**（ooyake への join） | `senkyo.authority` |
| datom 面への projection | `senkyo.datoms` |

```clojure
(require '[senkyo.screen :as screen])

(screen/screen {:iso3 "JPN" :medium :door-to-door
                :attrs {:within-campaign-period? true}})
;; => {:verdict :prohibited
;;     :blocking [{:reg-id :jp-poll-138-door-to-door ...}]
;;     :note "この法域ではこの手段を使えない。..."}

(screen/screen {:iso3 "CAN" :medium :door-to-door})
;; => {:verdict :permitted-with-obligations ...}   ← 同じ手段、逆の結論
```

## なぜこの repo が要るのか

**選挙法は法域ごとに反対を向いている。** これは「まだ実装していない差」ではなく、
実際に反対向きの法である:

| | JPN | USA | CAN |
|---|---|---|---|
| 戸別訪問 | 公職選挙法 §138 で**全面禁止**・罰則付き | 許可制を課すこと自体が違憲（Watchtower v. Stratton, 2002） | 集合住宅の管理者は候補者の訪問を**妨げてはならない**（CEA s.81） |
| 運動期間 | §129 で立候補届出後〜投票日前日に限定 | 連邦の期間制限**無し** | 事前運動の一般禁止は無い |
| ビラ | §142 で種類・枚数が法定、選管の**証紙**が要る | 連邦の枚数制限**無し**、開示で縛る | 枚数でなく支出上限で縛る |
| 候補者性 | **届出**をもって発生 | **金額**（$5,000 超）で発生 | 届出（official agent の選任が要件） |

米国の選挙運動の常識で日本の運動計画を立てると**犯罪になる**。逆に日本の常識で
カナダの戸別訪問を「できない」と答えるのも誤りである。LLM に手段を選ばせる前に、
**必ず法域を経由させる**ための表がこの repo である。

## 3 つの規律

**1. カバレッジは正直に。** 収録は JPN / USA / GBR / DEU / CAN の 5 法域・
31 instrument・14 手続き。`coverage` は収録数だけでなく、**人口 1 億超で未収録の
12 法域を名指しで**返す。ここに無い法域は spec-basis が「無い」のであって、
「規制が無い」ではない。

```clojure
(senkyo.facts/coverage)
;; => {:jurisdictions ["CAN" "DEU" "GBR" "JPN" "USA"] :count 5 :instruments 31
;;     :uncovered-large ["IND (India, 1428M)" "CHN (China, 1425M)" ...]}
```

**2. 不明を『不要』に倒さない。** verdict は 5 値で、属性が足りなければ
`:undetermined` のまま残る。`:permitted` は既定値ではない。

```
:no-spec-basis  その法域のカタログが無い（「規制が無い」ではない）
:prohibited     その手段自体が禁じられている
:undetermined   決まらない項目が残っている ← :permitted に倒さない
:permitted-with-obligations  使えるが義務と証跡がある
:permitted      義務も未決も無い（実際にはほとんど出ない）
```

`:local`（国レベルで決まらず自治体・州が決める）は `:unknown` として残る。
米国の掲示物規制・ドイツの Sondernutzungserlaubnis がこれで、**国の表では
答えが出ないことを答えとして返す**。

**3. 条文番号の確度を持ち歩く。** `:reg/confidence` が `:high` のものは条文番号
まで確度が高い。`:medium` は法律レベルでは正しいが項番号が改正で動きうる。
`:require-high-confidence?` を渡すと `:medium` は**除外されず `:deferred` 枠に出る**
—— 除外すると「その義務は無い」と読めてしまうため。

## 構造的に持たない語彙（compliance-first の境界）

`senkyo.screen/out-of-scope-intents` は**この repo と消費側 actor が設計として
持たない意図**を閉じた集合で宣言する。「未実装」ではない。

```clojure
#{:voter-targeting          ; 有権者個人・世帯の選別・名簿化
  :vote-persuasion-script   ; 投票行動を変えさせる話法・台本
  :candidate-ranking        ; 候補者・政党の優劣評価
  :turnout-operation        ; 個人単位で投票する/しないを動かす運用
  :distribution-dispatch    ; 配布・貼付・訪問の実行指揮
  :opinion-profiling        ; 政治的信条のプロファイリング
  :eligibility-adjudication}; 被選挙権・有効投票・当落の裁定
```

これを含む screen 要求は `:out-of-scope` で止まり、findings を返さない。
**境界を各 actor に書くと actor の数だけ文言が分岐する**ので、1 か所で定義して
全 consumer が同じ集合を参照する。

## ooyake への join —— 統合の現在地を両方向で数える

`senkyo.authority` は所管当局を
[`ooyake`](https://github.com/kotoba-lang/ooyake)（World Government Atlas）の
`:gov.unit` へ join する。ただし **ooyake が完全であることに依存しない** ——
当局名・根拠法は `senkyo.facts` が一次情報として持ち、`gov.<iso3>.electoral` は
任意の join key として重ねるだけ。

```clojure
(senkyo.authority/join-report ooyake-units)
;; => {:joined ["GBR" "USA"]
;;     :senkyo-only ["CAN" "DEU" "JPN"]   ← 規制はあるが atlas に選管が無い
;;     :atlas-only [...61 法域...]         ← 選管はあるが規制カタログが無い
;;     :note "...join できた数だけを報告するのは嘘になる。"}
```

**実測（2026-08-07）**: ooyake の electoral registry は 63 の選挙管理機関を
持つが、**JPN・DEU・CAN は入っていない**（USA・GBR は在る）。逆に 63 件のうち
61 件は senkyo に規制カタログが無い。`join-report` はこの**両方の穴**を返す。
片方向だけ数えれば統合されているように読めてしまう。

## 期限は日付でなく『基準点 + オフセット』

選挙の日付は選挙ごとに違うので絶対日付を持たない。日付ライブラリにも依存しない
（epoch-day の整数で受け渡す）。

```clojure
(senkyo.procedure/schedule "JPN" {:poll-day 20500 :announcement-day 20488})
;; => [{:id :jp-candidacy-filing :due 20488 :received-by :election-commission ...}
;;     {:id :jp-expense-return   :due 20515 :confidence :medium ...} ...]

(senkyo.procedure/unresolved sched)   ; ← これを空にしてから「期限管理できている」と言う
```

解けなかった行は**落とさずに残す**（落とすと「期限が無い」と読める）。
`:unknown-anchor` は「期限なし」ではなく「基準日を知らない」である。

## この repo が意図的に持たないもの

- **有権者データ。** 名簿・世帯・支持傾向のいかなる表現も持たない。
- **実行指揮。** 誰がどの区域を回るか、いつ貼るかは扱わない。
- **政策の当否。** 主張の内容・優劣は評価しない。
- **法的助言。** これは表であって助言ではない。拘束力のある判断の前に
  `:reg/source-urls` の原文と、当該選挙の選管資料に当たること。
- **観測の収集。** 掲示場の位置などの実地データは持たない。物理的な屋外掲出物
  一般は [`okugai`](../okugai) / [`denchu`](../denchu) の領分で、**選挙運動用
  文書図画はそれとは別系統の規制**（適用除外を受ける場合がある）。

## 出典と鮮度

各 instrument は `:reg/source-urls` に公式の一次情報（e-Gov 法令検索・FEC・
legislation.gov.uk・gesetze-im-internet.de・Justice Laws Canada）を、
`:reg/verified` に最終確認日を持つ。**選挙法は改正が頻繁で、この表は必ず古くなる。**

```bash
kbb --backend sci --classpath src:test:../tetsuzuki/src run_tests.cljk    # 35 tests / 327 assertions
```

MIT License.
