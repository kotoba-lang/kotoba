# goyoukiki Actor Design — match-LLM as a contained intelligence node

政府調達（入札公告・調達予定）と全省庁統一資格の候補団体を扱う actor。
teian（deck-LLM⊣BriefingGovernor）/ koyomi（schedule-LLM⊣ComplianceGovernor）
と同型に **match-LLM⊣ProcurementGovernor** を据え、charter（propose→match
のみ・通知は常に人間・機微情報の最小開示・沈黙期間中は共有不可・発注機関への
接触経路を持たない）を守る。

actor は「候補を発見して match を記録する」だけで、実際に候補へ通知する
（match/share）のは常に人間承認後の MatchTarget port。actor が候補や発注
機関に勝手に連絡することは設計上ない（提案という *proposal* と、通知という
*actuation* の分離。さらに発注機関への経路自体が protocol 上に存在しない —
teian が独自のデッキ表現を作らないのと同様、goyoukiki は独自の「発注機関
向け通知」表現を作らない、というより意図的に作らない）。

## 1. 二つのフロー

```
ingest(record-op):  intake → record → END                       ; 観測。常時ON、無作動
assess(assess-op):  intake → advise → govern → decide → commit | hold | 人間承認
```

- **ingest**: `:opportunity/register`（:forecast=調達予定 または
  :tender=入札公告。先回り観測は :forecast も :tender も同じ扱い）
  `:candidate/register`（全省庁統一資格 登録団体）。LLM/governor/phase を
  通らない事実記録。
- **assess**: `:match/propose` `:match/share`。match-LLM 提案 →
  ProcurementGovernor 検査 → phase gate → 通知(share)は必ず人間
  （`interrupt-before`）。

チャネル: `:request :context(:phase) :proposal :verdict :disposition :record :approval :audit`

### propose ≠ share — 「気軽な commit」と「常に人間の通知」

`:match/propose` の commit は **データ**（opportunity に乗る候補提案 —
candidate-id・score・rationale）で、外部への effect が無い。phase 2/3 で
clean+confident+eligible なら governor 通過即 commit してよい（気軽な
`git commit` 相当）。一方 `:match/share` は **外部 effect そのもの**
（候補団体への実通知）なので、governor の `stakes?` が常に true — phase に
関わらず `:request-approval` へ escalate し、人間が承認して初めて
`goyoukiki.matchport/share!` が呼ばれる（`git merge` 相当、常に人間）。

`:match/propose` の commit 時に `goyoukiki.matchport/propose-match!` も呼ぶ
（候補提案の記録 — teian の `:deck/draft` が `deckport/propose-revision!`
を呼ぶのと同型）。

## 2. 注入される依存（swap）

- **Store**（`goyoukiki.store/Store`）: `MemStore` ‖ `DatomicStore`
  （langchain.db、`:db-api` で実 Datomic Local / kotoba pod）。
- **Advisor**（`goyoukiki.matchllm/Advisor`）: `mock-advisor` ‖ `llm-advisor`
  （langchain.model）。破損応答は confidence 0 noop → governor が
  hold/escalate。
- **MatchTarget**（`goyoukiki.matchport/MatchTarget`）: `mock-matchport` のみ
  を同梱（既定・決定的・in-memory）。`share!` は候補自身の登録
  `:contact` のみを宛先として解決する — protocol 上、発注機関を宛先に
  できる経路が存在しない（構造的な安全境界。governor のルールではなく
  型の設計で防ぐ）。実 Notifier（メール/ポータル等）の live クライアントは
  本 repo に含めない — 各社 API token 発行が前提で live 結合は未検証。
- **Phase**（context `:phase 0..3`）: proposeの自律度のみ段階化。share は
  常に人間。

## 3. ProcurementGovernor（独立・propose のみ許可）

match-LLM は candidate の適格性も cross-candidate の機密境界も沈黙期間の
概念も no-actuation charter も知らないので、EAVT 上の規則として **独立**に
提案を *棄却* し HOLD に落とせる別系統である必要がある。

