# ADR-0001: gijiroku — scribe-LLM を PrivacyGovernor で封じた会議記録 actor

- Status: Accepted (2026-07-03)
- 関連: langgraph-clj ADR-0001（Pregel superstep + interrupt + Datomic
  checkpoint）、kekkai ADR-0001（coord-LLM ⊣ TailnetGovernor、直近の同型実例）、
  gftd-talent-actor DESIGN.md（PolicyGovernor 保護属性ゲート）、
  ai-gftd-itonami DESIGN.md（CACAO 自己発行）
- 正本: superproject `90-docs/adr/2607031100-kotoba-lang-gijiroku-meeting-actor.md`
  （org 配置・org taxonomy 判断・cloud-itonami/cloud-manimani 消費経路を含む
  canonical な意思決定）。本ファイルはこの repo 内の実装詳細への短いポインタ。
- 追記（2026-07-03）: 下記1.の「bot 参加方式は charter 外」は ADR-0002 で
  覆した — `gijiroku.bot-join` として実装済み（`MeetingPlatform` を protocol
  にした設計のおかげで `operation.cljc`/`governor.cljc` は無変更）。詳細は
  ADR-0002 を参照。

## Context

cloud-itonami・cloud-manimani から使える、Zoom/Google Meet/Teams の会議を
録音・文字起こし・記録する共通 actor が必要（superproject ADR-2607031100）。

## Decision

`kotoba-lang/gijiroku` を scribe-LLM ⊣ PrivacyGovernor 型の単一 repo actor
として実装する。詳細設計は `docs/DESIGN.md`、実装は `src/gijiroku/*`、契約は
`test/gijiroku/*_test.clj` を参照。要点:

1. Platform port（Zoom/Google Meet/Teams、既定 mock）で録音・文字起こしを
   公式 API から取得。bot 参加方式は charter 外。
2. 二流路 StateGraph（ingest 常時 ON / assess は scribe-LLM proposal →
   PrivacyGovernor → phase gate）。
3. PrivacyGovernor HARD: consent-required / protected-content redaction /
   tenant-isolation / no-actuation。`:minutes/distribute` は常に人間承認。
4. Store は `MemStore`‖`DatomicStore`（`langchain.db` :db-api 駆動）で
   backend 非依存。CACAO 自己発行で kotobase.net にも接続可能。

## Consequences

superproject ADR-2607031100 の Consequences を参照（同一）。
