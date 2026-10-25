# ADR-0001: tayori — reply-LLM を ComplianceGovernor で封じた通信文下書き制御面

- Status: Accepted (2026-07-06)
- 関連: kekkai ADR-0001（coord-LLM⊣TailnetGovernor、ネットワーク制御面版）、
  gijiroku（scribe-LLM⊣PrivacyGovernor、meeting minutes 版）、
  superproject 側の正本 90-docs/adr/2607061500-kotoba-lang-tayori-correspondence-actor.md
- 鏡像: 本 ADR は kekkai/gijiroku の **通信文下書き版ミラー**。あちらは
  「coord-LLM を TailnetGovernor で封じる」「scribe-LLM を PrivacyGovernor で封じる」、
  こちらは「reply-LLM を ComplianceGovernor で封じる」。

## 課題

email/Slack/WhatsApp の返信下書きと git 文書の改訂案を、複数チャネル横断で
1つの actor に集約したい。だがここに知能（LLM）を素朴に据えると、consent の無い
相手への送信・機微情報の無編集な引用・「もう送った」という自己申告を鵜呑みに
する経路ができてしまう。モデルの目的関数に「宛先の consent 状態」「redaction
要件」「no-actuation charter」は入っていない。

しかも actor が**実際に送信/publish まで作動**すると、誤りが即座に相手への
メッセージや公開文書として実体化する。したがって課題は「LLM で返信を書く」こと
ではなく、**「提案器(reply-LLM)を信頼境界の内側に封じ込め、大胆な下書きは書か
せつつ、*コンプライアンス的に閉じた* draft/revision だけを commit し、実送信/
publish は常に人間承認後の Channel/DocTarget port にやらせる」**こと。

## 決定

### 1. reply-LLM は封じ込め、直接 send/publish しない

reply-LLM は *proposal*（返信文・改訂差分）のみを返す助言者。出力は必ず独立した
`ComplianceGovernor` を通す。単一の不変条件: **actor は ComplianceGovernor が
拒否する送信/publish を決して行わない。**

### 2. draft/revision の commit と send/publish の commit を非対称に扱う

draft/revision の commit はデータ（気軽な `git commit`）— phase 2/3 で
clean+confident なら govern 通過即 commit してよい。send/publish は外部
effect そのもの（`git merge` 相当）— governor の high-stakes フラグにより
**phase に関わらず常に人間承認**を経由する。詳細は `../DESIGN.md` の表。

### 3. Channel/DocTarget は protocol、実装は差し替え可能

`tayori.channel/Channel`（Email/Slack/WhatsApp）と `tayori.docport/DocTarget`
（git PR）はどちらも protocol。既定は mock、実クライアントは I/O 注入
（`:http-fn` `:json-write` `:json-read` `:creds`）で live 未検証のまま追加できる。

## Consequences

- (+) 送信/publish が「ComplianceGovernor が拒否する経路では絶対に起きない」
  ことが型で保証される。
- (+) draft と send/publish の非対称性が、オーナーが要望した「PR/commit
  スタイル」をそのまま actor の語彙に落とし込む。
- (−) 実チャネル(Gmail/Slack/WhatsApp/GitHub)は OAuth/token 前提で live 未検証。
  既定の mock で runnable・testable。

## 参照

- `../DESIGN.md`（ops/HARD invariant/phase の一覧表）
- `orgs/kotoba-lang/kekkai` docs/adr/0001-architecture.md（同型の直近の手本）
- 90-docs/adr/2607061500-kotoba-lang-tayori-correspondence-actor.md（superproject
  正本、Context/Decision/Consequences 全文）
