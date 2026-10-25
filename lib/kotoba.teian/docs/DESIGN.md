# teian Actor Design — deck-LLM as a contained intelligence node

社内資料（デッキ/文書/表）の下書き・配布を扱う actor。kekkai（coord-LLM⊣
TailnetGovernor）/ tayori（reply-LLM⊣ComplianceGovernor）と同型に
**deck-LLM⊣BriefingGovernor** を据え、charter（propose→draft のみ・配布は常に
人間・機微情報の最小開示・テナント分離）を守る。

actor は「下書き（deck/doc/sheet の EDN 案）を書く」だけで、実際に配布する
（deck/publish = 取締役会・経営会議への配信）のは常に人間承認後の DeckTarget
port。actor が資料を勝手に配ることは設計上ない（下書きという *proposal* と、
配布という *actuation* の分離）。content は `kotoba-lang/slides` の
`slides.model` EDN そのもの — teian は独自のデッキ表現を作らない。

## 1. 二つのフロー

```
ingest(record-op):  intake → record → END                       ; 観測。常時ON、無作動
assess(assess-op):  intake → advise → govern → decide → commit | hold | 人間承認
```

- **ingest**: `:artifact/register` — 資料作成対象の itonami activity を
  ground fact として記録。LLM/governor/phase を通らない事実記録。
- **assess**: `:deck/draft` `:deck/publish`。deck-LLM 提案 →
  BriefingGovernor 検査 → phase gate → 配布(publish)は必ず人間
  （`interrupt-before`）。

チャネル: `:request :context(:phase) :proposal :verdict :disposition :record :approval :audit`

### draft ≠ publish — 「気軽な commit」と「常に人間の配信」

`:deck/draft` の commit は **データ**（activity に乗る下書き — slides EDN
content）で、外部への effect が無い。phase 2/3 で clean+confident なら
governor 通過即 commit してよい（気軽な `git commit` 相当）。一方
`:deck/publish` は **外部 effect そのもの**（取締役会・経営会議への実配布）
なので、governor の `stakes?` が常に true — phase に関わらず
`:request-approval` へ escalate し、人間が承認して初めて
`teian.deckport/publish!` が呼ばれる（`git merge` 相当、常に人間）。

`:deck/draft` の commit 時に `teian.deckport/propose-revision!` も呼ぶ
（下書き候補の記録 — tayori の `:document/revise` が
`docport/propose-revision!` を呼ぶのと同型）。

## 2. 注入される依存（swap）

- **Store**（`teian.store/Store`）: `MemStore` ‖ `DatomicStore`（langchain.db、
  `:db-api` で実 Datomic Local / kotoba pod）。
- **Advisor**（`teian.deckllm/Advisor`）: `mock-advisor` ‖ `llm-advisor`
  （langchain.model）。破損応答は confidence 0 noop → governor が
  hold/escalate。
- **DeckTarget**（`teian.deckport/DeckTarget`）: `mock-deckport` のみを同梱
  （既定・決定的・in-memory）。`publish!` は best-effort で `slides.office`
  の pptx export を試み（deck kind のみ、失敗時は黙って export なしに
  degrade）、実配布は注入された Distributor fn（既定 no-op）に委ねる。実
  Distributor（メール/Slack 添付等）の live クライアントは本 repo に含めない
  — 各社 API token 発行が前提で live 結合は未検証（ADR Consequences）。
  `propose-revision!` は draft-commit 時、`publish!` は承認後のみ呼ばれる。
- **Phase**（context `:phase 0..3`）: drafting の自律度のみ段階化。publish は
  常に人間。

## 3. BriefingGovernor（独立・propose のみ許可）

deck-LLM は artifact のテナント境界も redaction 要件も no-actuation charter
も知らないので、EAVT 上の規則として **独立**に提案を *棄却* し HOLD に
落とせる別系統である必要がある。

| op | HARD | 常に人間? |
|---|---|---|
| `:deck/draft` | subject存在(no-artifact) / no-actuation(effect=`:draft`) / redaction-required / tenant-isolation | いいえ(phase≥2で自動可) |
| `:deck/publish` | subject存在 / draft存在(no-draft) | **常に** |

SOFT: confidence floor(<0.6) → escalate。

- **no-actuation**: `:deck/draft` proposal の `:effect` は `:draft` のみ。
  実配布は人間承認後、DeckTarget port のみが行う。
- **redaction-required**: proposal の `:cites` が機微区分（`:financial`/
  `:legal`/`:personnel`）を `:redactions` 無しに引用したら hard violation。
- **tenant-isolation**: proposal の `:tenant` が artifact 自身の登録
  `:repo`（= itonami activity の repo 由来のテナント識別子）と不一致なら
  hard violation（他テナント向けの draft 生成を防ぐ）。

## 4. Phase 0→3

| phase | draft | publish |
|---|---|---|
| 0 ingest-only | 発行しない(hold, :phase-disabled) | — |
| 1 assisted | 常に人間 | 常に人間 |
| 2 assisted-draft | clean+confidentで自動commit | 常に人間 |
| 3 supervised | 同上 | **常に人間**(phaseに関わらず不変) |

## 5. 台帳（append-only）

`:t` タグ: `:recorded`(ingest) / `:deckllm-proposal`(advise trace) /
`:teian-hold`(HARD違反) / `:approval-requested`(escalate) /
`:human-signoff` / `:signoff-rejected` / `:committed`。「いつ・どの
activity の・どの根拠で・誰が承認して配布したか」が不変に残る。

## 6. 参照

- 90-docs/adr/2607062000-kotoba-lang-teian-briefing-actor.md（superproject
  側の正本 ADR — Context/Decision/Consequences の全文）
- `../kekkai/docs/DESIGN.md`（同型 actor の手本）/ `../tayori/docs/DESIGN.md`
  （propose→draft/publish 非対称性・DocTarget port の直近の手本）
- `../slides/src/slides/model.cljc`（teian が verbatim content として保持する
  deck/doc/sheet EDN モデル）