| op | HARD | 常に人間? |
|---|---|---|
| `:match/propose` | subject存在(no-opportunity) / no-actuation(effect=`:draft`) / nomination(candidate非nil) / eligibility / redaction-required | いいえ(phase≥2で自動可) |
| `:match/share` | subject存在 / candidate存在 / match存在(no-match) / eligibility(recheck) / redaction(recheck) / silence-period | **常に** |

SOFT: confidence floor(<0.6) → escalate。

- **no-actuation**: `:match/propose` proposal の `:effect` は `:draft` のみ。
  実通知は人間承認後、MatchTarget port のみが行う。
- **nomination**: proposal は `:candidate` を必ず具体的に指名する
  （confidence だけを信用しない — nil candidate が commit まで届くと
  store が壊れる）。
- **eligibility**: 指名された candidate が opportunity の
  `:required-categories`/`:min-rank` を満たさなければ hard violation
  （存在しない・不適格な候補への match はマッチングエンジンが絶対に
  生んではならない欠陥）。share 時は再検証（propose 承認後の適格性
  失効ドリフトを検知）。
- **redaction-required**: proposal の `:cites` が機微区分
  （:other-candidate-capability/:other-candidate-pricing/
  :agency-internal-budget）を `:redactions` 無しに引用したら hard
  violation。
- **silence-period**: opportunity が `:silence-period?` の間は
  `:match/share` が hard violation（`:match/propose` は影響を受けない —
  内部提案自体に外部効果は無いため）。官製談合防止法・入札談合等関与
  行為防止法が懸念する「競争入札の最中に情報の非対称性・調整の経路と
  なる」リスクを、この一点でブロックする。

## 4. Phase 0→3

| phase | propose | share |
|---|---|---|
| 0 ingest-only | 発行しない(hold, :phase-disabled) | — |
| 1 assisted | 常に人間 | 常に人間 |
| 2 assisted-match | clean+confident+eligibleで自動commit | 常に人間 |
| 3 supervised | 同上 | **常に人間**(phaseに関わらず不変) |

## 5. 台帳（append-only）

`:t` タグ: `:recorded`(ingest) / `:matchllm-proposal`(advise trace) /
`:goyoukiki-hold`(HARD違反) / `:approval-requested`(escalate) /
`:human-signoff` / `:signoff-rejected` / `:committed`。「いつ・どの案件の・
どの候補が・どの根拠で・誰が承認して通知したか」が不変に残る。

## 6. スコープ境界（意図的に実装しないもの）

- **発注機関への接続。** `goyoukiki.matchport/MatchTarget` に発注機関を
  宛先にできるパラメータは存在しない。goyoukiki は「候補にopportunityを
  知らせる」側だけの actor であり、「発注機関に候補を売り込む/未承諾提案を
  送る」actor ではない（unsolicited-proposal規制・ex-parte接触規制の
  リスク領域に踏み込まない設計判断）。
- **入札応答文書のドラフト。** shared match を受けて実際の提案書を書くのは
  `teian`/`tayori` の役割（両者は既に文書ドラフト actor として存在する —
  重複実装しない）。
- **JP以外の国。** v1 は日本のみ。米国/EU/中国は別 ADR・別 follow-up。

## 7. 参照

- 90-docs/adr/2607070200-kotoba-lang-goyoukiki-procurement-signal-actor.md
  （superproject 側の正本 ADR — Context/Decision/Consequences の全文）
- `../teian/docs/DESIGN.md` / `../koyomi/docs/DESIGN.md`（同型 actor の手本）
- ADR-2607032330（cloud-itonami-iso3166 market-entry-compliance blueprints —
  goyoukikiとの役割分担: あちらは市場参入コンプライアンスの静的blueprint、
  goyoukikiは案件⟷候補のライブなmatching control plane）
- ADR-2607051300（cross-org-capability-map — "サプライチェーン企業が情報を
  載せAIが分析・マッチングする" という未着手ギャップの記録。本actorがその
  最初の実装）
