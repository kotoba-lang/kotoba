# etzhayyim-project-hub App migration

このディレクトリは `legacy-runtime` 実装を残したまま、App 版を段階移行するための配置先です。

## 対象 App services

- `project-hub-qk6cjn0l`

## App 実装方針

- 各 service は `projects/*/wasm/*-component` として順次実装。
- 既存 App runtime は互換運用のため維持。
- HTTP/cron/job エンドポイントから優先して移植。

## 実装済みコンポーネント

- `hub-mcp-component` (`project-hub-qk6cjn0l` 対応)
  - `POST /api/mcp`, `POST /{nanoid}/api/mcp`
  - GitHub REST 互換サブセットを MCP `hubetzhayyim` ツールで提供
