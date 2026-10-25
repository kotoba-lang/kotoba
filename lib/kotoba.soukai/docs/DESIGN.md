# soukai Actor Design — secretary-LLM as a contained intelligence node

株主総会の招集〜決議確定〜議事録確定を扱う actor。koyomi（schedule-LLM⊣
ComplianceGovernor）/ kekkai（coord-LLM⊣TailnetGovernor）/ tayori（reply-LLM⊣
ComplianceGovernor）と同型に **secretary-LLM⊣ResolutionGovernor** を据え、
charter（propose→draft のみ・発送/確定は常に人間・決議結果は決定論的関数の
verbatim 引用のみ）を守る。

actor は「下書き（招集通知案・決議結果説明・議事録案）を書く」だけで、実際に
招集通知を発送する/議事録を確定するのは常に人間承認後の NoticeTarget port /
commit。決議の可決/否決/定足数未達という結果そのものは `soukai.tally` という
純粋関数の出力を常に verbatim で引用し、LLM が独自の判定を述べることは
governor によって構造的に禁止される。

## 1. 二つのフロー

```
ingest(record-op):  intake → record → END                       ; 観測。常時ON、無作動
assess(assess-op):  intake → advise → govern → decide → commit | hold | 人間承認
```

- **ingest**: `:meeting/register` `:record-date/snapshot`（基準日の株主名簿
  スナップショット）`:agenda/register`（決議種別込み — 取締役会等の決議に
  基づき機械的に登録、LLM は判定しない）`:vote/record`（個別の議決権行使）。
- **assess**: `:convocation/draft`（secretary-LLM が招集通知案を提案、effect
  は `:draft` 固定）/ `:convocation/send`（常に人間）/ `:resolution/finalize`
  （secretary-LLM は `soukai.tally/outcome-of` の計算結果をそのまま引用す
  るだけ — 独自の可決/否決判定はしない）/ `:minutes/draft`（施行規則72条
  記載事項に沿った議事録案）/ `:minutes/finalize`（常に人間）。

チャネル: `:request :context(:phase) :proposal :verdict :disposition :record :approval :audit`

### draft ≠ send/finalize — 「気軽な commit」と「常に人間の承認」

`:convocation/draft` / `:resolution/finalize` / `:minutes/draft` の commit
は **データ**（提案/説明文が乗るだけ）で、外部への effect が無い。phase 2/3
で clean+confident なら governor 通過即 commit してよい（気軽な
`git commit` 相当）。一方 `:convocation/send`（招集通知の実発送）と
`:minutes/finalize`（議事録の法的確定）は **外部 effect / 法的確定そのもの**
なので、governor の `stakes?` が常に true — phase に関わらず
`:request-approval` へ escalate し、人間が承認して初めて
`soukai.noticeport/send!`（通知テキスト生成 + Distributor 呼び出し）が
呼ばれる（`git merge` 相当、常に人間）。

`:convocation/draft` の commit時にも `soukai.noticeport/propose-revision!`
を呼ぶ（下書きの時点で「発送先」への proposal-id を記録しておく）。

## 2. 注入される依存（swap）

- **Store**（`soukai.store/Store`）: `MemStore` ‖ `DatomicStore`（langchain.db、
  `:db-api` で実 Datomic Local / kotoba pod）。
- **Advisor**（`soukai.secretaryllm/Advisor`）: `mock-advisor` ‖ `llm-advisor`
  （langchain.model）。破損応答は confidence 0 noop → governor が hold/escalate。
- **NoticeTarget**（`soukai.noticeport/NoticeTarget`）: `mock-noticeport` が
  この R0 で唯一の実装（実配信は無い — README/ADR-2607121700 §6 参照）。
  `send!` は承認後のみ呼ばれる。
- **Phase**（context `:phase 0..3`）: drafting/finalizing の自律度のみ段階化。
  send/finalize は常に人間。

## 3. ResolutionGovernor（独立・propose のみ許可）

secretary-LLM は法定の招集期間も電子提供義務も決議の定足数/決議要件計算も
tenant 境界も no-actuation charter も知らないので、EAVT 上の規則 + `soukai.
tally` の決定論的関数として **独立**に提案を *棄却* し HOLD に落とせる別
系統である必要がある。

