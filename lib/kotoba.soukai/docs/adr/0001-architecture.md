# ADR-0001: soukai — secretary-LLM を ResolutionGovernor で封じた株主総会運営制御面

- Status: Accepted (2026-07-12)
- 関連: koyomi ADR-0001（schedule-LLM⊣ComplianceGovernor、予定共有版）、
  kekkai ADR-0001（coord-LLM⊣TailnetGovernor、ネットワーク制御面版）、
  tayori ADR-0001（reply-LLM⊣ComplianceGovernor、通信文下書き版）、
  superproject 側の正本 90-docs/adr/2607121700-kotoba-lang-soukai-agm-actor.md
- 鏡像: 本 ADR は koyomi/kekkai/tayori の **株主総会運営版ミラー**。あちらは
  「schedule-LLM を ComplianceGovernor で封じる」「coord-LLM を
  TailnetGovernor で封じる」「reply-LLM を ComplianceGovernor で封じる」、
  こちらは「secretary-LLM を ResolutionGovernor で封じる」。

## 課題

日本の株式会社の株主総会の招集〜決議確定〜議事録確定を扱う専用の設計は、
このワークスペースに存在しなかった（koyomi=日程共有、gijiroku=汎用議事録、
holdco=資本分配コンプライアンス、isic-8291=KYC/デューデリジェンス — いずれも
近傍だが目的が異なる。詳細は superproject 正本 ADR の Context 節）。だが
ここに知能（LLM）を素朴に据えると、招集通知の法定記載事項の欠落・法定期間を
下回る通知発送・電子提供義務の未充足という手続的コンプライアンス違反に加え、
**決議の可決/否決という法的に最も重い判断そのものを LLM の自由裁量に委ねて
しまう**という、他の姉妹 actor には無い固有のリスクが生じる。モデルの
目的関数に「定足数」「決議要件の正確な分数」「基準日名簿との整合」は入って
いない。

したがって課題は「LLM で招集通知/議事録を書く」ことだけでなく、**「決議結果
という一点だけは、LLM の裁量から完全に切り離し、決定論的関数の出力を verbatim
で引用させる」**構造を、koyomi/kekkai/tayori と同じ「封じ込め + 独立 governor
+ 不変台帳」パターンの中に据えること。

## 決定

### 1. secretary-LLM は封じ込め、直接発送/確定しない

secretary-LLM は *proposal*（招集通知案・決議結果の説明文・議事録案）のみを
返す助言者。出力は必ず独立した `ResolutionGovernor` を通す。単一の不変条件:
**actor は ResolutionGovernor が拒否する発送/確定/記録を決して行わない。**

### 2. 決議結果は `soukai.tally` という純粋関数の verbatim 引用のみ

`soukai.tally/outcome-of` は LLM/governor/store への依存が一切無い純粋関数で、
定足数・決議要件を正確な分数の相互乗算で判定する（浮動小数点除算は使わない
— 法的拘束力のある計算での丸め誤差を排除するため）。secretary-LLM の
`:resolution/finalize` 提案の `:outcome` は必ずこの関数の出力そのもの。
`ResolutionGovernor` の `resolution-mismatch` HARD check は、**governor
自身が同じ計算を独立に再実行**し、proposal の主張と食い違えば即 hold
（人間承認をも経由させない — un-overridable）。

### 3. draft の commit と send/finalize の commit を非対称に扱う

draft/finalize(説明文)の commit はデータ（気軽な `git commit`）— phase 2/3で
clean+confidentなら govern 通過即 commit してよい。send(招集通知の実発送)・
finalize(議事録の法的確定)は外部effect/法的確定そのもの（`git merge`相当）
— governor の high-stakes フラグにより **phase に関わらず常に人間承認**を
経由する。詳細は `../DESIGN.md` の表。

### 4. NoticeTarget は protocol、この版は mock のみ

`soukai.noticeport/NoticeTarget`（`fetch-convocation`/`propose-revision!`/
`send!`）は protocol。この R0 は実配信を持たない — `mock-noticeport` が唯一の
実装で、依存を増やさず（`kotoba-lang/mailer` 等を追加しない）孤立した scratch
ディレクトリからでもビルド・テスト可能に保つ。実配信の追加は別 follow-up。

## Consequences

- (+) 発送/確定(招集通知送付・議事録の法的確定)が「ResolutionGovernor が
  拒否する経路では絶対に起きない」ことが型で保証される。
- (+) 決議の可決/否決/定足数未達という最も重い判断が、`soukai.tally` という
  決定論的関数から常に導かれる（`resolution-mismatch` HARD gate による
  構造的強制）。
- (+) koyomi/gijiroku/holdco/isic-8291/teianをreimplementせず、明示的な
  非対象として境界を切ることで、実装対象を「総会固有の法定手続」に絞れる。
- (-) 実 NoticeTarget(実郵送/実メール等)は本 R0 の範囲外。既定の mock で
  runnable・testable。
- (-) R0 は日本・法定原則のみ(定款によるカスタマイズは非対応)。

## 参照

- `../DESIGN.md`（ops/HARD invariant/phase の一覧表、隣接 actor との境界）
- `orgs/kotoba-lang/koyomi` / `kekkai` / `tayori` の
  `docs/adr/0001-architecture.md`（同型の直近の手本）
- 90-docs/adr/2607121700-kotoba-lang-soukai-agm-actor.md（superproject
  正本、Context/Decision/Consequences 全文）
