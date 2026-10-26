# appview 差替え面の棚卸し（JUN-133 — TS SDK prune 後の残作業）

TS SDK（`@etzhayyim/kotoba-kotodama-host-sdk`）は prune 済み（2026-10-20）。
appview 8 本はこの import を持つため現状 bundle できない。本ファイルは
**amu selfhost（kototama-browser-host-v1）側が用意すべき面の正確な棚卸し**。
実測（2026-10-20、各 repo の `appview/*/src/app.ts` の import 簿から）。

## appview ごとの import 面

| appview | import 面 |
|---|---|
| app-itonami (`itonami-it0n4m1x`) | createWorkerExport, nowISO, nsid, asAgentTool, withCapabilityTags |
| app-playwright (`…playwright-pl4y1t8r`) | asAgentTool, createKyselyDb, createWorkerExport, withCapabilityTags, type HostSDK, nowISO, str, genID, nsid |
| repository (`…repository-r3p0s1t0`) | asAgentTool, createKyselyDb, createWorkerExport, withCapabilityTags, type HostSDK, nowISO, str, nsid |
| app-editor (`…editor-ed1t0r00`) | nowISO, rlsDefaults, withCapabilityTags, withOCELEvent, resolveModelId, type HostSDK, nsid, parseLexiconInput |
| app-briefing (`…briefing-w3olw1pf`) | type HostSDK, resolveHeartbeatCadence, createCadenceState, createInboxBuffer, decodeJson, genID, nsid, parseLexiconInput |
| os-messaging (`…os-messaging-0sm3sg01`) | nowISO, str, decodeJson, type AppDef, type HostSDK, type ComAtprotoSyncSubscribeReposCommit（+ 上部に数個） |
| app-editor 外: llm / app-kenkyusha | 未検出（app.ts の所在・import 形が違う — 要調査） |

## 差替え面の和集合（amu selfhost 側が用意するもの）

- **Worker/export 系**: createWorkerExport, asAgentTool, withCapabilityTags,
  withOCELEvent, rlsDefaults
- **ユーティリティ**: nowISO, nsid, genID, str, decodeJson
- **lexicon/heartbeat 系**: parseLexiconInput, resolveHeartbeatCadence,
  createCadenceState, createInboxBuffer
- **model 系**: resolveModelId
- **型**: HostSDK, AppDef, ComAtprotoSyncSubscribeReposCommit
- **DB 系**: createKyselyDb —— **不要**（ADR-2605111200 で Workers の DB 接続
  禁止。app-playwright / repository からは削除方向）。

## 次スライス

1. 型（HostSDK / AppDef / ComAtprotoSyncSubscribeReposCommit）の kotoba 側
   対応物の確定（WIT / EDN 権威の語彙に落とす）。
2. ユーティリティ群（nowISO / nsid / genID / str / decodeJson）を kotoba の
   生成 facade（host_facade 系）に載せる。
3. appview 1 本ずつ差替え + bundle 検証（app-itonami が最小（5 シンボル））。
