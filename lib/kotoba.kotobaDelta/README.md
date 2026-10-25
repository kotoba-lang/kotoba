# kotoba-delta

**Datomic-for-code-edits** — kotoba/kotobase スタック上の DeltaDB 相当
（ADR-2607161325、設計判断の元は ADR-2607160005 Phase 4 research）。
agent の編集を **署名付き・parent-covering な離散 operation の append-only
log** として記録し、決定的に replay / git projection する。

## DeltaDB との設計差分（意図的）

- **text CRDT を持たない**: 書き手は agent で、編集は Edit/Write/Remove の
  離散 op として届く。順序は log（transactor 型全順序）が与えるので収束は
  構成上自明。CRDT が要る「人間のキーストローク・オフライン同時編集」は
  スコープ外（必要になったら別途）。
- **conflict は明示**: `:op/old` が一意に見つからない edit は
  `:old-not-found` / `:ambiguous-old` の first-class conflict。silent
  convergence はしない（semantic conflict は merge で消えないため）。
- **署名 + 権限が最初から**: 全 op は did:key actor の Ed25519 署名 +
  parent hash（replay 攻撃は構造的に不能）。DeltaDB が沈黙している
  authorization 層は fleet-vcs（signed pins + quorum）がそのまま上に載る。
- **secrets は log に入る前に拒否**: admission gate が秘密情報パターンを
  reject（op-log が API key を永久保存する liability への回答）。
- **会話リンク**: `:op/turn` が op を生成した会話ターンに紐付く —
  prompt→行 の provenance。
- **git projection は決定的**: 同一 log からの projection は**同一 commit
  SHA** を生む（実測で確認済み）。fleet-vcs の pin 検証（サーバ側 git SHA
  消費）とそのまま噛み合う。

## Usage

```bash
kbb --backend sci --classpath src bin/delta.cljk record --log ops.edn --key agent.pem \
    --kind edit --file src/a.cljc --old '(def x 1)' --new '(def x 2)' \
    --turn conv-xxx/turn-43 [--workspace DIR]
kbb --backend sci --classpath src bin/delta.cljk verify  --log ops.edn
kbb --backend sci --classpath src bin/delta.cljk replay  --log ops.edn --workspace DIR
kbb --backend sci --classpath src bin/delta.cljk project --log ops.edn --repo DIR   # 決定的 commit
```

## Tests

```bash
kbb --backend sci --classpath src:test run-tests.cljk
```

## anchor → code_graph definition-CID 結合（ADR-2607160005/2607161325）

`delta.anchor` の `:anchor/def-cid`（定義テキストの content-addressed 識別子）は
kotobase code_graph が definition CID に使うものと同一。`code-graph-ref` が
code_graph の definition 参照形（`:code.definition/cid|name|kind`）に変換する。
**同一定義テキストは surrounding code に関係なく同一 def-cid** になり、これが
**delta op-log（どの op が定義に触れたか）と code_graph（content-addressed
definitions）を結ぶ join key** になる。hash-fn を code_graph と同じ
（sha256/CIDv1）にすれば CID が literal に一致。

## ⑱ 構造 anchor + IStore 永続化（ADR-2607160005）

- `delta.anchor`: op を行番号でなく **定義（kind+name）+ content hash** に
  anchor。コード移動に耐える（DeltaDB の "references survive as code moves"
  を kotoba-native に）。resolve は :unchanged/:moved/:edited/:gone を返す。
  balanced-delimiter splitter で文字列・コメントを誤認しない。
- `delta.op` v2: op が `:op/anchor` を**署名 payload に**含む（provenance が
  file path でなく定義に紐付く）。`log-head` が op-log head を返す。
- `delta.store`: op-log を **kotobase IStore stream**（append + monotonic
  :seq、cursor resume）で永続化。LocalStore standalone でも kotobase.net の
  KotobaseStore でも同一契約（`KotobaseStore ≡ LocalStore`）。log-head +
  :seq cursor が **signed fleet head に折り込まれ**、manifest と編集
  provenance を一つの署名 head が証明する。

## 位置づけ / roadmap

- core は pure `.cljc`（`delta.op`）、IO は nbb CLI。kotobase の
  `IStore` streams / `code_graph`（definition CID anchor）への接続、
  fleet-vcs ledger との統合（op-log head を signed fleet head に含める）、
  S 式構造 anchor は follow-up。
- DeltaDB は観測継続（ADR-2607160005 P4）。format が公開されたら
  互換 projection を検討するが、本 repo は待たない。
