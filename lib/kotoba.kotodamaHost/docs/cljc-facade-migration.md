# facade / 実行面の一本化（JUN-133）— TS SDK prune 済み

**owner 決定（2026-10-20）**: TS SDK は prune して **kotoba + amu selfhost** に
一本化する。compat 維持（RESTORATION.md 方針）は取り下げ。

## 実施（本変更）

- `sdk/kotodama-host-sdk/`（TS SDK 全 108 ファイル）を **削除**。
- ソースカタログ（`resources/kotodama_host/sdk_sources.edn`）を kotoba 側の
  生成物（`src/kotodama/host_facade.cljc`）に更新。
- parity の TS SDK レグを prune 検証に差替え（facade ↔ boundary.edn ↔ WIT
  の 3 者一致は維持）。

## 体制（変更後）

```
sdk_facade.edn（権威）
  │  scripts/gen-sdk-facade.cljk（決定的生成）
  ▼
src/kotodama/host_facade.cljc（生成物）
  │  kbb / amu
  ▼
実行面: kotoba + amu selfhost（kototama-browser-host-v1）
```

- guest/host 契約の権威は EDN/CLJC（boundary.edn / sdk_facade.edn / WIT）。
- 実行は amu selfhost（typed ホストの本筋 — Chicory 二重実装なし）。
- appview 8 本（app-itonami / app-editor / app-kenkyusha / app-playwright /
  app-briefing / llm / repository / os-messaging）は TS SDK import を
  **amu selfhost 経由の面に差し替える**のが残作業。TS SDK はもう無いので
  8 本は現状 bundle できない（prune を先行させた owner 決定の了解事項）。

## 残スライス

1. appview 8 本の import 差替え（amu selfhost 経由）+ bundle 検証。
2. defence-handlers.ts 等の 8 本外の消費者の扱い（同じく amu selfhost 面へ）。
