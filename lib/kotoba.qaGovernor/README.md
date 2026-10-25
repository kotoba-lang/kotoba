# kotoba-lang/qa-governor

「Nintendoクオリティ」を項目化した共通QAルーブリック + governor + 監査台帳。
設計は [ADR-2607031100](../../../90-docs/adr/2607031100-kotoba-lang-qa-governor-actor.md)
（superproject `com-junkawasaki/root`）を参照。

AGENTS.mdの「Actors」節にある既存パターン——知能ノード（LLM）を1ノードに
封じ込め *proposal のみ* 返させ、別系統のgovernorが検閲する。単一不変条件
「governorが拒否するcommitをactorは決して行わない」——をQAに転用したもの。
`ghosthacker-flow`（[ADR-2607023200](../../../90-docs/adr/2607023200-ghosthacker-game-portfolio-flow.md)）
を最初のconsumerとして想定しているが、このrepo自体はドメイン非依存で、
どのkotoba-lang/gftdcojp/etzhayyim/com-junkawasaki配下のrepoからも使える。

## コンセプト

1. **`qa-governor.rubric`** — カテゴリ×重みのルーブリック定義と加重平均
   スコア計算。既定カテゴリ（`stability`/`correctness`/`robustness`/
   `documentation`/`consistency`）はドメイン非依存。consumerは
   `extend-rubric`で固有カテゴリ（例: game-feel）を追加できる。
2. **`qa-governor.governor`** — 知能ノードが返す採点案（`{:category :score
   :evidence}`の集合）を検証する。**LLMの自己申告を無条件で信用しない**——
   evidenceが無い、または高スコアの主張とevidenceの文言が矛盾する場合は
   却下する。
3. **`qa-governor.ledger`** — 承認済みスコアのappend-only監査台帳。
   repo単位の履歴・最新値・推移を追える。

## 現在の実装範囲

pure `.cljc` の3namespace（rubric/governor/ledger）に加え、**5カテゴリ
全ての決定論的（LLM無し）evidence収集アダプタ**を実装済み（`test/`に
テストあり）:

- **`qa-governor.collectors.clojure-project`**（pure）— `kbb -M:test` /
  `kbb -M:lint` の出力文字列をparseし、correctness/consistencyの
  proposal entryを作る。実行は`clojure-project-shell`（JVM host adapter）。
- **`qa-governor.collectors.stability`**（pure）— `future`/`agent`系を
  使うのに`shutdown-agents`が無い`-main`を検出する（ghosthacker-flow.terminal
  実装時に見つけた実バグの回帰ガード）。テスト実行がtime budgetを超えて
  いないかも見る。
- **`qa-governor.collectors.robustness`**（pure）— error-pathテストの痕跡
  （例外ベースの`thrown?`と、`ok? false`/`:problem`のような構造化Result型
  ベースの両方——後者が無いと`thrown?`を使わない流儀のrepoを不当に低評価
  してしまうことが`kotoba-lang/kotoba`への適用で判明し修正した）と、
  guard/boundary系のdeftest名の有無をテストソースから数える。
- **`qa-governor.collectors.documentation`**（pure）— 公開`defn`の
  docstringカバレッジ率 + README.md/CHANGELOG.mdの有無。
- **`qa-governor.collectors.static-analysis-shell`**（JVM host adapter）—
  上記3collectorにファイル内容を読んで渡す。
- **`qa-governor.collectors.repo`**（JVM host adapter）— 全collectorを
  1つのproject-dirに対してまとめて実行する最上位エントリポイント。

**実際に`ghosthacker-flow`に対して実行した結果**（2026-07-03時点）:
全5カテゴリがcorrectness=100/consistency=100/stability=100/robustness=100/
documentation=100で揃い、governor全承認、**総合スコア100.0（グレードS）**。
LLMを一切介さず、実際のテスト実行・lint結果・ソースコードの構造だけから
到達した数字。

## `qa-governor.operation` — langgraph-clj StateGraph配線（ADR-2607031100 追加実装）

`intake → collect → govern → decide → commit | hold`の1repo=1QAパス実行を
StateGraphとして配線した（`minidrama.operation`/`tashikame.operation`等と
同型のActorsトポロジー）。`:collect`ノードは今日は上記5つの決定論的
collector（`qa-governor.collectors.repo/collect`）——**自己申告するLLMは
まだ無い**——だが、governorのevidence/score整合性チェックは決定論的
collectorに対しても有効な回帰ガードとして機能する（collector自体の実装
バグでスコアと矛盾するevidenceを返した場合に検知する）。将来の実LLM採点
ノードは、この同じ`:govern`ノードに供給する追加のproposal源として差し込む
だけでよい設計——他のノードを変更する必要はない。

`qa-governor.ledger`は「承認済みスコアのみ」という自身の契約を尊重し、
holdの監査痕跡はledgerでなく、その run固有の`:audit`チャンネル（in-memory、
呼び出し側が結果から読む）に積む。

```clojure
(require '[qa-governor.operation :as op]
         '[langgraph.graph :as g]
         '[qa-governor.ledger :as ledger])

(def store (op/mem-ledger-store)) ; MemStore相当。永続バックエンドは follow-up

(def actor (op/build {:ledger-get (:ledger-get store) :ledger-put! (:ledger-put! store)}))

(g/run* actor {:request {:repo "ghosthacker-flow" :project-dir "/path/to/ghosthacker-flow"}} {})
;; => {:state {:disposition :commit ...} ...}

(ledger/latest ((:ledger-get store)) "ghosthacker-flow")
;; => {:repo "ghosthacker-flow" :timestamp-ms ... :scores {...} :total ... :grade ... :verdict :approved}
```

## 使い方（イメージ、pure coreのみ手組みする場合）

```clojure
(require '[qa-governor.rubric :as rubric]
         '[qa-governor.governor :as governor]
         '[qa-governor.ledger :as ledger])

;; 1. 知能ノード(LLM)がproposalを返す(evidence付き)
(def proposal
  [{:category :stability :score 100 :evidence "clean exit in 1.6s, no hang, 3 manual runs"}
   {:category :correctness :score 100 :evidence "109 assertions green, clj-kondo 0 warnings"}])

;; 2. governorが検証する
(def result (governor/evaluate-proposal proposal))
;; => {:approved [...] :rejected [] :all-approved? true}

;; 3. 承認された場合のみ、スコアを計算して台帳に積む(timestamp-msは呼び出し側)
(when (:all-approved? result)
  (let [scores (into {} (map (juxt :category :score) (:approved result)))
        total (rubric/weighted-score rubric/default-rubric scores)]
    (ledger/record ledger/empty-ledger
                    {:repo "ghosthacker-flow"
                     :timestamp-ms 0
                     :scores scores
                     :total total
                     :grade (rubric/grade total)
                     :verdict :approved})))
```

## 開発

`qa-governor.operation`はlanggraph-clj（sibling `:local/root`、
`io.github.com-junkawasaki/langgraph-clj`）に依存するため、`:dev`エイリアス
（langgraph-clj自身の推移依存であるkotoba-lang/langchainをlocal checkoutに
override）を付けて実行する:

```bash
kbb -M:dev:test
```

Lint（clj-kondo、Clojars経由でHomebrew等の別インストール不要）:

```bash
kbb -M:lint
```

## ライセンス

MIT License — [LICENSE](LICENSE) 参照。