| op | HARD | 常に人間? |
|---|---|---|
| `:convocation/draft` | no-actuation(effect=`:draft`) / tenant-isolation | いいえ(phase≥2で自動可) |
| `:convocation/send` | no-actuation / tenant-isolation / **notice-period-gate**(会社法299条1項) / **electronic-provision-gate**(325条の3) | **常に** |
| `:resolution/finalize` | no-actuation / tenant-isolation / **resolution-mismatch**(soukai.tally の計算結果と proposal の :outcome が不一致なら hard — 単一不変条件の核) | いいえ(phase≥2で自動可。ただし close-margin なら SOFT escalate) |
| `:minutes/draft` | no-actuation / tenant-isolation | いいえ(phase≥2で自動可) |
| `:minutes/finalize` | no-actuation / tenant-isolation / **minutes-legal-fields-gate**(施行規則72条の6項目が揃っているか) | **常に** |

no-actuation は soukai では koyomi と異なり **全 assess op に一律適用**
（`:convocation/send`/`:minutes/finalize` も proposal の `:effect` は常に
`:draft` でなければならない — 実際の発送/確定を主張することは、それが
たとえ pass-through 提案であっても許されない）。

SOFT: confidence floor(<0.6) → escalate。close-margin(`:resolution/finalize`
のみ、`:ordinary-resolution`/`:special-resolution` の for/(for+against) 比が
閾値の±5ポイント以内) → escalate（hard にはしない — 数式は曖昧ではないが、
僅差の実世界判断は人間の目を通す方が慎重、という運用上のヒューリスティック）。

## 4. Phase 0→3

| phase | draft/finalize(説明文) | send/finalize(発送・法的確定) |
|---|---|---|
| 0 ingest-only | 発行しない(hold) | — |
| 1 assisted | 常に人間 | 常に人間 |
| 2 assisted-draft | clean+confidentで自動commit | 常に人間 |
| 3 supervised | 同上 | **常に人間**(phaseに関わらず不変) |

## 5. 台帳（append-only）

`:t` タグ: `:recorded`(ingest) / `:secretaryllm-proposal`(advise trace) /
`:soukai-hold`(HARD違反) / `:approval-requested`(escalate) /
`:human-signoff` / `:signoff-rejected` / `:committed`。「いつ・どの総会/
議案の・どの根拠で・誰が承認して発送/確定したか」、決議については「どの
tally 計算結果に基づき記録したか」が不変に残る。

## 6. 隣接 actor/repo との境界

`soukai` は株主総会運営の**法定手続そのもの**（招集通知の法的記載事項・
基準日/議決権集計・決議要件・議事録の法定様式）にスコープを絞り、隣接領域は
既存 actor/repo をそのまま消費する（reimplement しない）:

| 隣接領域 | 担当 | soukai との境界 |
|---|---|---|
| 日程調整・カレンダー招待 | `koyomi` | soukai は招集通知の**法的記載事項**（開催日時・場所・目的事項・通知発送日・電子提供URL）のみ扱う。日程共有そのものは koyomi を再利用する（follow-up、本 R0 では未配線） |
| Zoom/Meet/Teams の録音・文字起こし | `gijiroku` | オンライン開催時の会議記録メカニズムは gijiroku の守備範囲。soukai の `:minutes/draft` は**法定様式**（施行規則72条）の確定のみを扱い、議事の逐語録・文字起こしは持たない |
| 剰余金分配・実質的支配者開示 | `holdco`(cloud-itonami-isic-6420) | 資本分配コンプライアンスは別 governor・別事実カタログ。soukai は決議手続そのものだけを扱う |
| 法人・役員のKYC/デューデリジェンス | `cloud-itonami-isic-8291` | 第三者への開示ではなく自社ガバナンス機能。無関係 |
| 決算説明会等の資料作成 | `teian` | briefing-actor の守備範囲。狭義のIR全般は soukai の対象外(follow-up) |

`soukai.tally`（決定論的集計）は soukai 固有の新規実装 — 隣接 actor に
相当機能は無い。

## 7. 参照

- 90-docs/adr/2607121700-kotoba-lang-soukai-agm-actor.md（superproject
  側の正本 ADR — Context/Decision/Consequences の全文）
- `../koyomi/docs/DESIGN.md`（二流路StateGraph・port注入・Phase 0→3の直近の手本）
- `orgs/cloud-itonami/cloud-itonami-isic-6420/src/holdco/facts.cljc`（G2引用
  カタログの直近の手本 — `soukai.facts` はこの規律を踏襲）
