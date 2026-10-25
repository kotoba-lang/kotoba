# shoko Actor Design — archive-LLM as a contained intelligence node

書庫（ファイル/フォルダの保管・共有）を扱う actor。kekkai（coord-LLM⊣
TailnetGovernor）/ teian（deck-LLM⊣BriefingGovernor）/ koyomi（schedule-LLM⊣
ComplianceGovernor）と同型に **archive-LLM⊣ArchiveGovernor** を据え、charter
（propose→draftのみ・共有は常に人間・deny-by-defaultなACL・テナント分離）を
守る。アーキテクチャ的には kekkai の deny-by-default ACL 形（`kekkai.acl`、
`deny-by-default-violations`）と teian/koyomi の draft/publish 形のハイブリッド:
ファイル自体は `kotoba-lang/drive` の EDN をそのまま保持し、「誰と共有できるか」
は shoko 自身の grant 台帳が deny-by-default で判定する。

actor は「下書き（保管候補の提案）を書く」だけで、実際にアクセス権を付与する
（`:file/share`）のは常に人間承認後。actor が勝手にファイルを共有することは
設計上ない（下書きという *proposal* と、権限付与という *actuation* の分離）。
content は `kotoba-lang/drive` の `drive.model` EDN そのもの — shoko は独自の
ファイル表現を作らない。

## 1. 二つのフロー

```
ingest(record-op):  intake → record → END                       ; 観測。常時ON、無作動
assess(assess-op):  intake → advise → govern → decide → commit | hold | 人間承認
```

- **ingest**: `:file/register` — 既存ファイル/フォルダ（`drive.model` EDN +
  shoko自身が付与する `:tenant`）を ground fact として記録。LLM/governor/phase
  を通らない事実記録。
- **assess**: `:file/draft`（archive-LLM 提案: drive EDN content + confidence +
  cites + redactions、effect は `:draft` 固定）→ `:govern` → `:decide` →
  commit|escalate|hold。`:file/share`（principal への共有）は **常に人間承認**。

チャネル: `:request :context(:phase) :proposal :verdict :disposition :record :approval :audit`

### draft ≠ share — 「気軽な commit」と「常に人間の承認」

`:file/draft` の commit は **データ**（file に乗る下書き — drive.model EDN
content）で、外部への effect が無い。phase 2/3 で clean+confident なら
governor 通過即 commit してよい（気軽な `git commit` 相当）。一方
`:file/share` は **外部 effect そのもの**（principal へのアクセス権付与・
通知）なので、governor の `stakes?` が常に true — phase に関わらず
`:request-approval` へ escalate し、人間が承認して初めて
`shoko.archiveport/share!` が呼ばれる（`git merge` 相当、常に人間）。

`:file/draft` の commit 時に `shoko.archiveport/propose-revision!` も呼ぶ
（下書き候補の記録 — teian の `:deck/draft` が `deckport/propose-revision!`
を呼ぶのと同型）。

## 2. 注入される依存（swap）

- **Store**（`shoko.store/Store`）: `MemStore` ‖ `DatomicStore`（langchain.db、
  `:db-api` で実 Datomic Local / kotoba pod）。
- **Advisor**（`shoko.coordllm/Advisor`）: `mock-advisor` ‖ `llm-advisor`
  （langchain.model）。破損応答は confidence 0 noop → governor が
  hold/escalate。
- **ArchiveTarget**（`shoko.archiveport/ArchiveTarget`）: `mock-archiveport`
  のみを同梱（既定・決定的・in-memory）。`share!` は承認後のみ呼ばれ、注入
  された Distributor fn（既定 no-op）に実配信を委ねる。実 Distributor（メール/
  Slack 通知等）の live クライアントは本 repo に含めない。
- **Phase**（context `:phase 0..3`）: drafting の自律度のみ段階化。share は
  常に人間。

## 3. ArchiveGovernor（独立・propose のみ許可）

archive-LLM は grant 台帳の状態もテナント境界も no-actuation charter も
知らないので、EAVT 上の規則として **独立**に提案を *棄却* し HOLD に
落とせる別系統である必要がある。

| op | HARD | 常に人間? |
|---|---|---|
| `:file/draft` | subject存在(missing-file/missing-activity、独立・無条件) / no-actuation(effect=`:draft`) / tenant-isolation | いいえ(phase≥2で自動可) |
| `:file/share` | subject存在 / draft存在(missing-draft) / share-requires-acl(deny-by-default) / tenant-isolation(再検証) | **常に** |

SOFT: confidence floor(<0.6) → escalate。

- **subject-exists（missing-file / missing-activity）**: 参照する file/
  activity が store に存在しない場合、`content`/`tenant` の有無に関わらず
  必ず hard violation。**独立・無条件** — tenant-isolation 等の他チェックが
  「存在しないなら比較しようがないので素通り」してしまう経路を構造的に塞ぐ
  （koyomi の `missing-activity-violations` / teian の
  `missing-artifact-violations` / kekkai の `key-violations :no-node` と同じ
  教訓。koyomi の confirmed bug #2 — governor に subject 存在チェックが無く
  rogue tenant が素通りした — の再発防止として最初から実装）。
- **no-actuation**: `:file/draft` proposal の `:effect` は `:draft` のみ。
  実際のアクセス権付与は人間承認後、ArchiveTarget port のみが行う。
