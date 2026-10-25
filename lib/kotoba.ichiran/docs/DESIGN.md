# ichiran Actor Design — tally-LLM as a contained intelligence node

itonami ledger からの集計表（ワークブック）の下書き・配布を扱う actor。
teian（deck-LLM⊣BriefingGovernor）/ koyomi（schedule-LLM⊣ComplianceGovernor）
と同型に **tally-LLM⊣TallyGovernor** を据え、charter（propose→draft のみ・
配布は常に人間・機微情報の最小開示・テナント分離）を守る。

actor は「下書き（workbook の EDN 案）を書く」だけで、実際に配布する
（tally/publish = CFO・経営会議への配信）のは常に人間承認後の TallyTarget
port。actor が集計表を勝手に配ることは設計上ない（下書きという *proposal* と、
配布という *actuation* の分離）。content は `kotoba-lang/sheets` の
`sheets.model` EDN そのもの — ichiran は独自のワークブック表現を作らない。

## 1. 二つのフロー

```
ingest(record-op):  intake → record → END                       ; 観測。常時ON、無作動
assess(assess-op):  intake → advise → govern → decide → commit | hold | 人間承認
```

- **ingest**: `:artifact/register` — 集計対象の itonami activity を
  ground fact として記録。LLM/governor/phase を通らない事実記録。
- **assess**: `:tally/draft` `:tally/publish`。tally-LLM 提案 →
  TallyGovernor 検査 → phase gate → 配布(publish)は必ず人間
  （`interrupt-before`）。

チャネル: `:request :context(:phase) :proposal :verdict :disposition :record :approval :audit`

### draft ≠ publish — 「気軽な commit」と「常に人間の配信」

`:tally/draft` の commit は **データ**（activity に乗る下書き — sheets EDN
content）で、外部への effect が無い。phase 2/3 で clean+confident なら
governor 通過即 commit してよい（気軽な `git commit` 相当）。一方
`:tally/publish` は **外部 effect そのもの**（CFO・経営会議への実配布）
なので、governor の `stakes?` が常に true — phase に関わらず
`:request-approval` へ escalate し、人間が承認して初めて
`ichiran.tallyport/publish!` が呼ばれる（`git merge` 相当、常に人間）。

`:tally/draft` の commit 時に `ichiran.tallyport/propose-revision!` も呼ぶ
（下書き候補の記録 — koyomi の `:event/draft` が
`scheduleport/propose-revision!` を呼ぶのと同型）。

## 2. 注入される依存（swap）

- **Store**（`ichiran.store/Store`）: `MemStore` ‖ `DatomicStore`（langchain.db、
  `:db-api` で実 Datomic Local / kotoba pod）。
- **Advisor**（`ichiran.coordllm/Advisor`）: `mock-advisor` ‖ `llm-advisor`
  （langchain.model）。破損応答は confidence 0 noop → governor が
  hold/escalate。
- **TallyTarget**（`ichiran.tallyport/TallyTarget`）: `mock-tallyport` のみを
  同梱（既定・決定的・in-memory）。`publish!` は `sheets.wire`
  の Transit envelope export を試み（失敗時は黙って export なしに
  degrade）、実配布は注入された Distributor fn（既定 no-op）に委ねる。実
  Distributor（メール/Slack/BI ツール等）の live クライアントは本 repo に
  含めない — 各社 API token 発行が前提で live 結合は未検証（ADR
  Consequences）。`propose-revision!` は draft-commit 時、`publish!` は
  承認後のみ呼ばれる。
- **Phase**（context `:phase 0..3`）: drafting の自律度のみ段階化。publish は
  常に人間。

## 3. TallyGovernor（独立・propose のみ許可）

tally-LLM は artifact のテナント境界も redaction 要件も no-actuation charter
も知らないので、EAVT 上の規則として **独立**に提案を *棄却* し HOLD に
落とせる別系統である必要がある。

| op | HARD | 常に人間? |
|---|---|---|
| `:tally/draft` | missing-subject(no-artifact、独立・無条件) / no-actuation(effect=`:draft`) / redaction-required / tenant-isolation | いいえ(phase≥2で自動可) |
| `:tally/publish` | missing-subject / draft存在(no-draft) / redaction(recheck) / tenant-isolation(recheck) | **常に** |

SOFT: confidence floor(<0.6) → escalate。

- **missing-subject**: 参照する artifact(itonami activity) が store に
  未登録なら必ず hard violation。proposal の `:content`/`:tenant` の中身に
  一切依存しない、独立・無条件のチェック（koyomi の
  `missing-activity-violations` の修正版をモデルに、最初から実装 —
  ADR-2607062030 amendment）。`:tally/draft` `:tally/publish` の両方の
  トップレベル `concat` に常駐し、他のどのチェックより先に評価される。
- **no-actuation**: `:tally/draft` proposal の `:effect` は `:draft` のみ。
  実配布は人間承認後、TallyTarget port のみが行う。
- **redaction-required**: proposal の `:cites` が機微区分（`:financial`/
  `:legal`/`:personnel`）を `:redactions` 無しに引用したら hard violation。
- **tenant-isolation**: proposal の `:tenant` が artifact 自身の登録
  `:repo`（= itonami activity の repo 由来のテナント識別子）と不一致なら
  hard violation（他テナント向けの draft 生成を防ぐ）。
- **publish 時の再検証（redaction/tenant recheck）**: `:tally/publish` は
  proposal が転送してきた cites/redactions/tenant を信用せず、
  store から fresh に読んだ「今まさに保管されている draft」に対して
  redaction-violations/tenant-violations を **再実行**する。draft 承認時
  点と publish 時点の間に draft の内容が（governor を経由しない別経路で）
  ドリフトしていても、publish 直前にもう一度捕まえる（TOCTOU 対策。
  ADR-2607062030 amendment: teian の `:deck/publish` レビューで見つかった
  ギャップの教訓を最初から実装 — `test/ichiran/governor_contract_test.cljk`
  の `publish-recheck-catches-post-draft-redaction-drift`/
  `...-tenant-drift` で検証)。

## 4. Phase 0→3

| phase | draft | publish |
|---|---|---|
| 0 ingest-only | 発行しない(hold, :phase-disabled) | — |
| 1 assisted | 常に人間 | 常に人間 |
| 2 assisted-draft | clean+confidentで自動commit | 常に人間 |
| 3 supervised | 同上 | **常に人間**(phaseに関わらず不変) |

## 5. 台帳（append-only）

`:t` タグ: `:recorded`(ingest) / `:coordllm-proposal`(advise trace) /
`:ichiran-hold`(HARD違反) / `:approval-requested`(escalate) /
`:human-signoff` / `:signoff-rejected` / `:committed`。「いつ・どの
activity の・どの根拠で・誰が承認して配布したか」が不変に残る。

## 6. 参照

- 90-docs/adr/2607062030-kotoba-lang-ichiran-tally-scaffold.md（superproject
  側の正本 ADR — Context/Decision/Consequences の全文、フル実装への昇格を
  記録）
- `../teian/docs/DESIGN.md`（deck-LLM⊣BriefingGovernor、propose→draft/
  publish 非対称性・DeckTarget port の直近の手本）/
  `../koyomi/src/koyomi/governor.cljc`（missing-activity-violations の
  独立・無条件チェックの手本）
- `../sheets/src/sheets/model.cljc`（ichiran が verbatim content として保持
  する workbook/tab/cell/formula/named-range/chart EDN モデル）/
  `../sheets/src/sheets/wire.cljc`（TallyTarget の Transit export が使う
  `workbook-envelope`）
