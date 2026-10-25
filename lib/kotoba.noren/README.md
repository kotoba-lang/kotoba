# noren

**暖簾（のれん）—— 店が外に掛けている面のこと。この repo は、事業者の公開面を
「測る・処方する・建てる」判断そのもの**を持つ純 `.cljc` ライブラリである。
名前が機能を示さないので最初に名乗る（superproject `AGENTS.md` の規約）。

I/O は 1 バイトも無い。取得も送信も課金もしない —— それを回すのは
[`cloud-itonami/loop-noren`](https://github.com/cloud-itonami/loop-noren) で、
この repo は `loop-*` が持ってはいけない **domain scoring truth** の側にあたる
（`manifest/repository-rules.edn`、ADR-2607299000）。

設計: superproject **ADR-2608111400**。

## 何を持っていて、何を持っていないか

| ns | 答える問い |
|---|---|
| `noren.discovery` | この事業者を名簿に載せてよいか（OSM タグ → 業種 / LLM 抽出の原文照合 / DiscoveryGovernor） |
| `noren.prospect` | この事業者に、いま接触してよいか（業種 gate / 特定電子メール法 3 条 1 項 4 号の形 / 観測の鮮度） |
| `noren.diagnose` | その公開面は、店の仕事をどれだけ引き受けられているか |
| `noren.prescribe` | 直すのか建て替えるのか。**測った軸だけで**何を言えるか |
| `noren.governor` | その提案を外へ出してよいか（HARD 11 / SOFT 2） |
| `noren.build` | 貰った事実だけで面を建てる |
| `noren.plan` | 月額いくらで、何が付いていて、今日その capability を使ってよいか |

**UI 品質は測り直していない。** `kotoba-lang/design-quality` が HIG/WCAG の
12 軸を持っているので、`noren.diagnose` は同じ `{:id :title :weight :check}` の
形で presence 軸を足すだけで、重み正規化も finding 収集も機構ごと借りる。

## 発見に LLM を使うときの 2 つの分離（`noren.discovery`）

発見を自動化すると「ホスト名から業種を推測して売る」に落ちる。その推測を消すのが
この名前空間で、解き方は 2 つの分離である。

**1. 業種は OSM のタグから決める。** `amenity=restaurant` は誰かが現地を見て付けた
宣言で、こちらの推測ではない。タグ → ISIC は `osm-tag->isic` に**表として**書いて
あり導出しない。証拠は OSM の element id で、第三者が
`https://www.openstreetmap.org/node/…` を開いて確かめられる。チェーン店舗
（`brand:wikidata` 等）は candidate にしない —— `website` が本部を指すため
（実測 2026-08-11、神楽坂 387 件中 19 件）。

**2. LLM は抽出しかしない。判定しない。** murakumo-main が読むのは相手のページ本文で、
返してよいのは**本文にそのまま在る文字列**（店名・アドレス・その周辺の一文・受信拒否の
文言）だけ。`verify-extraction` が 1 つずつ原文に照合し、**verbatim で見つからない主張は
落とす**。落とした値は捨てず `:dropped` に残す（モデルを替えたとき、抽出が良くなったのか
照合が緩んだのかを区別するため）。

したがって**発見の健全性はモデルの性能に依存しない** —— 依存しているのは照合であって
推論ではない。モデルの判断に属する項目（`:kind` / `:own-site?` / `:confidence`）だけは
照合できないので、DiscoveryGovernor が閾値と HARD rule で受け止める。

## 3 つの規律

**1. 測っていないことは言えない。** `:claims` は 1 文につき 1 つの軸 id を
背負い、governor はその軸が `:evidence` に無ければ `:hold` にする。文面を
LLM に書かせても、LLM が触れるのは claim の並べ方だけで claim は増やせない。

**2. 貰っていない事実は書かない。** 営業時間も電話も住所もメニューも、brief に
無ければ節ごと出さず `:missing` に積む。診断で `:hours` が落ちた店に、想像した
営業時間の載ったサイトを見せるのは提案ではなく事故である。

**3. 建てた面は自分の基準を通る。** 相手のサイトを採点する側が、自分の出す面を
採点していなければ話にならない。テストが `build → diagnose` を実際に通し、
presence ≥ 90 / UI ≥ 80 / `:healthy` を要求する（`app-css` を空にすると
`:repairable` に落ちることを確認済み —— 落ちない gate は劇場）。

## 接触してよい形（特定電子メール法）

日本の特定電子メール法はオプトイン規制（法 3 条 1 項）で、広告宣伝メールは
原則として同意が要る。この loop が当たる例外は **自らメールアドレスを公表して
いる団体・営業を営む個人**（同項 4 号）ただ 1 つ。したがって:

- アドレスを知っているだけでは足りない。**どこで公表されていたか（URL）と
  いつ見たか**が無ければ、例外に当たる根拠が持てない → `:no-publication-evidence`
- サイトに「営業メールお断り」があれば公表アドレスでも送れない（4 号ただし書き）
- 本文には送信者の名称・住所・受信拒否の通知先が要る（法 4 条）
- 一度断られた相手は恒久に送らない。再送は最短 60 日、生涯 2 回まで

`noren.governor` はこれを**判定に必要な事実が渡されていない場合も含めて**
HARD で止める。検査に必要な材料が無いことは、検査に通ったことではない。

## 使う

```clojure
(require '[noren.prospect :as prospect] '[noren.diagnose :as diagnose]
         '[noren.prescribe :as prescribe] '[noren.governor :as gov])

(prospect/eligible p "2026-08-11")
;; => {:ok? true :reasons [] :surface :storefront}

(-> (diagnose/diagnose html {:surface :storefront :url url :year 2026})
    prescribe/prescribe)
;; => {:action :rebuild :claims [{:claim/axis :hours :claim/text "営業時間の…"}] …}

(gov/review {:prospect p :prescription rx :message m
             :history hs :suppression #{} :now "2026-08-11"})
;; => {:decision :commit|:hold :violations [...] :warnings [...] :receipt {...}}
```

## テスト

```bash
kbb --backend sci --classpath "src:test:../design-quality/src:../jp-go-digital-design-system/src:../html/src:../css/src" run_tests.cljk
kbb -M:test    # 同じ .cljc を JVM でも
```

17 tests / 116 assertions。接触の HARD rule 11 本と DiscoveryGovernor の
reject 条件は、すべて「実際に止まること」を 1 つずつ壊して確かめている。
