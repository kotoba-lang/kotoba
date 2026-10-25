# tayori Actor Design — reply-LLM as a contained intelligence node

Email/Slack/WhatsApp の返信・git 文書の改訂を扱う actor。kekkai（coord-LLM⊣
TailnetGovernor）/ gijiroku（scribe-LLM⊣PrivacyGovernor）と同型に
**reply-LLM⊣ComplianceGovernor** を据え、charter（propose→draft/revision のみ・
送信/publish は常に人間・機微情報の最小開示）を守る。

actor は「下書き/改訂案を書く」だけで、実際に送信・publish するのは常に人間承認
後の Channel/DocTarget port。actor がメールを送ることも文書を publish すること
も設計上ない（メール/文書という *actuation* と、下書きという *proposal* の分離）。

## 1. 二つのフロー

```
ingest(record-op):  intake → record → END                       ; 観測。常時ON、無作動
assess(assess-op):  intake → advise → govern → decide → commit | hold | 人間承認
```

- **ingest**: `:thread/register` `:message/ingest` `:contact/register`
  `:document/register` を ground fact として記録。LLM/governor/phase を通らない
  事実記録。
- **assess**: `:reply/draft` `:reply/send` `:document/revise` `:document/publish`。
  reply-LLM 提案 → ComplianceGovernor 検査 → phase gate → 送信/publish は必ず
  人間（`interrupt-before`）。

チャネル: `:request :context(:phase) :proposal :verdict :disposition :record :approval :audit`

### draft/revise ≠ send/publish — 「気軽な commit」と「常に人間の merge」

`:reply/draft`/`:document/revise` の commit は **データ**（thread/document に
乗る下書き/改訂案）で、外部への effect が無い。phase 2/3 で clean+confident なら
governor 通過即 commit してよい（気軽な `git commit` 相当）。一方
`:reply/send`/`:document/publish` は **外部 effect そのもの**（メール送信・
PR マージ）なので、governor の `stakes?` が常に true — phase に関わらず
`:request-approval` へ escalate し、人間が承認して初めて
`tayori.channel/send-reply!` / `tayori.docport/publish!` が呼ばれる（`git merge`
相当、常に人間）。

`:document/revise` だけは commit 時に `tayori.docport/propose-revision!` も呼ぶ
（本物の branch+commit — 文書は下書きの時点で既に「本物の PR」になる）。返信は
下書きの時点では外部に一切出ない（メール下書きフォルダへの保存すら行わない —
必要なら Channel 実装側の follow-up）。

## 2. 注入される依存（swap）

- **Store**（`tayori.store/Store`）: `MemStore` ‖ `DatomicStore`（langchain.db、
  `:db-api` で実 Datomic Local / kotoba pod）。
- **Advisor**（`tayori.replyllm/Advisor`）: `mock-advisor` ‖ `llm-advisor`
  （langchain.model）。破損応答は confidence 0 noop → governor が hold/escalate。
- **Channel**（`tayori.channel/Channel`）: `mock-channel` ‖ `email`/`slack`/
  `whatsapp`（I/O 注入、live 未検証）。`send-reply!` は承認後のみ呼ばれる。
- **DocTarget**（`tayori.docport/DocTarget`）: `mock-doctarget` ‖ `git`
  （GitHub API、I/O 注入、live 未検証）。`propose-revision!` は draft-commit 時、
  `publish!` は承認後のみ呼ばれる。
- **Phase**（context `:phase 0..3`）: drafting/revising の自律度のみ段階化。
  send/publish は常に人間。

## 3. ComplianceGovernor（独立・propose のみ許可）

reply-LLM は宛先の consent 状態も redaction 要件も no-actuation charter も
知らないので、EAVT 上の規則として **独立**に提案を *棄却* し HOLD に落とせる
別系統である必要がある。

| op | HARD | 常に人間? |
|---|---|---|
| `:reply/draft` | no-actuation(effect=`:draft`) / redaction-required | いいえ(phase≥2で自動可) |
| `:document/revise` | no-actuation(effect=`:revision`) / redaction-required | いいえ(phase≥2で自動可) |
| `:reply/send` | consent-required(宛先が`:blocked`でない) | **常に** |
| `:document/publish` | tenant-isolation(target=document自身の`:path`) | **常に** |

SOFT: confidence floor(<0.6) → escalate。

## 4. Phase 0→3

| phase | draft/revise | send/publish |
|---|---|---|
| 0 ingest-only | 発行しない(hold) | — |
| 1 assisted | 常に人間 | 常に人間 |
| 2 assisted-draft | clean+confidentで自動commit | 常に人間 |
| 3 supervised | 同上 | **常に人間**(phaseに関わらず不変) |

## 5. 台帳（append-only）

`:t` タグ: `:recorded`(ingest) / `:replyllm-proposal`(advise trace) /
`:tayori-hold`(HARD違反) / `:approval-requested`(escalate) /
`:human-signoff` / `:signoff-rejected` / `:committed`。「いつ・どのスレッド/
文書の・どの根拠で・誰が承認して送信/publishしたか」が不変に残る。

## 6. 参照

- 90-docs/adr/2607061500-kotoba-lang-tayori-correspondence-actor.md（superproject
  側の正本 ADR — Context/Decision/Consequences の全文）
- `../kekkai/docs/DESIGN.md`（同型 actor の直近の手本）
- ADR-2607031100（gijiroku — メール/Slack Distributor port の先行予見）
