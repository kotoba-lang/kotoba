# ADR-0001: teian — deck-LLM を BriefingGovernor で封じた資料下書き制御面

- Status: Accepted (2026-07-06)
- 関連: kekkai ADR-0001（coord-LLM⊣TailnetGovernor、ネットワーク制御面版）、
  tayori ADR-0001（reply-LLM⊣ComplianceGovernor、通信文下書き版）、
  superproject 側の正本
  90-docs/adr/2607062000-kotoba-lang-teian-briefing-actor.md
- 鏡像: 本 ADR は kekkai/tayori の **資料下書き版ミラー**。あちらは
  「coord-LLM を TailnetGovernor で封じる」「reply-LLM を ComplianceGovernor
  で封じる」、こちらは「deck-LLM を BriefingGovernor で封じる」。

## 課題

営業/経営会議/取締役会向けの資料（デッキ・レポート・集計表）の下書きと配布を、
itonami activity 横断で1つの actor に集約したい。だがここに知能（LLM）を
素朴に据えると、テナント境界を越えた draft 生成・機微情報の無編集な引用・
「もう配布した」という自己申告を鵜呑みにする経路ができてしまう。モデルの
目的関数に「artifact のテナント」「redaction 要件」「no-actuation charter」
は入っていない。

しかも actor が**実際に配布まで作動**すると、誤りが即座に取締役会・経営会議
への実配布として実体化する。したがって課題は「LLM で資料を作る」ことでは
なく、**「提案器(deck-LLM)を信頼境界の内側に封じ込め、大胆な下書きは書か
せつつ、*テナント分離・redaction 済み* な draft だけを commit し、実配布
(publish)は常に人間承認後の DeckTarget port にやらせる」**こと。

## 決定

### 1. deck-LLM は封じ込め、直接 publish しない

deck-LLM は *proposal*（deck/doc/sheet EDN 案・confidence・cites・
redactions・declared tenant）のみを返す助言者。出力は必ず独立した
`BriefingGovernor` を通す。単一の不変条件: **actor は BriefingGovernor が
拒否する配布(publish)を決して行わない。**

### 2. draft の commit と publish の commit を非対称に扱う

draft の commit はデータ（気軽な `git commit`）— phase 2/3 で
clean+confident なら govern 通過即 commit してよい。publish は外部
effect そのもの（`git merge` 相当）— governor の high-stakes フラグにより
**phase に関わらず常に人間承認**を経由する。詳細は `../DESIGN.md` の表。

### 3. DeckTarget は protocol、content は slides.model の EDN そのもの

`teian.deckport/DeckTarget`（fetch-deck/propose-revision!/publish!）は
protocol。teian は独自のデッキ表現を作らず、content は
`kotoba-lang/slides` の `slides.model` が定義する workspace/deck/doc/sheet
EDN をそのまま保持する。既定は `mock-deckport`（決定的・in-memory）。
`publish!` は best-effort で `slides.office` の pptx export を試みるが、
実配布クライアント（メール/Slack 添付等）は本 repo に含めない — 各社 API
token 発行が前提で live 結合は未検証。

## Consequences

- (+) 配布(publish)が「BriefingGovernor が拒否する経路では絶対に起きない」
  ことが型で保証される。
- (+) draft と publish の非対称性が、オーナーが要望した「PR/commit
  スタイル」をそのまま actor の語彙に落とし込む。
- (+) `kotoba-lang/slides` の既存 EDN モデルをそのまま再利用し、teian 自身は
  独自のデータ表現を作らない（重複実装を避ける）。
- (−) 実配布(email/Slack等)の実クライアントは OAuth/token 前提で live
  未検証。既定の mock-deckport で runnable・testable。

## 参照

- `../DESIGN.md`（op/HARD invariant/phase の一覧表）
- `orgs/kotoba-lang/kekkai` docs/adr/0001-architecture.md、
  `orgs/kotoba-lang/tayori` docs/adr/0001-architecture.md（同型の直近の手本）
- 90-docs/adr/2607062000-kotoba-lang-teian-briefing-actor.md（superproject
  正本、Context/Decision/Consequences 全文）
