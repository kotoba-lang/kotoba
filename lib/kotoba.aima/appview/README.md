# etzhayyim-project-aima App migration

このディレクトリは `legacy-runtime` 実装を残したまま、App 版を段階移行するための配置先です。

## 対象 App services

- `aima-components-01o07is9`
- `aima-concierge-apcxyinv`
- `aima-matching-t3r312c5`

## App 実装方針

- 各 service は `projects/*/wasm/*-component` として順次実装。
- 既存 App runtime は互換運用のため維持。
- HTTP/cron/job エンドポイントから優先して移植。
