# koyomi Actor Design — schedule-LLM as a contained intelligence node

予定共有(カレンダーイベントの下書き・共有)を扱う actor。kekkai（coord-LLM⊣
TailnetGovernor）/ tayori（reply-LLM⊣ComplianceGovernor）と同型に
**schedule-LLM⊣ComplianceGovernor** を据え、charter（propose→draft のみ・
共有は常に人間・テナント分離）を守る。

actor は「下書き（イベント内容の提案）を書く」だけで、実際に共有（招待送信）
するのは常に人間承認後の ScheduleTarget port。actor が招待を送ることは設計上
ない（招待という *actuation* と、下書きという *proposal* の分離）。

## 1. 二つのフロー

```
ingest(record-op):  intake → record → END                       ; 観測。常時ON、無作動
assess(assess-op):  intake → advise → govern → decide → commit | hold | 人間承認
```

- **ingest**: `:event/register` — 活動(itonami activity)の due-at から機械的に
  記録された `calendar.model` イベントを ground fact として記録。LLM/governor/
  phase を通らない事実記録。
- **assess**: `:event/draft`(schedule-LLM 提案: title/agenda を既存の
  start/end/attendees の上に決定的に構成、effect は `:draft` 固定) /
  `:event/share`(共有は必ず人間)。

チャネル: `:request :context(:phase) :proposal :verdict :disposition :record :approval :audit`

### draft ≠ share — 「気軽な commit」と「常に人間の承認」

`:event/draft` の commit は **データ**（event に乗る下書き）で、外部への
effect が無い。phase 2/3 で clean+confident なら governor 通過即 commit して
よい（気軽な `git commit` 相当）。一方 `:event/share` は **外部 effect そのもの**
（招待送信）なので、governor の `stakes?` が常に true — phase に関わらず
`:request-approval` へ escalate し、人間が承認して初めて
`koyomi.scheduleport/share!`（ICS 生成 + Distributor 呼び出し）が呼ばれる
（`git merge` 相当、常に人間）。

`:event/draft` の commit時にも `koyomi.scheduleport/propose-revision!` を呼ぶ
（下書きの時点で「共有先」への proposal-id を記録しておく — 実 target 実装なら
ここでドラフト予定枠を確保する等に使える）。

## 2. 注入される依存（swap）

- **Store**（`koyomi.store/Store`）: `MemStore` ‖ `DatomicStore`（langchain.db、
  `:db-api` で実 Datomic Local / kotoba pod）。
- **Advisor**（`koyomi.coordllm/Advisor`）: `mock-advisor` ‖ `llm-advisor`
  （langchain.model）。破損応答は confidence 0 noop → governor が hold/escalate。
- **ScheduleTarget**（`koyomi.scheduleport/ScheduleTarget`）: `mock-scheduleport`
  ‖ 実装（ICS は koyomi 自身が組み立て、実配信は注入された Distributor fn が
  行う。live 未検証）。`share!` は承認後のみ呼ばれる。
- **Phase**（context `:phase 0..3`）: drafting の自律度のみ段階化。share は
  常に人間。

## 3. ComplianceGovernor（独立・propose のみ許可）

schedule-LLM は宛先の consent 状態もテナント境界も no-actuation charter も
知らないので、EAVT 上の規則として **独立**に提案を *棄却* し HOLD に落とせる
別系統である必要がある。

| op | HARD | 常に人間? |
|---|---|---|
| `:event/draft` | no-actuation(effect=`:draft`) / tenant-isolation | いいえ(phase≥2で自動可。ただし first-contact? attendee があれば常に人間) |
| `:event/share` | consent-required(全 attendee が `:blocked` でない) / tenant-isolation | **常に** |

SOFT: confidence floor(<0.6) → escalate。ダブルブッキング
（`calendar.model/overlaps?` による既存イベントとの時刻重複 + attendee/resource
共有）→ escalate（hard にはしない — 意図的な同時刻イベントもあり得るため）。

`:first-contact? true` な attendee は tayori の contact モデルと同じ意味
（送信/共有を一度もしたことがない相手）だが、koyomi では hard にはせず
high-stakes に倒す（`:event/draft` の時点でも人間承認を要求する）— まだ
関係が無い相手を含む予定は、下書き自動 commit の対象から外れる。

## 4. Phase 0→3

| phase | draft | share |
|---|---|---|
| 0 ingest-only | 発行しない(hold) | — |
| 1 assisted | 常に人間 | 常に人間 |
| 2 assisted-draft | clean+confidentで自動commit | 常に人間 |
| 3 supervised | 同上 | **常に人間**(phaseに関わらず不変) |

## 5. 台帳（append-only）

`:t` タグ: `:recorded`(ingest) / `:coordllm-proposal`(advise trace) /
`:koyomi-hold`(HARD違反) / `:approval-requested`(escalate) /
`:human-signoff` / `:signoff-rejected` / `:committed`。「いつ・どのイベントの・
どの根拠で・誰が承認して共有したか」が不変に残る。

## 6. calendar.model との境界

`kotoba-lang/calendar`（`calendar.model`）は event の EDN モデル
（:calendar/id/title/start/end/attendees/links）と `overlaps?` を提供する
pure data ライブラリで、ICS export・招待送信・同意管理・governor の概念は
一切持たない（実測確認済み）。koyomi は calendar.model を **要求するだけで
再実装しない** — event content は draft の `:content` に verbatim で保持し、
ICS 文字列の組み立て（`koyomi.scheduleport/ics-string`）と共有時の
compliance 判断（governor）だけを koyomi 側が担う。

## 7. 参照

- 90-docs/adr/2607062010-kotoba-lang-koyomi-schedule-actor.md（superproject
  側の正本 ADR — Context/Decision/Consequences の全文）
- `../kekkai/docs/DESIGN.md` / `../tayori/docs/DESIGN.md`（同型 actor の直近の手本）
- ADR-2607061500（tayori — consent-required HARD invariant の先行実装）
