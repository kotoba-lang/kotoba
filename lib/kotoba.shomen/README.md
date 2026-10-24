# shomen

**書面（shomen）— 手続きがまだ紙・押印・収入印紙・出頭に縛られているとき、何に縛られ、
どの階層の法令がそう言い、電子の道が法的にどこまで開いているかを答える。純 Clojure（`.cljk`、2026-09-11 に `.cljc` から改名）、依存ゼロ。**

この repo の名前は機能を示さないので先に名乗る: **法務省所管を中心とした「analog 要件の
法的根拠」カタログと、その 1 件から「誰に何を求めるか（提言）」「電子化まで物理的に何を
するか（繋ぎ）」を決める決定核**である。提言は `cloud-itonami/teigen`、繋ぎは
`cloud-itonami/hikyaku` が、この repo の出力を入力にして動く。

| 問い | ns |
|---|---|
| analog 要件・法令階層・電子の状態の**閉じた語彙** | `shomen.vocabulary` |
| entry の**形**と適合検査（違反を全部返す） | `shomen.requirement` |
| 決定核: `route` / `advocacy` / `interim` | `shomen.classify` |
| seed カタログ（10 件、**全件 unverified-seed**） | `shomen.catalog` |
| 正直なカバレッジ報告 | `shomen.coverage` |

```bash
kbb --backend sci --classpath src:test run_tests.cljk          # 21 tests / 61 assertions
kbb --backend sci --classpath src -e '(require (quote [shomen.catalog :as c]) (quote [shomen.coverage :as v])) (print (v/report c/entries))'
```

カタログを引く・足す・確度を上げる手順（出力つき）は [`docs/operator-quickstart.md`](docs/operator-quickstart.md)。

## なぜ「収入印紙」を「書面・押印・対面」と別に数えるのか

政府の押印見直し（2020〜21）は「書面・押印・対面」の 3 分類で進み、**収入印紙はそこに
無い**。結果、申請はオンラインで出せるのに、**手数料だけが収入印紙のまま**という手続きが
残っている（seed の実例: 在留期間更新・在留資格変更 — 申請は在留申請オンラインシステム、
納付は手数料令が定める収入印紙）。書面と印紙を同じ列に入れると、この手続きは
「電子化済み」に見える。

## 決定の順序

```text
:e/status :unknown                        → :unverified         答えを拒否する
電子の道 in-force かつ analog が残らない    → :electronic-now     求めるものは無い
成立済み未施行                             → :electronic-soon    待つ。繋ぎは飛脚
法は許すが行政が用意していない              → :ask-administration 行政への要望
残る analog の最重階層が法律                → :ask-legislature    請願・規制改革要望
残る analog の最重階層が政令・省令          → :ask-ministry       意見公募・規制改革要望
残る analog の最重階層が通達・運用          → :ask-administration
```

**`:unverified` は他のどれにも畳まない。** 測っていない手続きを `:not-permitted` と
同じ値で返せば、提言 actor は調べていない法令に向けて改正要望を書く。

```clojure
(require '[shomen.catalog :as cat] '[shomen.classify :as c])

(c/route (cat/entry :jp-immigration-residence-permission-fee))
;; => :ask-ministry     ← 申請はオンライン、手数料は政令で収入印紙のまま

(c/advocacy (cat/entry :jp-immigration-residence-permission-fee))
;; => {:target :ministry :channels #{:public-comment :regulatory-reform-hotline}
;;     :remaining [:revenue-stamp]
;;     :legal-bases ["出入国管理及び難民認定法 §67（手数料）→ …手数料令（収入印紙による納付）"] …}

(c/interim (cat/entry :jp-naturalisation-application))
;; => {:delegable? false :blocked [:presence] :tasks [{:task :principal-must-act …}]}
;;    出頭が残る手続きは繋ぎ自体が成立しない。飛脚に送らず本人が行く
```

## seed 時点の所見（2026-08-23）

| route | 件 | 実例 |
|---|---|---|
| `:electronic-now` | 4 | 会社設立登記 / 登記事項証明書 / 電子定款（印紙税 4 万円が消える）/ 電子契約 |
| `:ask-ministry` | 2 | 在留資格の手数料（政令）/ 帰化の書面・出頭（省令） |
| `:ask-administration` | 1 | 出生届（戸籍法は紙と書くが、デジタル手続法 §6 が許す） |
| `:electronic-soon` | 1 | 債権差押命令申立て（令和 5 年法 53 号、未施行） |
| `:unverified` | 2 | 訴えの提起 / 公正証書 —— **施行済みかを測っていない** |

**法務省所管で「法律自身が紙・印紙を要求し電子を閉じている」手続きは seed では見つから
なかった。** 残る制約は省令・政令・運用の階層にある。だから提言の宛先の多くは国会ではなく
大臣（命令等の改正 → 意見公募）と行政機関であり、経路はパブコメと規制改革ホットラインになる。
`:ask-legislature` の実例が無いのは「無い」ではなく「見つけていない」である。

## 確度

**全件 `:unverified-seed`。** 書いた者が法令を読んで埋めたもので、第三者検証は無い。
条文番号・金額・施行日は改正で動く。`teigen` も `hikyaku` も `:unverified-seed` の entry から
live の提出・発送を起こさない（両者の governor が拒否する）。確度を上げるには entry の
`:req/confidence` を `:maintainer-verified`（一次資料で確認）か `:counsel-verified`（資格者
確認）に上げ、`:req/verified` に日付を書く。

e-Gov 法令 ID は確信のあるものだけ `:a/law-id` に書いてある。法令本文は
`kotoba-lang/jp.go.e-gov.elaws`（9,523 法令の全文 DataLad）で引ける。

## 隣接 repo との境界

- `kotoba-lang/tetsuzuki` — 一般行政手続きの**期限と審査**。shomen は手続きの**媒体**
  （紙か電子か）だけを見る。`procedure-kinds` は同じ集合を使う（依存は持たない）。
- `cloud-itonami/toritsugi` — 市民側の手続きコンシェルジュ。手続きの案内をするが、
  紙要件の階層も電子代替可否も持たない。
- `cloud-itonami/cloud-itonami-iso3166-jpn-moj` — 法務省向けコンプライアンス事業の blueprint。
- `cloud-itonami/moushibumi` — 市民本人のパブコメ・請願。**本人の声**。`teigen` は
  **事業者自身の声**で、shomen の `:ask-*` だけを入力にする。

## 決定核の置き場（follow-up）

`shomen.classify` はスカラと keyword だけで書けるので `.kotoba` の決定核に切り出せる
（`kotoba-lang/murakumo` の `*_core.kotoba` + parity test の形）。今は `.cljk` 1 実装のみで、
mirror は作らない。切り出すときは `.cljk` 側を消して KIR を実行する（ADR-2608239100 の形）。

## License

MIT
