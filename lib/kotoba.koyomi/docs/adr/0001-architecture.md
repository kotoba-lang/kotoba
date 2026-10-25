# ADR-0001: koyomi — schedule-LLM を ComplianceGovernor で封じた予定共有制御面

- Status: Accepted (2026-07-06)
- 関連: kekkai ADR-0001（coord-LLM⊣TailnetGovernor、ネットワーク制御面版）、
  tayori ADR-0001（reply-LLM⊣ComplianceGovernor、通信文下書き版）、
  superproject 側の正本 90-docs/adr/2607062010-kotoba-lang-koyomi-schedule-actor.md
- 鏡像: 本 ADR は kekkai/tayori の **予定共有版ミラー**。あちらは
  「coord-LLM を TailnetGovernor で封じる」「reply-LLM を ComplianceGovernor
  で封じる」、こちらは「schedule-LLM を ComplianceGovernor で封じる」。

## 課題

`cloud-itonami` の営業・面談・取締役会・監査イベント等を、関係者に予定として
共有する手段が無い。`kotoba-lang/calendar` は既に event を pure EDN で保持する
portable なモデルを持つが、ICS export・招待送信・同意管理・governor の概念は
一切無い（実測確認済み）。だがここに知能（LLM）を素朴に据えると、consent の
無い相手への共有・別テナントの活動から生まれた予定の混入・「もう共有した」
という自己申告を鵜呑みにする経路ができてしまう。モデルの目的関数に「宛先の
consent 状態」「テナント境界」「no-actuation charter」は入っていない。

しかも actor が**実際に共有(招待送信)まで作動**すると、誤りが即座に相手への
招待として実体化する。したがって課題は「LLM で予定を書く」ことではなく、
**「提案器(schedule-LLM)を信頼境界の内側に封じ込め、大胆な下書きは書かせつつ、
*コンプライアンス的に閉じた* draft だけを commit し、実共有は常に人間承認後の
ScheduleTarget port にやらせる」**こと。

## 決定

### 1. schedule-LLM は封じ込め、直接 share しない

schedule-LLM は *proposal*（イベント内容: title/agenda を既存の
start/end/attendees の上に構成したもの）のみを返す助言者。出力は必ず独立した
`ComplianceGovernor` を通す。単一の不変条件: **actor は ComplianceGovernor が
拒否する共有を決して行わない。**

### 2. draft の commit と share の commit を非対称に扱う

draft の commit はデータ（気軽な `git commit`）— phase 2/3 で clean+confident
なら govern 通過即 commit してよい（ただし first-contact な attendee がいれば
常に人間 — まだ関係が無い相手を含む予定は自動化の対象から外れる）。share は
外部 effect そのもの（`git merge` 相当）— governor の high-stakes フラグにより
**phase に関わらず常に人間承認**を経由する。詳細は `../DESIGN.md` の表。

### 3. ScheduleTarget は protocol、ICS 生成は koyomi 自身が持つ

`koyomi.scheduleport/ScheduleTarget`（`fetch-event`/`propose-revision!`/
`share!`）は protocol。`calendar.model` には ICS export の概念が無いため、
RFC 5545 の VCALENDAR/VEVENT 文字列組み立ては `koyomi.scheduleport/ics-string`
が持つ。既定は mock、実装は I/O 注入（Distributor fn）で live 未検証のまま
追加できる。

### 4. ダブルブッキングは SOFT — hard にしない

`calendar.model/overlaps?`（既存の実装済み interval-overlap 関数）を使い、
同一 attendee/resource が重複する既存イベントを検知したら escalate する。
意図的な同時刻イベント（例: 複数の並行トラック）もあり得るため、hard
violation にはしない — 人間が一度見れば足りる。

## Consequences

- (+) 共有(招待送信)が「ComplianceGovernor が拒否する経路では絶対に起きない」
  ことが型で保証される。
- (+) draft と share の非対称性が、kekkai/tayori と同じ「PR/commit スタイル」
  を予定共有ドメインにも一貫して適用する。
- (+) calendar.model を再実装せず、event データモデルの単一の真実源を保つ。
- (−) 実 Distributor(実メール/カレンダー招待 API)は OAuth/token 前提で live
  未検証。既定の mock で runnable・testable。

## 参照

- `../DESIGN.md`（ops/HARD invariant/phase の一覧表）
- `orgs/kotoba-lang/kekkai` / `orgs/kotoba-lang/tayori` docs/adr/0001-architecture.md（同型の直近の手本）
- 90-docs/adr/2607062010-kotoba-lang-koyomi-schedule-actor.md（superproject
  正本、Context/Decision/Consequences 全文）