- **share-requires-acl（deny-by-default、kekkai.acl の写し、TENANT-SCOPED）**:
  `:file/share` の対象 principal が shoko 自身の `grant` 台帳に、共有対象
  file と **同じ tenant 内で** 一度も登場していないなら hard violation。
  「一度も vouch されていない principal への新規共有」を無条件で拒否する —
  kekkai の `deny-by-default-violations`（ACL grant のない到達edgeの拒否、
  src/dst の specific-pair でしか vouch しない）と同型。同じ tenant 内の
  **別の** file であれば新規 share を受けられる（正当なオンボーディング —
  例: alice は f-handbook への既存 grant により tenant
  `gftdcojp/cloud-itonami` で known になり、同じ tenant の別file
  f-contract への新規共有を受けられる）が、**別 tenant の grant は
  vouch にならない**（例: alice が tenant A でしか known でなくても、
  tenant B の file への共有は `:unregistered-principal` で hard hold）。
  "known" 判定に使う tenant は grant自体には持たせず、grant対象file の
  `:tenant` を都度 store 参照して解決する（`store/principal-known?`）。
  **修正済みの確認済みバグ**: 以前は「台帳全体のどこかに grant があれば
  known」という tenant 非依存の判定だったため、tenant A でしか known で
  ない principal に tenant B の file を `{:ok? false :violations []}`
  （= 違反ゼロ）で共有できてしまう権限昇格相当の穴があった。
- **tenant-isolation**: file 自身の登録済み `:tenant`（`:file/register` 時に
  記録）と、駆動する activity の `:repo` を**直接比較する純粋な store-vs-store
  チェック**（proposal が申告する値を信用しない）。draft時・share時のどちらで
  評価しても常に同じ強度 — teian の confirmed bug #2（`:deck/publish` が
  draft時のみ検証し publish時に再検証しない）の教訓を、そもそも proposal
  依存にしないことで最初から回避している。

## 4. TOCTOU 対策（koyomi confirmed bug #1 の教訓）

`shoko.operation`'s `commit-effects!` の `:file/share` 分岐は、**govern時点で
検証済みの `proposal` チャネル**（langgraph の checkpoint に乗り、
`:request-approval` の human-in-the-loop interrupt を越えて生き残る）の
`:content` をそのまま使い、commit時点で `store/draft-of` を**再読込しない**。
koyomi の confirmed bug #1（`:event/share` が commit 時点で store を再読込
する TOCTOU — governor が承認した内容と、人間が実際に承認した内容の間に
ずれが生じ得た）の再発防止として最初から実装。`governor_contract_test`の
`share-uses-governed-content-not-a-stale-commit-time-store-read` が、
承認 interrupt 待機中に store 側のdraft内容が変更されても、実際に
`share!` に渡る内容は govern時点でチェック済みのものだけであることを
証明する。

## 5. Phase 0→3

| phase | draft | share |
|---|---|---|
| 0 ingest-only | 発行しない(hold, :phase-disabled) | — |
| 1 assisted | 常に人間 | 常に人間 |
| 2 assisted-draft | clean+confidentで自動commit | 常に人間 |
| 3 supervised | 同上 | **常に人間**(phaseに関わらず不変) |

## 6. 台帳（append-only）

`:t` タグ: `:recorded`(ingest) / `:coordllm-proposal`(advise trace) /
`:shoko-hold`(HARD違反) / `:approval-requested`(escalate) /
`:human-signoff` / `:signoff-rejected` / `:committed`。「いつ・どのfileの・
どの根拠で・誰が承認して共有したか」が不変に残る。「いつ」= grant の
`:granted-at` は実コミット時は `store/real-now`（実時刻、epoch seconds）を
使う — `store/demo-now` はデモ/テストの決定的な種データ専用の固定値であり、
**`:now` が省略された実 `:file/share` request のフォールバックには使わない**
（修正済みの確認済みバグ: 以前は request に `:now` が無いとこの固定デモ時刻が
そのまま台帳に刻まれてしまい、監査台帳の「いつ」が静かに嘘になっていた）。

## 7. `shoko.model` — draft / grant / activity

- `draft` — `{:activity-id :file-id :content (drive.model file/folder EDN)
  :confidence :cites :redactions :status}`。`content` は
  `kotoba-lang/drive`（`drive.model`）の `file`/`folder` コンストラクタが
  作る EDN item をそのまま保持する — shoko は独自表現を作らない。
- `grant` — `{:principal :file-id :access #{:read} :granted-by
  :granted-at}` — shoko 自身の ACL 台帳（`drive.model` には ACL 概念が一切
  無いため — `acl|access-control|permission|share` を grep してゼロヒット、
  実測確認済み）。`(principal, file-id)` の組で `grant-id` によりキー化。
- `activity` — itonami activity（id/repo/title/status）。`:repo` が
  tenant-isolation の比較対象。

## 8. `kotoba-lang/drive` との境界

`kotoba-lang/drive`（`drive.model`）は file/folder の EDN モデル
（`:drive/id/kind/title/object-ref/media-type`、folder の
`:drive/children`）と `drive`/`folder`/`file`/`add-child`/`children` を
提供する pure data ライブラリで、ACL・共有・governor の概念は一切持たない
（実測確認済み）。shoko は drive.model を **要求するだけで再実装しない** —
file content は draft の `:content` に verbatim で保持し、ACL 判断
（governor）と grant 台帳の維持だけを shoko 側が担う。

## 9. 参照

- `90-docs/adr/2607062020-kotoba-lang-shoko-archive-scaffold.md`（superproject
  側の正本 ADR — Context/Decision/Consequences の全文）
- `../kekkai/docs/DESIGN.md`（deny-by-default ACL の手本）/
  `../teian/docs/DESIGN.md` / `../koyomi/docs/DESIGN.md`（draft/publish
  非対称性・TOCTOU対策・publish時再検証の直近の手本 — 独立レビューで見つかり
  修正済みのバグクラスの教訓元）
- `../drive/src/drive/model.cljc`（shoko が verbatim content として保持する
  file/folder EDN モデル）
