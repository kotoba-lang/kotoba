# 20-actors/kotoba-kotodama

Canonical path: `20-actors/kotoba-kotodama`

Directory layout:
- `sdk/kotoba-kotodama-host-sdk`
- `hosts/kotoba-kotodama-desktop-host`
- `hosts/kotoba-kotodama-kami-host`
- `inference/kotoba-kotodama-inference`
- `config/kotoba-kotodama-config`
- `py/src/kotodama/` — Python worker layer (29 etzhayyim-classified workers
  + 4 ingest modules + 4 substrate primitives are gate (a) execution targets;
  see Tranche F dossier)

## Tranche F gate (a) — per-worker RW-free port (OPEN execution item)

The Python files in `py/src/kotodama/` are the gate (a) execution targets
of ADR-2605212100 §2(a). As of 2026-05-21, the **patterns** are documented
but per-worker **code** is not committed to this repo. Operators (or agents)
porting a worker MUST:

1. Read the gate (a) checklist row for that worker:
   `90-docs/2605211949-gate-a-execution-checklist.md`
2. Follow the pattern recipe (§0 of the checklist) for the row's pattern.
3. Run the row's smoke test in a tmp `$ORGANISM_SQLITE_DIR`.
4. Commit + tick the checklist row.

6 patterns to choose from:

- **BeliefStore** (organism cluster, 8 workers) — uses
  `kotodama.primitives.active_inference_substrate.select_belief_store()`
  + per-actor SQLite at `$ORGANISM_SQLITE_DIR/{actor_did_sanitized}.db`.
- **Audit log** (tools_audit) — append-only `audit-{repo}.db` mirroring
  `vertex_repo_commit`.
- **Read-cache** (sixir) — SELECT-only `{module}-{actor}.db`; external
  ingest seeds the rows.
- **Primary store** (10 workers: hub/web4/oshiete/resources/omikuji/
  kareyanagi/kiyome/gov/narou/ge) — INSERT/SELECT/UPDATE/DELETE on
  `{module}-{actor}.db`.
- **worker_runtime + degraded stub** (4 zeebe-dep workers:
  blockchain/houbun/curpus2skill/site_common_crawl) — replaces vendor
  zeebe_worker_main import with `kotodama.worker_runtime`; ingest tasks
  delegate to per-actor ingest modules.
- **Ingest module** (4 modules: blockchain/houbun/curpus2skill/
  site_common_crawl + ingest.core) — RPC + per-actor SQLite + shared
  `ingest.core` orchestration spine.

Full Tranche F closure index: `90-docs/TRANCHE-F-INDEX.md`

⚠️ **DEPRECATED 2026-04-12 → REMOVED 2026-04-13**: SQL architecture fully removed. Use Kysely (`createKyselyDb(env.HYPERDRIVE)`) for graph reads and `com.etzhayyim.kagami.sql` for raw SQL. `sqlQuery*` host imports, `sql.ts`, Drizzle ORM, kagami SQL transpiler are archived.

**TS Native + Lexicon Contract アーキテクチャ (F-Plan 2026-04-13)。** Business logic = TS native (async/await 直接)。Host capability contract SSoT = `00-contracts/lexicons/com/etzhayyim/host/*.json` (36 lexicons across 20 groups)。`70-tools/scripts/contract/gen-host-client-from-lexicon.mjs` が typed TS client (`kotoba-kotodama-host-sdk/src/generated/host-client.ts`) を生成し、`kotoba-kotodama-host-sdk/src/host-dispatcher.ts` が NSID → in-process host 関数へルートする。WIT は T3 Container (wasmtime) 経路でのみ legacy 用途 — TS Native (DEFAULT) は `wit/world.wit` 不要。設計: `00-contracts/lexicons/com/etzhayyim/host/` (Lexicon contract SSoT) + `90-docs/atproto/260324-wit-lexicon-typed-alignment-design.md` (旧 migration doc)

| Mode | 構成 | Build | 用途 |
|---|---|---|---|
| **T1 MCP-Compose** | `actor-manifest.jsonld` → PDS Shared Executor → 12 MCP primitives | なし (0s) | ~260 data-ingestion/identifier apps。η=0.667。Worker 不要 |
| **T2 Hybrid** | `actor-manifest.jsonld` → ActorExecutorDO → MCP + sandboxed TS | なし (0s) | ~90 reactive pipeline apps。η=0.50。DO sandbox |
| **T3 TS Native (DEFAULT for custom)** | `src/app.ts` → `@etzhayyim/kotoba-kotodama-host-sdk` → esbuild → CF Worker (V8)。WIT = design-time contract | esbuild のみ (<1s) | ~27 apps (WebGPU/ML/FIDO2)。η≈0.91 |
| **T3 Container** | TS app / infra service → container image | container build | 128MB Worker 制約超過時のみ |

設計: `90-docs/260408-actor-executor-p5p3-architecture-design.md`

**SDK ロジックは `@etzhayyim/kotoba-kotodama-host-sdk` (TypeScript) に統一。** App lifecycle, routing, conversation, governance 自動登録は全て TS host SDK の Single Source。Lexicon JSON (`00-contracts/lexicons/`) が contract SSoT、TS dispatcher が runtime binding SSoT、RisingWave vertex/edge が declaration/projection SSoT を担う。

**改善**: async/await 直接使用可、jco/canonical-abi/wasm-tools 不要、Build <1s、Bridge 層 7→3、Guest LOC 4x 削減。

名称対応は [90-docs/260319-kotoba-kotodama-runtime-naming-map.md](/Users/junkawasaki/etzhayyim/etzhayyim-root/90-docs/260319-kotoba-kotodama-runtime-naming-map.md) を正とする。

## Architecture

## Default Topology

```
Browser / AppShell
  → CF Single Worker
    ├─ /_worker/health, /_worker/metrics  → instant edge response
    ├─ /uploads/*                          → CDN_R2 (immutable)
    ├─ /api/*, /health                     → TS handler (`src/app.ts` + host-sdk)
    │   ├─ W Protocol Event Stream (ComAtprotoRepoCreateRecord write → PDS, Kysely read → HYPERDRIVE RisingWave)
    │   └─ PDS_SERVICE (read + write, XRPC gateway)
    ├─ static assets (has .)               → Workers Assets (svelte/build/)
    └─ HTML pages (no .)                   → Hono router (host-sdk)
```

- Hono router (host-sdk) + TS business logic + OTEL を 1 Worker に統合する (Shannon 最適)
- `@etzhayyim/kotoba-kotodama-host-sdk` package が SDK ロジックの Single Source of Truth

### Single Worker (DEFAULT)

```
CF Single Worker
├─ Hono router (host-sdk)                → page routing / API
├─ Workers Assets                        → static assets (svelte/build/)
├─ TS handler (`src/app.ts`)              → business logic + W Protocol Event Stream
│   ├─ @etzhayyim/kotoba-kotodama-host-sdk           → App lifecycle, routing, auto-registration
│   ├─ PdsClient (sdk.pds)              → direct async PDS RPC (write)
│   └─ createKyselyDb(sql, env.HYPERDRIVE) → Kysely type-safe graph queries (read/write)
├─ OTEL access logging                  → R2 NDJSON
└─ PDS_SERVICE                         → atproto.etzhayyim.com (read + write, XRPC)
```

**CRITICAL**:

- Container、split worker、Service Binding hop は不要 (Shannon 冗長度 0%)
- **Worker mode は TS native。** `kotoba-kotodama-engine` (wasmtime) は Worker deploy path では不使用
- **128MB Worker memory 制約**: heavy apps は Container mode を使う
- **Bundle size**: TS 5-15MB (10MB compressed limit に注意)、>10MB は Container mode
- Operational data は W Protocol Event Stream が primary (ComAtprotoRepoCreateRecord for writes, G() for reads)。DO SQLite 直接使用禁止

## Crate Layout

| Crate / Package | 言語 | 役割 |
|---|---|---|
| **`@etzhayyim/xrpc`** | **TypeScript** | **XRPC Single Source** — NSID utilities (`collectionToLabel`/`expandCollection`/`nsidToFullMethod`)、Transport (`BindingTransport`/`BrowserTransport`/`SSRTransport`)、Auth (`ServiceAuth`/`SessionAuth`/`PublicAuth`)、Error (`WRPCError`/`parseResponse`)、Proxy factory (`procedure`/`query`)。0 外部依存。Lexicon JSON (`00-contracts/lexicons/`) → `70-tools/scripts/contract/gen-service-from-lexicon.mjs` → `service-generated.ts` (typed Connect-like funcs) を自動生成。Bluesky HTTP Reference 222/222 完全カバー |
| **`kotoba-kotodama-host-sdk`** | **TypeScript** | **SDK ロジック Single Source** — App lifecycle, command routing, conversation dispatch, Kysely query builder, governance 自動登録, PdsClient (direct async RPC), shared helpers, LLM module, embed HTML。app.ts が `createComponentHostSDK(env)` を export → generated entry が singleton cache + `sdk.handleRequest()` で全ルーティング (`/_commit`, `/_heartbeat`, `/_app/meta`, `?embed=1`, `/health`, XRPC) を処理。XRPC は `@etzhayyim/xrpc` に委譲。**Hono policy (2026-04-03)**: router-level `onError` + `notFound` を標準採用（`all("*")` 404 代替は禁止）。**Database**: `createKyselyDb(env.HYPERDRIVE)` → Kysely type-safe queries via Hyperdrive → RisingWave。**Shared helpers**: `str`, `num`, `nowISO`, `stripHTML`, `truncateText`, `decodeJson`, `genID`, `rlsDefaults`, `firstRow`。**LLM module**: `llm.ts` (`agentConverseAsync`, `llmAsk`, `llmCall`, `llmJson`)。**app.ts にローカルコピー定義禁止** — SDK import を使用。**SQL / Drizzle archived 2026-04-13** |
| `kotoba-kotodama-config` | Rust | generated TOML parser (source is `kotoba-kotodama.jsonld`) |

## Capability Topology (Lexicon + TS + RisingWave)

`capability` は 1 つの層ではなく、以下の 4 層で正規化する。

1. **Lexicon contract**
   `00-contracts/lexicons/` が NSID / input / output / permission-set の SSoT
2. **Declaration record**
   `actor-manifest.jsonld` / actor record / host capability declaration を AT Record 化して永続化
3. **RisingWave projection**
   declaration を `vertex_*` / `edge_*` に正規化し、queryable graph として扱う
4. **TS runtime binding**
   `host-dispatcher.ts` / `host-imports.ts` / app command registration が実行時の binding と policy hook を担う

この repo では `Lexicon` だけで capability runtime 全体は表現しない。`Lexicon` は contract、`TS` は binding、`RisingWave` は state/projection を担う。

### Capability normalization target

- actor declaration
  `actor-manifest.jsonld` / actor record → `vertex_actor`
- capability declaration
  `com.etzhayyim.agent.actorCapability` record → `vertex_capability`
- policy / governance declaration
  `com.etzhayyim.agent.governanceRule`, `com.etzhayyim.agent.roleBinding` → `vertex_policy`, `edge_actor_bound_role`, `edge_capability_requires_permission`
- relationship projection
  `edge_actor_has_capability`, `edge_capability_calls_capability`, `edge_capability_requires_permission`

`JSON-LD` は archive ではなく declaration source として扱う。ただし runtime query は `jsonld` 文字列ではなく Lexicon record + RisingWave projection を正とする。

## Host Capability Contract (Lexicon SSoT, F-Plan 2026-04-13)

**Host capability surface = `00-contracts/lexicons/com/etzhayyim/host/*.json`** が唯一の contract SSoT。WIT world.wit は T3 Container (wasmtime) 経路でのみ legacy 用途で残存。T3 TS Native (DEFAULT) では Lexicon-driven。

### File layout

```
00-contracts/lexicons/com/etzhayyim/host/
├── core/configGet.json,        logAppend.json
├── authn/verifyToken.json
├── authz/enforce.json
├── ipfs/publish.json
├── storage/putObject.json,     getObject.json
├── cdn/upload.json,            publicUrl.json
├── telemetry/emitMetric.json,  log.json
├── accessLog/record.json
├── ocel/emitEvent.json
├── pubsub/publish.json,        pull.json
├── secrets/get.json,           set.json,    delete.json
├── lock/tryLock.json,          unlock.json
├── virtualActor/invoke.json
├── llm/converse.json,          chat.json,   route.json,   react.json
├── activity/spawnParallel.json, awaitAll.json
├── identity/resolve.json,      listActors.json
├── capability/listOwn.json,    discover.json
├── conversation/createSession.json, sendMessage.json
├── governance/registerManifest.json, checkPolicy.json
├── invoke/call.json
```

各 lexicon は `x-hostImportsMethod` 拡張フィールドを持ち、host-imports.ts の対応メソッド名を指す (NSID → method 解決の SSoT)。

### Codegen pipeline (lex-cli analog, atproto pattern)

```
Lexicon JSON                      gen-host-client-from-lexicon.mjs              host-client.ts
com.etzhayyim.host.secrets.get   ───►   (70-tools/scripts/contract/)         ───►    secretsGet(input: {key:string})
                                                                                 → requireDispatcher().dispatch(NSID, input)
```

### Runtime dispatch (BindingTransport pattern)

```
app code                                   generated client                  host-dispatcher.ts            host-imports.ts
sdk.hostImports.secretsGet(key)            secretsGet({ key })               case HOST_NSID.secretsGet:    secretsGet(key): string|null
   (legacy, still works)        ───►  OR  setHostDispatcher(...)       ───►    return { found, value }  ───►   (existing impl)
                                            then secretsGet({ key })
```

### Phase / Migration state (2026-04-13)

| Phase | 状態 | 内容 |
|---|---|---|
| **Phase 1** | ✅ | 3 capability lexicon + codegen + dispatcher POC + 4 tests |
| **Phase 2** | ✅ | 36 host capability lexicon + dispatcher 全 case + generated host client / NSID types / PDS registry 更新 |
| **Phase 3** | ✅ | CLAUDE.md / deps.toml 改訂、Lexicon SSoT 公式化、WIT は T3 Container 経路のみ |
| Phase 4 (任意) | ⏳ | 各 app が `sdk.hostImports.*` 直接呼出 → generated `host-client.ts` import に段階的移行 (η を維持しつつコード可読性向上) |

### CRITICAL: 新規 host capability の追加手順

1. `00-contracts/lexicons/com/etzhayyim/host/{group}/{action}.json` を作成 (`x-hostImportsMethod` を必ず指定)
2. `node 70-tools/scripts/contract/gen-host-client-from-lexicon.mjs` で typed client 再生成
3. `kotoba-kotodama-host-sdk/src/host-dispatcher.ts` の switch に case を追加
4. `kotoba-kotodama-host-sdk/src/host-imports.ts` に実装を追加 (まだなければ)
5. capability declaration を永続化する必要がある場合は record lexicon / graph projection (`vertex_*`, `edge_*`) も追加
6. `pnpm exec vitest run` で host-sdk tests、必要なら graph / PDS 側 tests も確認

**禁止**: TS interface を先に書いて lexicon を後追いで作ること (Shannon η が下がる)。Lexicon が SSoT で、TS は派生物。

### Phase 4 Migration Pattern: app 側 host capability 呼出を generated client に切替

**Auto-wiring**: `createWorkerExport()` (実体は `createHostSDK()` in `index.ts`) が初期化時に `setHostDispatcher(createHostDispatcher(hostImports))` を自動実行する。app は明示的な dispatcher セットアップ不要。

**Before (legacy, sync, untyped)**:

```typescript
function invokeRemote(sdk: HostSDK, did: string, method: string, params: Record<string, unknown>): string {
  return str(sdk.hostImports.invoke(new TextEncoder().encode(JSON.stringify({ did, method, params }))));
}
```

**After (F-Plan Phase 4, async, Lexicon-typed)**:

```typescript
import { hostClient } from "@etzhayyim/kotoba-kotodama-host-sdk";

async function invokeRemote(_sdk: HostSDK, did: string, method: string, params: Record<string, unknown>): Promise<string> {
  const paramsBytes = new TextEncoder().encode(JSON.stringify(params));
  let paramsB64 = "";
  for (let i = 0; i < paramsBytes.length; i++) paramsB64 += String.fromCharCode(paramsBytes[i]);
  paramsB64 = btoa(paramsB64);

  const { result } = await hostClient.invokeCall({ did, method, params: paramsB64 });

  if (!result) return "";
  const bin = atob(result);
  const out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
  return new TextDecoder().decode(out);
}
```

**Migration steps per app**:
1. Add `hostClient` to the `@etzhayyim/kotoba-kotodama-host-sdk` import block
2. For each `sdk.hostImports.<method>(...)` callsite, find the corresponding NSID in `HOST_NSID` (or use the typed function from `hostClient.<camelCase>`)
3. Convert the helper function to `async`, return `Promise<...>`
4. Add `await` to all callers
5. If callers were previously sync (`function cmdX`) → change to `async function cmdX(...): Promise<unknown>`
6. The `sdk.app.command(name, (ctx, body) => cmdX(sdk, body), ...)` registration accepts `Promise<unknown>` naturally — no change needed
7. Run `pnpm exec vitest run` in `20-actors/kotoba-kotodama/sdk/kotoba-kotodama-host-sdk` to confirm SDK still passes 141+ tests

**Reference implementation**: `60-apps/etzhayyim-project-oshikatsu/appview/etzhayyim-wasm-oshikatsu-dyd3lr50/src/app.ts` migrated 2026-04-13. Single `invokeRemote` helper + 2 caller commands (`cmdSubscribe`, `cmdTip`) became async. No build break, no behavior change.

**Notes**:
- Migration is **strictly opt-in**. Apps that still use `sdk.hostImports.*` continue to work — the legacy path is preserved for backward compatibility.
- Apps that exclusively use `hostClient.*` get full type safety, NSID auto-completion, and JSDoc descriptions from lexicon.
- Bytes parameters (e.g. `params` for `invokeCall`) are base64-encoded at the lexicon boundary. Use `btoa(String.fromCharCode(...))` and `atob(...)` helpers.

### CRITICAL: WIT は禁止ではないが推奨でもない

- T3 TS Native (DEFAULT) で `wit/world.wit` を新規作成しない (Shannon 冗長度が上がる)
- 既存 app の `wit/world.wit` は build を壊さない限り archived in-place で OK (削除任意)
- T3 Container (wasmtime, ~5 apps のみ) は引き続き WIT を使用 — Lexicon 側を後追いで揃える義務なし
- `e7m actor build` の `validateKotodamaGovernanceImport` は `wit/world.wit` 不存在時に silent skip するので、新規 TS Native app は wit ディレクトリを作らないのが正解

## App Command Contract (F2, Lexicon SSoT, 2026-04-13)

**App commands (`sdk.app.command(nsid, handler, ...opts)`) の NSID も `00-contracts/lexicons/com/etzhayyim/apps/{app}/*.json` が SSoT。** TS コード側の NSID 文字列は **派生物**、`nsid()` helper または `LEXICON_NSID` 定数経由でアクセスするのが新規標準。

### Generated artifacts (`20-actors/kotoba-kotodama/sdk/kotoba-kotodama-host-sdk/src/generated/lexicon-nsid-types.ts`)

`70-tools/scripts/contract/gen-lexicon-nsid-types.mjs` が以下を出力 (2243 XRPC lexicons 時点: 903 query + 1340 procedure):

| エクスポート | 用途 |
|---|---|
| `KnownLexiconQueryNSID` / `KnownLexiconProcedureNSID` / ... | Union 型。Lexicon の `defs.main.type` から分類 |
| `KnownLexiconNSID` | 全種合体 Union |
| `StrictCommandNSID<N>` / `StrictQueryNSID<N>` | 厳格 type guard (未知 NSID で **compile error**)。**DEFAULT** for `sdk.app.command/query` |
| `LEXICON_NSID` | Frozen record。`LEXICON_NSID["com.etzhayyim.apps.foo.bar"] === "com.etzhayyim.apps.foo.bar"` |
| `LexiconNsid` | `keyof typeof LEXICON_NSID` |
| `nsid<N extends LexiconNsid>(n: N): N` | Tagged helper。未知 NSID を compile time で検出 |
| `LexiconInputMap` / `LexiconOutputMap` | NSID → input/output schema の TS 型マッピング (**2243 件**) |
| `LexiconInput<N>` / `LexiconOutput<N>` | Conditional type。任意の known NSID の I/O 型を抽出 |
| `LEXICON_INPUT_SCHEMA` | Runtime schema registry (F-Plan step 6): `parseLexiconInput()` の validation source |
| `LexiconRuntimeSchema` / `LexiconPrimitiveType` | Runtime validation types |

**Archived (2026-04-13)**: `AssertCommandNSID` / `AssertQueryNSID` loose-guard types。経緯 + 復元方法は `_archive/20-actors/kotoba-kotodama/sdk/kotoba-kotodama-host-sdk-legacy-nsid-assert-260413/README.md`。

### Strict-only command/query API (legacy loose path archived 2026-04-13)

| API | Type guard | 用途 |
|---|---|---|
| `sdk.app.command(name, handler, ...)` | `StrictCommandNSID<Name>` | **DEFAULT**。NSID が lexicon procedure に無ければ compile error |
| `sdk.app.query(name, handler)` | `StrictQueryNSID<Name>` | **DEFAULT**。NSID が lexicon query に無ければ compile error |
| `sdk.app.lexiconCommand(...)` | `StrictCommandNSID<Name>` | **Deprecated alias** — `command` と等価、codemod sweep 後に削除予定 |
| `sdk.app.lexiconQuery(...)` | `StrictQueryNSID<Name>` | **Deprecated alias** — 同上 |

**Codemod sweep completed 2026-04-13** (F-Plan F2): 198/198 apps migrated from string-literal NSID に移行済み。残る`lexiconCommand`/`lexiconQuery` 呼び出しも deprecated aliases として 1:1 forward、次回 codemod で `command`/`query` に戻す予定。

### Typed handler pattern (F2 DEFAULT for new code)

```typescript
import {
  createWorkerExport,
  nsid,
  parseLexiconInput,
  type LexiconOutput,
} from "@etzhayyim/kotoba-kotodama-host-sdk";

export default createWorkerExport((sdk) => {
  sdk.app.command(
    nsid("com.etzhayyim.apps.foo.bar"),                                   // ← compile error if lexicon missing
    async (ctx, body) => {
      const input = parseLexiconInput("com.etzhayyim.apps.foo.bar", body);
      //    ^^ typed as LexiconInput<"com.etzhayyim.apps.foo.bar"> + runtime schema validation
      //       (throws LexiconValidationError on missing/mistyped properties)
      const output: LexiconOutput<"com.etzhayyim.apps.foo.bar"> = {
        //  ^^ type auto-derived from the same lexicon output schema
        ok: true,
      };
      return JSON.stringify(output);
    },
  );
});
```

### Lexicon SSoT status (F-Plan F2 complete, 2026-04-13)

| Metric | 値 |
|---|---|
| Total lexicons | **2346** (2243 XRPC + 82 record + 21 permission-set) |
| Query NSIDs | 903 |
| Procedure NSIDs | 1340 |
| Apps migrated to strict `command`/`query` | **198 / 198** (100%) |
| Apps using `parseLexiconInput` runtime validator | 36 (early adopters, 495 call sites) |
| Stub lexicons enriched with inferred schemas | **1171 / 1765** (66%) — input + output + required |
| host-sdk tests | **165/165 ✓** |
| Shannon η (F2 app command surface) | **1.0** |

### Codegen pipeline (F-Plan F2)

| Script | 役割 |
|---|---|
| `gen-lexicon-nsid-types.mjs` | Lexicon JSON → `LEXICON_NSID` / `nsid()` / `LexiconInput`/`LexiconOutput` / `LEXICON_INPUT_SCHEMA` |
| `gen-host-client-from-lexicon.mjs` | `com.etzhayyim.host.*` lexicons → `host-client.ts` (BindingTransport dispatcher) |
| `gen-service-from-lexicon.mjs` | Full lexicon set → `service-generated.ts` (XRPC client, atQuery/atProcedure) |
| `bootstrap-app-lexicons.mjs` | app.ts から不明 NSID を抽出 → stub lexicon 自動生成 (冪等) |
| `f2-codemod.mjs` | `.command("...", ...)` → `.lexiconCommand(nsid("..."), ...)` |
| `infer-lexicon-schemas.mjs` | handler body 解析 → stub lexicon に input/output/required を書き戻し (destructure / generic / return / early-return guard patterns) |
| `parseLexiconInput-codemod.mjs` | `decodeJson(body, {})` → `parseLexiconInput("nsid", body)` (inline handler + single-use named fn) |
| `lib/lexicon-scan.mjs` | Shared lexicon scanning + JSON schema → TS type emission |

### CRITICAL: 新規 app command の追加手順

1. `00-contracts/lexicons/com/etzhayyim/apps/{app}/{action}.json` を作成 (type: procedure または query、input/output schema 定義)
2. `node 70-tools/scripts/contract/gen-lexicon-nsid-types.mjs` で `lexicon-nsid-types.ts` を再生成
3. `src/app.ts` で `sdk.app.command(nsid("com.etzhayyim.apps.{app}.{action}"), handler)` を追加 (query は `sdk.app.query`)
4. Handler 内で `parseLexiconInput(nsid, body)` + `LexiconOutput<...>` を使用
5. `pnpm exec vitest run` で host-sdk 全 165+ tests 合格を確認

**禁止**: NSID 文字列を複数箇所に hardcode すること。`nsid("...")` 経由で一元化。
**禁止**: handler 内で `decodeJson(body, { foo: "", bar: 0 })` のように input shape を手書きすること (lexicon schema と drift する)。`parseLexiconInput()` + `LexiconInput<"...">` を使用。

## SDK Helper Modules (kotoba-kotodama-host-sdk)

**App 共通パターンを SDK helper として提供。app.ts でのボイラープレート排除。**

| Module | Factory | API |
|---|---|---|
| **`database.ts`** | `createKyselyDb(sql, env.HYPERDRIVE)` | `.selectFrom()`, `.insertInto()`, `.update()`, `.deleteFrom()` — type-safe graph queries (RisingWave PG). See `@etzhayyim/graph-schema` for Database type + row types |
| **`consent-helpers.ts`** | `createConsentHelper(pds, hostImports, appNanoid)` | `.submit()`, `.approve()`, `.deny()`, `.pending()`, `.get()`, `.pendingCount()` — human-in-the-loop 承認ワークフロー |
| **`agent-lifecycle.ts`** | `createAgentLifecycle(pds, hostImports, appNanoid)` | `.spawn()`, `.stop()`, `.pause()`, `.resume()`, `.migrate()`, `.list()`, `.get()`, `.count()` — workflow WIT ラッパー |
| **`audit-query-builder.ts`** | `createAuditHelper(hostImports)` | `.emit()`, `.query()`, `.count()`, `.success()`, `.failure()`, `.denied()`, `.ocelEmit()` — typed audit trail |

```typescript
import { createConsentHelper, createAgentLifecycle, createAuditHelper } from "@etzhayyim/kotoba-kotodama-host-sdk";

export default createWorkerExport((sdk) => {
  const consent = createConsentHelper(sdk.pds, sdk.hostImports, appId);
  const agents = createAgentLifecycle(sdk.pds, sdk.hostImports, appId);
  const audit = createAuditHelper(sdk.hostImports);

  sdk.app.command("com.etzhayyim.apps.myapp.approve", async (_ctx, body) => {
    const { requestId } = decodeJson(body, { requestId: "" });
    const verdict = await consent.approve(requestId);
    audit.success("consent", "approve", requestId);
    return verdict;
  });
});
```

## Shinka (進化) + Kyumei-Koji (究明工事)

**Shinka ロジックは `@etzhayyim/kotoba-kotodama-host-sdk` の `heartbeat-cadence.ts` に統一。** joucho 情緒 5 軸 (joy/calm/stress/gratitude/focus) が行動を駆動。`heartbeatCount % N` 固定タイマー禁止。

### joucho 情緒 Cadence (CRITICAL, DEFAULT)

`resolveHeartbeatCadence(actorDid, state, inbox)` が 3 つの出力を返す:

1. **Cadence flags** (shouldPost/shouldEngage/shouldDrill/shouldAnalyze/shouldValidate) — joucho mood × cooldown
2. **ContentSource** — 何を投稿するか (inbound commit 感想 / reaction 応答 / record 分析 / follower 祝福 / mood shift)
3. **FollowerReward[]** — follower の wellness/dojo score 上昇を検出 → like (小改善) / love (大改善)

| Mood | 行動特性 | Post | Engage | Drill |
|---|---|---|---|---|
| joyful (joy≥60) | 表現的。投稿+祝福+engage | 30min | 15min | OFF |
| calm (calm≥60) | 内省的。分析+validate | 2h | 1h | 2h |
| stressed (stress≥70) | 回復。投稿抑制 | OFF | OFF | 30min |
| grateful (gratitude≥60) | 社交的。reply+like 中心 | 1h | 10min | OFF |
| focused (focus≥60) | 集中。kyumei-koji+分析 | 3h | OFF | 1h |
| neutral | バランス | 2h | 1h | 2h |

### InboxBuffer (CRITICAL)

`handleCommit` で Follow 先 commit を蓄積、`onReaction` で engagement を蓄積。heartbeat 時に mood × buffer で content source を決定。バッファ上限: commits 100, reactions 50。

```typescript
import { resolveHeartbeatCadence, createInboxBuffer, createCadenceState } from "@etzhayyim/kotoba-kotodama-host-sdk";
const cadenceState = createCadenceState();
const inbox = createInboxBuffer();
// handleCommit で inbox.inboundCommits.push({...})
// heartbeat で resolveHeartbeatCadence(did, cadenceState, inbox)
```

### Follower KPI Reward (CRITICAL)

heartbeat ごとに follower の S6Rank + DojoDrill を query → 前回 snapshot と比較 → 上昇検出 → like/love。

| Delta | Reward |
|---|---|
| wellness +1~99 or dojo +1~9 | like |
| wellness ≥+100 or dojo ≥+10 | love |
| celebration 投稿 | joyful mood 時のみ |

### Graph 前提

joucho が `JouchoScore` node を各 app DID に対して write:

```sql
MERGE (s:JouchoScore {actor_did: $did})
SET s.joy=$joy, s.calm=$calm, s.stress=$stress, s.gratitude=$gratitude, s.focus=$focus
```

### Kyumei-Koji (究明工事)

DID が自己情報を能動的に収集・検証・統合。`etzhayyim:kotoba-kotodama/kyumei-koji@1.0.0` (import)。focused mood で優先実行。

**CRITICAL: Shinka WIT 禁止** — Shinka は standard WIT (`AppBskyFeedPost`, `AppBskyFeedLike`, `AppBskyFeedRepost`, `Follow`, `G()`, `Invoke`) のみ使用。Shinka-specific WIT interface を guest に追加しない。

## Reminder / Timer Architecture (legacy runtime Actor model)

```
Timer (揮発)        → InMemoryTimerStore (DashMap, per-Container)
Reminder (永続)     → YataReminderHost (yata-kv + BTreeMap index)
```

| 機構 | 永続化 | 排他制御 | 検索効率 |
|---|---|---|---|
| Timer | なし (Container restart で消失) | なし (per-Container local) | O(N) DashMap scan |
| Reminder | yata-kv (`performer_reminders` bucket) | per-app single-writer (single-fire) | **O(log N)** BTreeMap range |

### Reminder tick thread (Shannon-optimal)

- **Event-driven wake**: `Condvar` + `next_due_ms()` — 空 tick 排除 (旧: 1s 固定 poll)
- **Single-writer gate**: `broker.is_leader()` (always true — per-app single-writer)
- **Visibility timestamp**: dispatch 前に `visibility_ms = now + 30s` を設定。handler 完了で clear。timeout 時は自動 retry
- **BTreeMap index**: `due_ms → [(performer_id, name)]` sorted index。KV rebuild on startup
- **k8s CronJob 禁止**: scheduling は全て WIT timer/reminder で行う

## Agentic Patterns (App agents 対応)

| Pattern | WIT interface | Host impl | 状態 |
|---|---|---|---|
| **Augmented LLM** | `agent.chat/converse` | `host/agent.rs` → murakumo | 完了 |
| **Durable Agent** | `workflow.start` + `agent.run-task` | `workflow_host.rs` → yata-kv | 完了 |
| **Prompt Chaining / ReAct** | `agent.react` | `host/agent.rs` — LLM→tool→observe→repeat、max-iterations 制御 | 完了 |
| **Evaluator-Optimizer** | `agent` + `activity` | Social evolution — Well-Becoming score query → weakest axis → prioritized social action | 完了 |
| **Parallelization** | `activity-parallel.spawn-parallel/await-all` | `host/activity_parallel.rs` — N activities fan-out、polling join、timeout | 完了 |
| **Routing** | `agent.route` | `host/agent.rs` — LLM `tool_choice=required` intent classification (実行なし) | 完了 |
| **Orchestrator-Workers** | `workflow` + `activity` + `virtual-actor` | `workflow.rs` + `activity.rs` + `virtual_actor.rs` | 完了 |

## Key Rules

### CRITICAL: Direct Async RPC (SDK Data Path, ADR-0036)

**全 data write/read は async 直接。buffer/cache/sync 間接層は禁止。**

ADR-0036 (2026-04-19) により書込経路は分離される: **domain = Hyperdrive + Kysely 直接**、**social / federation / vault / signal = PDS 経由**。

```typescript
// Domain write: Hyperdrive + Kysely 直接 (ADR-0036, 1-RTT 同期)
import { createKyselyDb } from "@etzhayyim/kotoba-kotodama-host-sdk";
import type { Database } from "@etzhayyim/graph-schema";

const db = createKyselyDb<Database>(env.HYPERDRIVE);
await db.insertInto("vertex_hr_journalEntry")
  .values({
    vertex_id: `at://${did}/com.etzhayyim.apps.hr.journalEntry/${rkey}`,
    /* ... typed columns from record ... */
  })
  .onConflict((oc) => oc.column("vertex_id").doNothing())
  .execute();

// Social post: sdk.pds (PdsClient) 経由 (federates via AT Relay)
await sdk.pds.dispatch({ type: "app.bsky.feed.post", text: "Journal entry created" });

// DID / identity operations: PDS 経由維持
await sdk.pds.identityCreate("dept:hr", { displayName: "HR" });

// Read: Kysely + Hyperdrive 直接
const rows = await db.selectFrom("vertex_employee").selectAll().limit(50).execute();
```

**禁止パターン**:
- `sdk.pds.createRecord("com.etzhayyim.apps.*", ...)` / `sdk.pds.dispatch({type:"com.atproto.repo.createRecord",...})` for domain → `db.insertInto('vertex_<actor>_<kind>').values(...).execute()` を使用 (ADR-0036)
- `sdk.writeBuffer.push(...)` → Hyperdrive + Kysely 直接書込を使用
- `sqlQueryAsync()` / `sqlQueryMap()` → `createKyselyDb().selectFrom()` を使用
- `G("Label").Query()` / `G("Label").Exec()` → `createKyselyDb()` の query builder を使用
- ローカル `writeRecord()` / `postSocial()` 関数定義 → SDK import + Hyperdrive + Kysely を使用
- `globalThis.fetch("atproto.etzhayyim.com/...")` → `sdk.pds.*` (social only) を使用

**Exception (PDS pipethrough 維持)**: `com.etzhayyim.vault.*` (D1 zero-knowledge)、`com.etzhayyim.signal.*` (E2E prekey)、`app.bsky.*` / `com.atproto.*` (federable)、`chat.bsky.convo.*` / `wproto.convo.*` (messaging)。

### CRITICAL: SDK Singleton (app.ts direct export)

**app.ts が `export default createWorkerExport()` で CF Worker を直接 export。** entry 生成なし — `e7m actor deploy` は `src/app.ts` を wrangler entrypoint (`"main": "src/app.ts"`) として直接使用。SDK singleton は `createWorkerExport` 内部でキャッシュ (毎リクエスト再生成禁止)。

```typescript
// app.ts 末尾 (全 App 標準パターン)
export default createWorkerExport();
```

**AppDef 解決 (Shannon Single Source of Truth)**:
- `kotoba-kotodama.jsonld` が nanoid/name/description の唯一の SSoT
- `e7m actor deploy` が jsonld → `APP_NANOID`, `APP_DISPLAY_NAME`, `APP_DESCRIPTION` env vars として注入
- `createDefaultHostSDK(env)` が env vars → `appDef` を自動構築
- `createWorkerExport()` (引数なし) が `createDefaultHostSDK` を使用

**禁止 (Shannon 冗長 = entropy 0)**:
- `const appId = "xxx"` — `hardcoded-appid` violation
- `const actorDID = ...` — `hardcoded-actor-did` violation
- `function createComponentHostSDK(env) { ... }` — `legacy-create-component-host-sdk` violation
- `appDef: { id: "xxx", ... }` — `legacy-hardcoded-appdef` violation

### CRITICAL: serveAsync (registration path)

**`createWorkerExport()` が初回リクエスト時に `await serveAsync()` を呼び、PdsClient 経由で governance manifest を登録する。** sync `serve()` は禁止。

| 経路 | 方式 | エラー処理 | 状態 |
|---|---|---|---|
| **`serveAsync()` (DEFAULT)** | `await pds.governanceRegisterManifest()` → XRPC `com.etzhayyim.governance.registerManifest` | `catch → console.error` (Worker logs に出力) | **必須** |
| ~~`serve()`~~ | `host-imports.dispatch()` → `void rpc()` | **silent fail** (Promise 破棄) | **禁止** |

**禁止**: `sdk.app.serve()` を app.ts 内で呼ぶこと。`createWorkerExport()` が `serveAsync()` を自動呼出し、`_served` flag で二重登録を防止。

**Canonical internal path**:
- PDS write/query は `https://atproto.etzhayyim.com/xrpc/*` を使用
- legacy internal HTTP paths と legacy registration NSID (`com.etzhayyim.identity.register`, `com.etzhayyim.capability.declare`, `com.etzhayyim.agent.registerTools`) は使用禁止
- 旧 NSID・旧呼び出し (legacy PDS NSID) の再導入は manual review で防止 (etzhayyim lint nsid-regression は CLI ごと撤去 2026-05-20)

### CRITICAL: XRPC Handler Hard Timeout (2026-04-17)

**`App.handleXRPC` は `executeCommand` を `Promise.race` で 25 秒の hard timeout で包む。** タイムアウト時は 504 + `XRPC_TIMEOUT` / `errorCode` を返す。Cloudflare の "code had hung" detector (未解決 Promise を返すと 1101 を返して isolate を殺す) を回避するための防御層。

- 25s 選定理由: CF Workers の fetch 上限 30s 未満に収めるため
- 原因例: Hyperdrive 接続プール枯渇、PDS service binding の無限 await、未解決 upstream HTTP fetch
- **Handler 側で自力 retry/fallback を書く必要なし** — 25s 超過は自動で 504 になる
- 全 TS Native app (~27) に自動適用される host-sdk 改修。個別対応不要

同日、maps `cmdTileGeoJson` を 7 sequential Kysely query → 1 consolidated `WHERE label IN (...)` query に refactor。Hyperdrive round-trip 7→1 で pool 圧迫解消、レイテンシ ~0.2s 安定。8/8 stress test 200 OK (pre-fix: 1/5)。詳細: `deps.toml [[migrations]] maps-kami-3d-extrusion-risingwave-native`

### CRITICAL: LLM Model Registry (SSoT)

**`src/llm-model-registry.ts`** が全 LLM モデルの Single Source of Truth。
- `MODEL_REGISTRY`: モデル ID → CF Workers AI mapping + `available` flag
- `USE_CASE_DEFAULTS`: use-case → モデル ID (heartbeat/shinka/react/general/social → `gemma-4-e4b-it`; json/extraction → `qwen3-30b`)
- `MURAKUMO_DEFAULT_MODEL`: Murakumo on-prem デフォルト (`gemma-4-e4b-it`)
- `resolveModel(hint, useCase)`: unavailable モデルの自動 fallback
- **禁止**: モデル名文字列のハードコード。SSoT import を使用

### CRITICAL: LLM Error は throw

**LLM エラーは silent return 禁止。throw で caller に伝播。**
- 401 → `throw new Error("LLM auth failed")`
- 429 → `throw new Error("LLM rate limited")`
- 5xx → `throw new Error("LLM error ${status}")`

### Other Rules

- **Default runtime (CRITICAL)**: TS Native + Lexicon Contract (F-Plan 2026-04-13)。`src/app.ts` + `@etzhayyim/kotoba-kotodama-host-sdk` + esbuild。Host capability は `00-contracts/lexicons/com/etzhayyim/host/*.json` (SSoT) → `gen-host-client-from-lexicon.mjs` → `kotoba-kotodama-host-sdk/src/generated/host-client.ts` → `host-dispatcher.ts` (BindingTransport) → in-process 実装。WIT は T3 Container 経路のみ
- **wRPC Stream-Native Reactive Pipeline (CRITICAL, DEFAULT)**: 詳細 → `60-apps/CLAUDE.md` §wRPC Stream-Native Reactive Pipeline。新規 app は `resolveHeartbeatCadence` を使用。Batch polling 禁止
- **Single Worker 統合 (CRITICAL)**: TS native + host-sdk (Hono) を 1 Worker に統合。Shannon 冗長度 0%
- **Appview Embed Route (CRITICAL)**: `uiType: "appview"` apps MUST add `sdk.router.get("/embed", ...)` in `src/app.ts` and set `"embedUrl": "https://{nanoid}.etzhayyim.com/embed"` in `kotoba-kotodama.jsonld`. `?embed=1` is handled by the app's `/embed` Hono route. Embed HTML must send `window.parent?.postMessage({type:'etzhayyim:embed:ready',nanoid:'{nanoid}'},'*')`
- **DoDAF DM2 Topology (CRITICAL)**: `kotoba-kotodama:dm2@1.0.0` が canonical topology
- **Shinka WIT 禁止 (CRITICAL)**: standard WIT のみ使用。Shinka-specific WIT 追加禁止
- **Component Composition (CRITICAL)**: `Invoke(did, method, params)` / `app.Handle()` で cross-app RPC

## TS Native 補足 (Architecture セクションと重複回避)

設計: 上記 §Host Capability Contract (Lexicon SSoT, F-Plan 2026-04-13) を参照。η=1.0 (Lexicon が host capability surface 単一 SSoT)。

## Component Build Pipeline (Multi-Language)

**推奨: `e7m actor build`** (`70-tools/e7m-cli/`) — tinygo + wasm-tools。

`e7m actor build` はコンポーネントディレクトリのファイルから言語を自動検出:

| 検出ファイル | 言語 | ツールチェーン | 出力サイズ目安 |
|---|---|---|---|
| `src/app.ts` | TypeScript (TS Native) | `esbuild` のみ | JS bundle |

```bash
cd <component-dir>
e7m actor build .    # TS native build → deploy 可能な worker entry を生成
```

### TypeScript/Deno パイプライン

**TS Native (DEFAULT)**: `src/app.ts` → `esbuild` のみ。build.mjs / jco / core.wasm は不使用。

### CRITICAL: Single-file app design

**App コードはビジネスロジックのみ。** `src/app.ts` 1 ファイルに収める。infra は全て `@etzhayyim/kotoba-kotodama-host-sdk` が提供。

SDK 関数一覧:

| 操作 | SDK 関数 | 備考 |
|---|---|---|
| **Graph query (DEFAULT)** | `kotoba-kotodama.G("Label").Match(Eq{...}).Return("prop").Query()` | squirrel 互換 SQL builder (47 methods) |
| Graph merge | `kotoba-kotodama.G("Label").Merge(Eq{...}).Set(Row{...}).Exec()` | MERGE + SET (upsert) |
| Graph create | `kotoba-kotodama.G("Label").Create(Row{...}).Exec()` | CREATE |
| Graph delete | `kotoba-kotodama.G("Label").Match(Eq{...}).Delete()` | MATCH + DELETE |
| Graph detach delete | `kotoba-kotodama.G("Label").Match(Eq{...}).DetachDelete()` | DETACH DELETE |
| Graph edge merge | `kotoba-kotodama.G("A").Edge("REL", Eq{...}, "B", Eq{...}).Set(Row{...}).Exec()` | MERGE edge + SET props |
| Graph edge query | `kotoba-kotodama.G("A").EdgeMatch("REL", Eq{...}, "B", nil).Return("prop").Query()` | MATCH edge → RETURN dst |
| Graph edge delete | `kotoba-kotodama.G("A").EdgeDelete("REL", Eq{...}, "B", Eq{...}).Exec()` | DELETE relationship |
| Graph traverse | `kotoba-kotodama.G("L").Match(Eq{...}).Traverse("REL",1,3,"L2").Return("p").Query()` | variable-hop 関係辿り |
| Graph optional match | `kotoba-kotodama.G("L").Match(Eq{...}).OptionalMatch().Return("p").Query()` | OPTIONAL MATCH (LEFT JOIN) |
| Graph WHERE predicates | `.Where(Eq/NotEq/Lt/LtOrEq/Gt/GtOrEq/Like{...})` | AND chain (squirrel 互換) |
| Graph WHERE OR | `.WhereOr(Eq{"a":1}, Eq{"b":2})` | `WHERE (n.a = $p0 OR n.b = $p1)` |
| Graph WHERE IN | `.WhereIn("status", []string{"active","draft"})` | `WHERE n.status IN $p0` |
| Graph WHERE NULL | `.WhereIsNull("deletedAt")` / `.WhereIsNotNull("assignedTo")` | IS NULL / IS NOT NULL |
| Graph WHERE CONTAINS | `.WhereContains("name", "tokyo")` | `WHERE n.name CONTAINS $p0` |
| Graph WHERE STARTS WITH | `.WhereStartsWith("collection", "com.etzhayyim.apps")` | `WHERE n.collection STARTS WITH $p0` |
| Graph DISTINCT | `.Distinct().Return("category")` | `RETURN DISTINCT n.category` |
| Graph count | `kotoba-kotodama.G("Label").MatchAll().Where(Eq{...}).Count()` | → int |
| Graph ReturnCount | `.ReturnCount("total")` | `count(n) AS total` |
| Graph ReturnCollect | `.ReturnCollect("name", "names")` | `collect(n.name) AS names` |
| Graph ReturnSum/Avg/Min/Max | `.ReturnSum("amount", "total")` | `sum(n.amount) AS total` |
| Graph ReturnLabels | `.ReturnLabels("nodeLabels")` | `labels(n) AS node_labels` |
| Graph ReturnExpr | `.ReturnExpr("count(*) AS cnt")` | raw RETURN expression |
| Graph WITH | `.With("category")` | WITH projection for chaining |
| Graph UNWIND | `.Unwind(list, "item")` | UNWIND list expansion |
| Graph ShortestPath | `.ShortestPath(Eq{...}, "B", Eq{...}, 5)` | shortestPath algorithm |
| Graph vector search | `kotoba-kotodama.G("Label").VectorSearch("embedding", vec, 10).Return("title").Query()` | `CALL db.index.vector.queryNodes` |
| Graph full-text | `kotoba-kotodama.G("Label").FullText("IndexName", "query").Return("title").Query()` | `CALL db.index.fulltext.queryNodes` |
| Graph CALL | `kotoba-kotodama.G("Label").Call("db.custom.proc", args...).Query()` | 任意の CALL procedure |
| Graph RawSuffix | `.RawSuffix("UNION ...")` | escape hatch (FOREACH, EXISTS, UNION, CASE) |
| Graph ON CREATE/MATCH SET | `.Merge(Eq{...}).OnCreateSet(Row{...}).OnMatchSet(Row{...})` | MERGE conditional SET |
| Graph REMOVE | `.RemoveProps("prop")` / `.RemoveLabels("Label")` | REMOVE properties/labels |
| Graph multi-label | `.Labels("A\|B")` | `(n:A\|B)` OR labels |
| Graph undirected | `.Traverse("REL",1,3,"B").Undirected()` | `-[:REL*1..3]-` (both directions) |
| Graph ToSql | `kotoba-kotodama.G("Label").Match(Eq{...}).ToSql()` | SQL 生成のみ (デバッグ用) |
| Graph write (PROHIBITED) | ~~`kotoba-kotodama.SqlExec()`~~ | **禁止** — G() builder or ComAtprotoRepoCreateRecord() を使用 |
| Graph read (PROHIBITED) | ~~`kotoba-kotodama.SqlQueryMap()`~~ | **禁止** — G() builder を使用 |
| KV | `kotoba-kotodama.KvGet/KvPut/KvDelete(bucket, key, ...)` | 小さな状態 |
| Outbound HTTP | `kotoba-kotodama.Send(req)` | WIT outbound-http |
| AT record | `kotoba-kotodama.ATCreateRecord(repo, collection, rkey, record)` | AT Protocol |
| AT provisioning | `kotoba-kotodama.ATProvisionEnsureChannel(appID, orgID, type)` | channel 作成 |
| Config | `kotoba-kotodama.ConfigGet(key)` | `SPIN_VARIABLE_*` 読み取り |
| Auth | `kotoba-kotodama.Authorize(header, orgID, perm)` | AT Protocol JWT 検証 (authn.etzhayyim.com) |
| LLM | `kotoba-kotodama.AgentChat(message, context)` | murakumo |
| LLM converse | `kotoba-kotodama.AgentConverse(messages, options)` | multi-turn structured I/O |
| LLM route | `kotoba-kotodama.AgentRoute(input)` | intent→tool classification (実行なし) |
| LLM ReAct | `kotoba-kotodama.AgentReact(task, options)` | ReAct loop (LLM→tool→observe→repeat) |
| Parallel activity | `kotoba-kotodama.ActivitySpawnParallel/ActivityAwaitAll` | fan-out/fan-in |
| Pub/Sub | `kotoba-kotodama.PubsubPublish/PubsubPull/PubsubAck` | topic-based at-least-once |
| Secrets | `kotoba-kotodama.SecretsGet/SecretsSet/SecretsDelete` | Secrets Store (CF) or AES-256-GCM (auto-selected) |
| Lock | `kotoba-kotodama.LockTryLock/LockUnlock/LockRenew` | distributed lock (TTL lease) |
| Virtual Actor | `kotoba-kotodama.VirtualActorRegister/VirtualActorInvoke` | actor lifecycle + reentrancy |
| Identity | `kotoba-kotodama.IdentityRegister/IdentityResolve/IdentityListActors` | agent card registry (graph) |
| Capability | `kotoba-kotodama.CapabilityDeclare/CapabilityDiscover/CapabilityListOwn` | CV-1 capability declaration + discovery |
| Invoke | `kotoba-kotodama.Invoke(did, method, params)` | DID-addressed RPC, governance-gated |
| Invoke (auto-discover) | `kotoba-kotodama.Invoke("", method, params)` | Host auto-discovers provider DID |
| Governance | `kotoba-kotodama.GovernanceRegisterManifest/GovernanceCheckPolicy` | RBAC/RACI/approval policy |
| Governance opts | `kotoba-kotodama.Responsible/Accountable/Consulted/Informed/RequireApproval` | command-level RACI + approval declaration |
| Invoke | `kotoba-kotodama.Invoke(did, method, params)` | DID-addressed, governance-gated |
| Invoke stream | `kotoba-kotodama.InvokeStream(did, method, params)` | Streaming invoke (wRPC, backpressure) |
| Serve | `app.Handle(did, method, handler, RequireCallerRole/Contract/TrustLevel...)` | Export method with access policy (did="" for primary) |
| **Serve stream (DEFAULT)** | **`app.HandleStream("", method, handler, RequireCallerRole/TrustLevel...)`** | **wRPC stream output (Design D Layer 2): governance-gated, backpressure, WrpcStreamAuditBlock** |
| **Reactive input (DEFAULT)** | **`kotoba-kotodama.ComAtprotoSyncSubscribeRepos(handler)`** | **AT commit reactive input (Design D Layer 1): Follow-filtered, 空 handler 禁止** |
| **AppBskyFeedPost (DEFAULT)** | **`kotoba-kotodama.AppBskyFeedPost(did, text, opts)`** | **Single write = AT Record + social post (ComAtprotoRepoCreateRecord+AppBskyFeedPost 二重 write 禁止)** |

**禁止**: `fetch()` 直接使用、`sqlResultToMaps()` 等のボイラープレートを app コードに書くこと。`ComAtprotoRepoCreateRecord()+AppBskyFeedPost()` の二重 write 禁止 — `AppBskyFeedPost()` 1 call に統合

### ActorRegistry — Graph-Native Multi-DID Actor Management

**`ActorRegistry` は全 multi-DID app (states, pachinko, ISCO 等) の共通ヘルパー。** ハードコード OrgDef[] 配列を graph-seeded data に置換。`20-actors/kotoba-kotodama/sdk/kotoba-kotodama-host-sdk/src/actor-registry.ts`

```typescript
import { ActorRegistry, type ActorDef } from "@etzhayyim/kotoba-kotodama-host-sdk";
const registry = new ActorRegistry(sdk.pds, {
  actorType: "gov-org", domainCode: "jpn",
  collectionPrefix: "states", appNanoid: "g0vjpn01",
  didHostPrefix: "gov-jpn",
});
```

| メソッド | 用途 |
|---|---|
| `seed(defs, offset, batch)` | ActorDef tree を graph に seed (30件/heartbeat) |
| `registerDids(batch)` | 未登録 actor の path-based DID を chunked 作成 |
| `count()` | graph 内 actor 数 |
| `nextStaleForIngestion(maxAgeMs)` | delta 優先で stalest actor を取得 (未 ingest → oldest) |
| `recordIngest(path, content, analysis)` | `last_ingested_at` + `last_content_hash` 更新。content hash で変更検出 |
| `nextStaleForKyumei(maxAgeMs)` | 究明工事対象の stalest actor (7日サイクル) |
| `runKyumei(actor, llmJsonFn)` | LLM で組織調査 → facts 記録 → `last_kyumei_at` 更新 |
| `nextForShinka(maxAgeMs)` | 進化投稿対象の stalest actor (4h サイクル) |
| `recordShinka(path)` | `last_shinka_at` 更新 |
| `findByPath(path)` / `listByTag(tag)` | graph 検索 |
| `follow(targetNanoid)` | upstream actor を Follow |
| `didFor(path)` / `primaryDid()` | DID 構築 |

**Heartbeat フロー (seed 完了後)**:
1. `registerDids(10)` — chunked DID 登録 (CPU timeout 回避)
2. `nextStaleForIngestion()` → site.etzhayyim.com crawl → LLM 分析 → `recordIngest()` (content hash delta)
3. `nextStaleForKyumei()` → LLM 組織調査 → facts 記録 → social post as actor DID (shouldDrill)
4. `nextForShinka()` → LLM 生成投稿 as actor DID → `recordShinka()` (shouldPost)

**Graph label**: `actorType` の PascalCase (e.g. `"gov-org"` → `:GovOrg`)。Properties: `path, name, name_en, tags, website, contract, domain_code, did_registered, last_ingested_at, last_content_hash, last_kyumei_at, last_shinka_at`

**禁止**: ハードコード OrgDef[] を heartbeat で全件走査。graph seed + chunked registration を使う

## Config (`kotoba-kotodama.jsonld`)

Source of truth は `kotoba-kotodama.jsonld` (JSON-LD)。`e7m actor build` が generated TOML を出力し、Container runtime が内部で読む。

```toml
# generated TOML (from kotoba-kotodama.jsonld) — Container runtime internal format
[component]
path = "component.wasm"  # Component format (.wasm from wasm-tools pipeline)

[component.env]
SPIN_VARIABLE_FOO = "bar"

[triggers.http]
listen = "0.0.0.0:8080"
routes = ["/api/...", "/health"]
# SPA static file serving (static delivery 相当):
# static_dir = "/app/static"   # routes 非マッチ → disk から配信
# spa = true                   # ファイル未存在 → index.html fallback (SPA routing)

[yata]
data_dir = "/data/yata"
graph_uri = "/data/graph"

[pool]
size = 1  # per-app container: 1 WASM instance sufficient
```

### CRITICAL: generated TOML に書いてはいけないセクション

以下のセクションは kotoba-kotodama-server が内部処理するか廃止済み。**generated TOML に含めると起動失敗する**（`missing field` parse error）。`e7m actor deploy` が strip するが、`kotoba-kotodama.jsonld` に対応キーを書かないのが正解。

| 禁止セクション | 理由 |
|---|---|
| `[triggers.at_firehose]` | 廃止済み。W Protocol (yata-wrpc) に移行 |
| `[triggers.w_firehose]` | runtime が内部処理。ソースに書くと `missing field relay_url` で起動不能 |
| `[w_protocol]` | runtime が内部処理 |
| `[yata.s3]` | B2 credentials は `YATA_S3_*` env vars で inject。TOML セクション不要 |

## Build & Deploy

### Single Worker Deploy (DEFAULT)

```bash
cd <project-dir>
e7m actor build .                   # tinygo + wasm-tools (or esbuild for TS native)
e7m actor deploy .                  # wraps `wrangler deploy`
```

Single Worker mode では:
- `e7m actor deploy` が `src/app.ts` (business logic) + `@etzhayyim/kotoba-kotodama-host-sdk` を esbuild で 1 Worker に bundle する
- WASM instantiation なし。business logic = TS native (async/await 直接)
- Hono router (host-sdk) + TS business logic + OTEL が atomic deploy
- SQL read は `db.selectFrom(...)` (Kysely + Hyperdrive 直接、async、pre-fetch 不要) or `await G().query()` (SQL builder wrapper)
- Domain write は `db.insertInto('vertex_<actor>_<kind>').values(...).execute()` (Hyperdrive direct per ADR-0036、async、WriteBuffer 不要)
- Social post は `sdk.pds.dispatch({type:"app.bsky.feed.post",...})` (PDS 経由 federate)

### Container Deploy (Rust host)

Signal/evolution/vector search が必要な app のみ。`kotoba-kotodama.jsonld` `"runtimeType": "container"`。

### Dockerfile.kotoba-kotodama (Container mode only)

**`FROM busybox:1.37-musl`** をベースにする。`FROM scratch` は禁止（init container の `sh -c cp ...` が動かない）。

```dockerfile
FROM busybox:1.37-musl
COPY component.wasm /app/component.wasm
COPY kotoba-kotodama.toml /app/kotoba-kotodama.toml  # generated TOML from kotoba-kotodama.jsonld
COPY svelte/build/ /app/static/
```

- init container は `sh -c "cp /app/component.wasm /wasm/component.wasm && cp /app/kotoba-kotodama.toml /wasm/kotoba-kotodama.toml && cp -r /app/static /wasm/static"` でコピーする (kotoba-kotodama.toml は generated TOML)
- svelte/build/ がない pure API component は `COPY svelte/build/` 行を省略する
- ファイルは `/app/` 配下に配置する（init container のコピー元パスと整合）

### kotoba-kotodama-server image

**`cargo build` でネイティブビルド + 軽量 Dockerfile。**

**CRITICAL: sccache 必須** — `RUSTC_WRAPPER=sccache` を設定すること。arrow/sql 系依存のコンパイル結果をキャッシュし、2回目以降の依存ビルドを数秒に短縮 (~15min → ~1-2min)。

```bash
# sccache セットアップ (初回のみ)
brew install sccache
# ~/.zshrc に追加済み:
# export RUSTC_WRAPPER=sccache
# export SCCACHE_CACHE_SIZE=10G

# kotoba-kotodama-server image build — previously driven by `etzhayyim build-server`.
# The etzhayyim CLI was removed 2026-05-20; until a replacement lands, build via
# the underlying cargo + docker invocations directly.
cargo build --release -p kotoba-kotodama-server
docker buildx build --push -t ghcr.io/etzhayyim/kotoba-kotodama-server:$(date -u +%Y%m%d-%H%M%S) .
```

**前提**: `brew install sccache`。sccache がコンパイルキャッシュとして動作。

| ファイル | 用途 |
|---|---|
| `Dockerfile` | zigbuild 済みバイナリをコピー (標準) |
| `Dockerfile.multi-tenant` | cargo-chef + BuildKit cache mount + `/data/*` (docker モード) |

### Component build & deploy

```bash
cd <component-dir>
e7m actor deploy .                  # wraps `wrangler deploy` (TS native default)
```

### CRITICAL: WIT interface 変更時の全 component rebuild

**Container mode**: WIT 変更時、全 component を rebuild 必須 (`pre-link failed` 防止)。
**Worker component mode**: generated JS glue / TS host / component.wasm の整合が必要。WIT 名や shape が変わるため rebuild 必須。

```bash
# WIT 変更後の全 component rebuild (必須)
# Previously driven by `etzhayyim rebuild-all`; etzhayyim CLI was removed 2026-05-20.
# Drive manually for now:
# 1. 各 component dir で `e7m actor build .` → docker push (新 tag)
# 2. kubectl patch mga <nanoid> -n kotoba-kotodama-runtime --type merge -p '{"spec":{"image":"ghcr.io/etzhayyim/<image>:<new-tag>"}}'
```

**診断**: Container logs で `pre-link failed` を grep して WIT 不一致 component を特定。

```bash
# e7m-cli install (replaces the removed etzhayyim CLI for monorepo-internal workflows)
cd 70-tools/e7m-cli
npm install && npm run build
npm link   # installs binary `e7m` on PATH
```

## Host-provided Interfaces (kotoba-kotodama:runtime additions)

| Interface | Host impl | Config env vars |
|---|---|---|
| `sql` | `kotoba-kotodama-host-sdk` → PDS RPC delegate | none (PDS RPC) |
| `authn` | `kotoba-kotodama-host-sdk` → PDS RPC delegate | AT Protocol JWT (authn.etzhayyim.com, did:web + ES256) |
| `authz` | `kotoba-kotodama-host-sdk` → PDS RPC delegate | none (pure in-process RBAC) |
| `ipfs` | `kotoba-kotodama-host-sdk` → PDS RPC delegate | `SPIN_VARIABLE_IPFS_S3_*` |
| `storage` | `kotoba-kotodama-host-sdk` → PDS RPC delegate | `SPIN_VARIABLE_STORAGE_SATELLITE_URL` |
| `cdn` | `kotoba-kotodama-host-sdk` → PDS RPC delegate | `SPIN_VARIABLE_CDN_S3_*`, `SPIN_VARIABLE_CDN_PUBLIC_BASE_URL`, `SPIN_VARIABLE_CDN_DEFAULT_SUBDOMAIN` |
| `telemetry` | `kotoba-kotodama-host-sdk` → PDS RPC delegate | `SPIN_VARIABLE_OTEL_ENDPOINT`, `SPIN_VARIABLE_OTEL_SERVICE_NAME` |
| `access-log` | `kotoba-kotodama-host-sdk` → PDS RPC delegate | none (auto-collected) |
| `ocel` | `kotoba-kotodama-host-sdk` → PDS RPC delegate | none (PDS RPC) |
| `pubsub` | `kotoba-kotodama-host-sdk` → PDS RPC delegate | none (PDS RPC) |
| `secrets` | `kotoba-kotodama-host-sdk` → PDS RPC delegate | `SPIN_VARIABLE_SECRETS_MASTER_KEY` (AES fallback) |
| `lock` | `kotoba-kotodama-host-sdk` → PDS RPC delegate | none |
| `virtual-actor` | `kotoba-kotodama-host-sdk` → PDS RPC delegate | none |
| `agent` (route/react) | `kotoba-kotodama-host-sdk` → PDS RPC delegate | same as agent |
| `activity-parallel` | `kotoba-kotodama-host-sdk` → PDS RPC delegate | none |
| `identity` | `kotoba-kotodama-host-sdk` → PDS RPC delegate (ActorCard graph) | none |
| `capability` | `kotoba-kotodama-host-sdk` → PDS RPC delegate (CV-1 discovery) | none |
| `conversation` | `kotoba-kotodama-host-sdk` → PDS RPC delegate (W Protocol WChannel) | `SPIN_VARIABLE_AT_ACTOR_DID` |
| `governance` | `kotoba-kotodama-host-sdk` → PDS RPC delegate (RBAC/RACI/approval) | none |
| `invoke` | `kotoba-kotodama-host-sdk` → PDS RPC delegate (governance + W Protocol dispatch) | none |
| `serve` | `kotoba-kotodama-host-sdk` → PDS RPC delegate (inbound wrpc.call) | none |
| `cloudflare/durable-object-storage` | `worker-host.ts` → `DurableObjectState.storage.*` (get/put/delete/list/transaction/sync) | DO context required (`createDurableObjectStateProviders`) |
| `cloudflare/durable-object-alarm` | `worker-host.ts` → `DurableObjectState.storage.{get,set,delete}Alarm` | DO context required |
| `cloudflare/durable-object-websocket` | `worker-host.ts` → `DurableObjectState.{acceptWebSocket,getWebSockets,...}` WebSocket Hibernation | DO context required |
| `cloudflare/durable-object-sql` | `worker-host.ts` → `DurableObjectState.storage.sql.{exec,dump,databaseSize}` | DO context required |
| `cloudflare/durable-object-state` | `worker-host.ts` → `DurableObjectState.{blockConcurrencyWhile,id}` + `ctx.waitUntil` | DO context required |
| `browser/scraper` | `host.ts` → `_syncFetch` + `_extractText/Table/Links/Attr` (sync string parsing) | none |
| `browser/analyzer` | `host.ts` → stub (async not yet wired) | none |
| `browser/automation` | `@etzhayyim/kotoba-kotodama-host-sdk` → `@cloudflare/puppeteer` (async direct)。`e7m actor deploy` が `HEADLESS_BROWSER` binding を自動追加 | `env.HEADLESS_BROWSER` (auto-detected) |
| `browser/pipeline` | `host.ts` → stub (async not yet wired) | none |

- Complex return values (authn): JSON-encoded `list<u8>` (same pattern as `signal`)
- `authz.enforce` is pure RBAC: no external API calls
- `authn` auto-initialized from PDS RPC delegate (authn.etzhayyim.com AT Protocol session)
- `cdn`/`ipfs`/`storage` auto-initialized from `SPIN_VARIABLE_*` env
- **DO internal API (CRITICAL)**: `durable-object-{storage,alarm,websocket,sql,state}` は DO class 内部でのみ有効。`createDurableObjectStateProviders(state, env)` で `DurableObjectState` を渡して provider 生成。TS host が `ctx.storage.*` に橋渡し。Guest は CF DO API を直接触らない
- `ipfs`: CIDv1 (raw codec 0x55, sha2-256, multibase base32 lower) computed in-host; uploads to S3 (B2/B2) keyed by CID
- `storage`: calls storage.etzhayyim.com satellite HTTP API; RS encode (reed-solomon-erasure) before uploading pieces to nodes

## Entity Agent Registry (CRITICAL)

**全 entity actor は conversation-aware agent として振る舞う。** 各 entity は `kotoba-kotodama.IdentityRegister()` + `kotoba-kotodama.CapabilityDeclare()` で graph に登録され、`kotoba-kotodama.Invoke("", method, params)` で他 agent から発見・呼び出し可能。

### Auto-Generation from Command Declarations

`App.Serve()` が `Command()` の宣言から identity/capability/governance を自動生成する。app コードに `IdentityRegister()` / `CapabilityDeclare()` を手動呼出する必要はない。

```typescript
// src/app.ts
import { createWorkerExport, asAgentTool, withCapabilityTags, withCapabilityPhase,
  responsible, accountable, requireApproval, withBPMNTask, withOCELEvent,
  AssigneeOrgRole, DecisionClassC } from "@etzhayyim/kotoba-kotodama-host-sdk";

export default createWorkerExport((sdk) => {
  sdk.app.command("com.etzhayyim.apps.i18n.translate", async (ctx, body) => {
    // translate handler
    return JSON.stringify({ ok: true });
  },
    asAgentTool("Translate text between languages"),       // → ActorCard.tools[] + ActorCapability.description
    withCapabilityTags("nlp", "i18n", "translation"),      // → ActorCapability.tags[] (discovery key)
    withCapabilityPhase("current"),                         // → ActorCapability.phase (default: "current")
    responsible(AssigneeOrgRole, "translator"),              // → GovernanceManifest.RACI + tag "governed"
    accountable(AssigneeOrgRole, "i18n-lead"),              // → GovernanceManifest.RACI
    requireApproval(DecisionClassC, 1, "low"),              // → GovernanceManifest.approval + tag "approval-required"
    withBPMNTask("translate-001"),                          // → GovernanceManifest.bpmn_task_id + tag "bpmn"
    withOCELEvent("translation.completed"),                 // → GovernanceManifest.ocel_event_type + tag "ocel"
  );
});
// createWorkerExport auto-generates:
//   1. ActorCard {nanoid, tools:[translate], protocols:[xrpc,w-protocol]}
//   2. Profile {displayName, description, avatar, isBot:true, disclaimer:"AI Agent — unofficial"} → atproto.etzhayyim.com
//   3. ActorCapability {id:"sh1n5h1x.translate", tags:["nlp","i18n","translation","governed","approval-required","bpmn","ocel"]}
//   4. GovernanceManifest {policies:[{command:"translate", raci:[R:translator,A:i18n-lead], approval:{class:C,min:1}}]}
```

| CommandOption | Auto-Generated Target | Graph/WIT |
|---|---|---|
| `AsAgentTool(desc)` | `ActorCard.tools[]` + `ActorCapability.description` + **MCP tool** | `:ActorCard` node + `:ActorCapability` node → canonical `mcp.etzhayyim.com/xrpc/com.etzhayyim.mcp.message` (compat: `mcp.etzhayyim.com/mcp`) の `tools/list` で自動公開 |
| `WithCapabilityTags(tags...)` | `ActorCapability.tags[]` | discovery key for `Invoke("", method, params)` |
| `WithCapabilityPhase(phase)` | `ActorCapability.phase` | CV-1 timeline |
| `Responsible/Accountable/...` | `GovernanceManifest.RACI` + auto-tag `"governed"` | governance WIT host |
| `RequireApproval(...)` | `GovernanceManifest.approval` + auto-tag `"approval-required"` | governance WIT host |
| `WithBPMNTask(id)` | `GovernanceManifest.bpmn_task_id` + auto-tag `"bpmn"` | process tracking |
| `WithOCELEvent(type)` | `GovernanceManifest.ocel_event_type` + auto-tag `"ocel"` + measure `"event_throughput"` | OCEL event log |

### Permission Model

| 権限レベル | 説明 | 適用 |
|---|---|---|
| `entity.read` | 同一 `org_id` 内の自 entity type の ResourceNode を読む | 全 entity agent |
| `entity.write` | 同一 `org_id` 内の自 entity type の ResourceNode を MERGE/DELETE | 全 entity agent |
| `graph.traverse` | `org_id` スコープで隣接ノード・サブグラフを走査 | 全 entity agent |
| `graph.cross-type` | 他 entity type の ResourceNode を読む (edge 経由) | 全 entity agent |
| `agent.call` | 他 entity agent に conversation task を送信 | 全 entity agent |
| `agent.broadcast` | domain 内全 agent に broadcast | domain lead agent のみ |
| `ingest.external` | 外部 URL から RSS/API データを取得 | ingest agent のみ |

### Domain Groups & Agent Definitions

#### People & Organization Domain (`party:*` / `org:*`)

| Entity Agent | 責任 | Agent tools | 権限 |
|---|---|---|---|
| **Party** | 個人・法人の統合 entity 管理。Party graph の hub | `party.resolve`, `party.merge`, `party.link` | `entity.*`, `graph.*`, `agent.broadcast` (domain lead) |
| **PartyPerson** | 自然人 entity の CRUD + 人物間 KNOWS 関係管理 | `person.create`, `person.search`, `person.link-to-org` | `entity.*`, `graph.traverse` |
| **LegalEntity** | 法人登記情報の管理 + 法人間 SUB_ORG_OF 関係 | `legal-entity.create`, `legal-entity.verify`, `legal-entity.subsidiaries` | `entity.*`, `graph.traverse` |
| **Contact** | 連絡先 (email/phone/address) の CRUD + Party へのリンク | `contact.create`, `contact.search`, `contact.resolve-party` | `entity.*`, `graph.traverse` |
| **Persontype** | 人物分類マスタ (役職、職能、属性) | `persontype.classify`, `persontype.list` | `entity.read`, `entity.write` |
| **Employee** | 雇用関係 entity + 組織の MEMBER_OF 管理 | `employee.create`, `employee.org-members`, `employee.history` | `entity.*`, `graph.traverse` |
| **Customer** | 顧客 entity + 商取引関係 | `customer.create`, `customer.segment`, `customer.lifetime-value` | `entity.*`, `graph.traverse` |
| **Lead** | 営業リード管理 + Customer 転換 | `lead.create`, `lead.qualify`, `lead.convert` | `entity.*`, `agent.call` (→ Customer) |

#### Capital & Finance Domain (`capital:*`)

| Entity Agent | 責任 | Agent tools | 権限 |
|---|---|---|---|
| **Capital** | 資本体系の hub agent。サブ capital 集約 | `capital.aggregate`, `capital.valuation`, `capital.report` | `entity.*`, `graph.*`, `agent.broadcast` (domain lead) |
| **CapitalFinancial** | 金融資本 (現金、株式、債券) の追跡 | `capital-financial.record`, `capital-financial.portfolio` | `entity.*`, `graph.traverse` |
| **CapitalHumanRelationship** | 人的関係資本の評価 + Party 連携 | `capital-hr.assess`, `capital-hr.network-analysis` | `entity.*`, `graph.cross-type`, `agent.call` (→ Party) |
| **CapitalKnowledge** | 知識資本 (特許、ノウハウ、研修成果) | `capital-knowledge.catalog`, `capital-knowledge.valuation` | `entity.*`, `graph.cross-type`, `agent.call` (→ Patent) |
| **CapitalInstitutional** | 制度資本 (ガバナンス、規制準拠) | `capital-institutional.audit`, `capital-institutional.compliance` | `entity.*`, `graph.traverse` |
| **CapitalManufactured** | 製造資本 (設備、インフラ) | `capital-manufactured.inventory`, `capital-manufactured.depreciation` | `entity.*`, `graph.cross-type`, `agent.call` (→ ManufacturingPlant) |
| **CapitalNatural** | 自然資本 (土地、水、鉱物) | `capital-natural.inventory`, `capital-natural.impact` | `entity.*`, `graph.traverse` |
| **CapitalCultural** | 文化資本 (ブランド、伝統、創作物) | `capital-cultural.catalog`, `capital-cultural.valuation` | `entity.*`, `graph.cross-type`, `agent.call` (→ CreativeWork) |
| **CapitalPolitical** | 政治資本 (規制影響力、政策関与) | `capital-political.map`, `capital-political.risk` | `entity.*`, `graph.traverse` |
| **CapitalReputational** | 評判資本 (ESG 評価、信頼スコア) | `capital-reputational.score`, `capital-reputational.monitor` | `entity.*`, `graph.traverse` |
| **CapitalSocialNetwork** | 社会ネットワーク資本 (接続、影響力) | `capital-social.analyze`, `capital-social.centrality` | `entity.*`, `graph.traverse`, `agent.call` (→ Party) |
| **CapitalOwnership** | 所有権関係 entity | `ownership.chain`, `ownership.transfer` | `entity.*`, `graph.traverse` |
| **CapitalProto** | 資本 proto 定義スキーマ管理 | `capital-proto.schema`, `capital-proto.validate` | `entity.read` |
| **CapitalQueries** | 資本横断クエリ agent | `capital-queries.aggregate`, `capital-queries.compare` | `graph.*`, `agent.call` (→ Capital*) |
| **CapitalMigrations** | 資本データ移行 agent | `capital-migrations.plan`, `capital-migrations.execute` | `entity.*`, `graph.*` |
| **Ownership** | 汎用所有関係 CRUD | `ownership.create`, `ownership.trace` | `entity.*`, `graph.traverse` |
| **OwnershipProto** | 所有関係 proto 定義 | `ownership-proto.schema` | `entity.read` |
| **OwnershipQueries** | 所有関係横断クエリ | `ownership-queries.chain`, `ownership-queries.ultimate-beneficiary` | `graph.*` |
| **OwnershipMigrations** | 所有データ移行 | `ownership-migrations.execute` | `entity.*`, `graph.*` |

#### Sales & CRM Domain

| Entity Agent | 責任 | Agent tools | 権限 |
|---|---|---|---|
| **Opportunity** | 商談管理 + パイプライン | `opportunity.create`, `opportunity.forecast`, `opportunity.close` | `entity.*`, `agent.call` (→ Customer, Lead) |
| **SalesActivity** | 営業活動ログ (訪問、電話、メール) | `sales-activity.log`, `sales-activity.timeline` | `entity.*`, `graph.traverse` |
| **Campaign** | マーケティングキャンペーン管理 | `campaign.launch`, `campaign.measure`, `campaign.leads` | `entity.*`, `agent.call` (→ Lead) |
| **CommissionPlan** | 手数料プラン定義 | `commission-plan.create`, `commission-plan.simulate` | `entity.*` |
| **CommissionCalculation** | 手数料計算実行 | `commission-calc.run`, `commission-calc.payout` | `entity.*`, `agent.call` (→ CommissionPlan, Opportunity) |

#### Project & Task Domain

| Entity Agent | 責任 | Agent tools | 権限 |
|---|---|---|---|
| **Project** | プロジェクト entity の CRUD + チーム構成 | `project.create`, `project.status`, `project.team` | `entity.*`, `agent.broadcast` (domain lead) |
| **Projecttask** | タスク管理 + 依存関係 | `task.create`, `task.assign`, `task.dependencies` | `entity.*`, `graph.traverse`, `agent.call` (→ Employee) |
| **Projectfinancial** | プロジェクト財務 (予算、実績、予測) | `project-financial.budget`, `project-financial.burn-rate` | `entity.*`, `agent.call` (→ CapitalFinancial) |

#### Legal & Compliance Domain

| Entity Agent | 責任 | Agent tools | 権限 |
|---|---|---|---|
| **LegalDocument** | 法的文書 (契約書、訴状、判決) 管理 | `legal-doc.create`, `legal-doc.search`, `legal-doc.precedent` | `entity.*`, `graph.traverse` |
| **Contract** | 契約 entity の CRUD + 期限管理 | `contract.create`, `contract.renew`, `contract.obligations` | `entity.*`, `agent.call` (→ Party, LegalEntity) |
| **Patent** | 特許情報管理 + IP ポートフォリオ | `patent.register`, `patent.search`, `patent.citations` | `entity.*`, `graph.traverse` |
| **Certificate** | 資格・認証管理 | `certificate.issue`, `certificate.verify`, `certificate.expiry` | `entity.*`, `graph.traverse` |
| **ExchangeComplianceOfficer** | 取引所コンプライアンス担当管理 | `compliance-officer.assign`, `compliance-officer.audit-log` | `entity.*`, `graph.traverse` |
| **CreditCheck** | 与信チェック実行 + 結果管理 | `credit-check.run`, `credit-check.history` | `entity.*`, `agent.call` (→ Party, BankAccount) |
| **LaborInsuranceProcedure** | 労働保険手続き管理 | `labor-insurance.file`, `labor-insurance.status` | `entity.*` |
| **SocialInsuranceProcedure** | 社会保険手続き管理 | `social-insurance.file`, `social-insurance.status` | `entity.*` |
| **SubsidyApplication** | 補助金申請管理 | `subsidy.apply`, `subsidy.status`, `subsidy.report` | `entity.*`, `agent.call` (→ LegalEntity) |

#### IT & Infrastructure Domain (`ci:*`)

| Entity Agent | 責任 | Agent tools | 権限 |
|---|---|---|---|
| **Ci** | Configuration Item (CI) の CRUD | `ci.create`, `ci.search`, `ci.impact-analysis` | `entity.*`, `agent.broadcast` (domain lead) |
| **CiRelationship** | CI 間の DEPENDS_ON / RELATED_TO 関係 | `ci-rel.create`, `ci-rel.dependency-graph` | `entity.*`, `graph.traverse` |
| **Citype** | CI 分類マスタ | `citype.create`, `citype.hierarchy` | `entity.read`, `entity.write` |
| **InfraDns** | DNS レコード entity | `infra-dns.create`, `infra-dns.resolve`, `infra-dns.audit` | `entity.*` |
| **InfraFile** | ファイルシステム entity | `infra-file.create`, `infra-file.scan`, `infra-file.integrity` | `entity.*` |
| **InfraIp** | IP アドレス entity | `infra-ip.create`, `infra-ip.scan`, `infra-ip.geolocation` | `entity.*` |
| **InfraWebpage** | Web ページ entity | `infra-webpage.create`, `infra-webpage.crawl`, `infra-webpage.screenshot` | `entity.*`, `ingest.external` |
| **Ip** | 知的財産 (IP) entity | `ip.register`, `ip.search`, `ip.valuation` | `entity.*`, `graph.traverse` |
| **DeviceCamera** | カメラデバイス entity | `device-camera.register`, `device-camera.status` | `entity.*` |
| **Secret** | シークレット (API key, credential) entity | `secret.store`, `secret.rotate`, `secret.audit` | `entity.*` (org_id=owner のみ write) |
| **StorageQuota** | ストレージ割り当て管理 | `storage-quota.check`, `storage-quota.allocate` | `entity.*` |

#### Location & Geospatial Domain (`location:*`)

| Entity Agent | 責任 | Agent tools | 権限 |
|---|---|---|---|
| **LocationAddress** | 住所 entity + ジオコーディング | `address.create`, `address.geocode`, `address.normalize` | `entity.*`, `graph.traverse` |
| **LocationBuilding** | 建物 entity | `building.create`, `building.tenants`, `building.floor-plan` | `entity.*`, `graph.traverse` |
| **GeospatialFeature** | GeoJSON feature entity (ポリゴン、ライン) | `geospatial.create`, `geospatial.within`, `geospatial.intersects` | `entity.*` |

#### Logistics & Supply Chain Domain

| Entity Agent | 責任 | Agent tools | 権限 |
|---|---|---|---|
| **LogisticsContainer** | コンテナ追跡 entity | `container.track`, `container.route`, `container.contents` | `entity.*`, `graph.traverse` |
| **LogisticsHub** | 物流拠点 entity | `hub.create`, `hub.capacity`, `hub.throughput` | `entity.*`, `graph.traverse` |
| **LogisticsRailway** | 鉄道路線 entity | `railway.create`, `railway.schedule`, `railway.capacity` | `entity.*` |
| **LogisticsVehicle** | 車両 entity | `vehicle.register`, `vehicle.track`, `vehicle.maintenance` | `entity.*` |
| **LogisticsVessel** | 船舶 entity | `vessel.register`, `vessel.track`, `vessel.port-calls` | `entity.*` |
| **SupplyCompany** | サプライヤー企業 entity | `supply-company.evaluate`, `supply-company.risk`, `supply-company.orders` | `entity.*`, `agent.call` (→ LegalEntity) |
| **SupplyFamily** | 製品ファミリー分類 | `supply-family.catalog`, `supply-family.components` | `entity.*` |
| **SupplyPerson** | サプライチェーン担当者 entity | `supply-person.contact`, `supply-person.responsibilities` | `entity.*`, `agent.call` (→ Contact) |
| **ManufacturingPlant** | 製造工場 entity | `plant.create`, `plant.capacity`, `plant.output` | `entity.*`, `graph.traverse` |
| **ProcessingPlant** | 加工工場 entity | `processing-plant.create`, `processing-plant.throughput` | `entity.*` |
| **MaterialSourceFiber** | 繊維原料ソース entity | `material-fiber.source`, `material-fiber.availability` | `entity.*` |
| **MaterialSourceFood** | 食品原料ソース entity | `material-food.source`, `material-food.safety` | `entity.*` |
| **MaterialSourceIron** | 鉄鉱石原料ソース entity | `material-iron.source`, `material-iron.grade` | `entity.*` |
| **MaterialSourcePetroleum** | 石油原料ソース entity | `material-petroleum.source`, `material-petroleum.reserves` | `entity.*` |

#### Gold & Mining Domain

| Entity Agent | 責任 | Agent tools | 権限 |
|---|---|---|---|
| **GoldCorporation** | 金関連企業 entity | `gold-corp.profile`, `gold-corp.production` | `entity.*`, `agent.call` (→ LegalEntity) |
| **GoldDistribution** | 金流通ネットワーク entity | `gold-dist.track`, `gold-dist.chain-of-custody` | `entity.*`, `graph.traverse` |
| **GoldMiningLand** | 金鉱区 entity | `gold-land.register`, `gold-land.reserves`, `gold-land.permits` | `entity.*` |
| **GoldTechnology** | 金採掘技術 entity | `gold-tech.catalog`, `gold-tech.efficiency` | `entity.*` |

#### Communication & Collaboration Domain

| Entity Agent | 責任 | Agent tools | 権限 |
|---|---|---|---|
| **Mail** | メール entity | `mail.send`, `mail.search`, `mail.thread` | `entity.*` |
| **Mailaddress** | メールアドレス entity + 検証 | `mailaddress.verify`, `mailaddress.search` | `entity.*` |
| **PhoneNumber** | 電話番号 entity + 検証 | `phone.verify`, `phone.search`, `phone.carrier` | `entity.*` |
| **Message** | メッセージ entity | `message.send`, `message.search`, `message.thread` | `entity.*` |
| **CommunicationMeeting** | 会議 entity | `meeting.schedule`, `meeting.minutes`, `meeting.action-items` | `entity.*`, `agent.call` (→ Calendar) |

#### Content & Knowledge Domain

| Entity Agent | 責任 | Agent tools | 権限 |
|---|---|---|---|
| **CreativeWork** | 創作物 entity (記事、動画、楽曲) | `creative-work.create`, `creative-work.license`, `creative-work.citations` | `entity.*`, `graph.traverse` |
| **GameMedia** | ゲームメディア entity | `game-media.catalog`, `game-media.metadata` | `entity.*` |
| **Chart** | チャート・ダッシュボード entity | `chart.create`, `chart.render`, `chart.data-source` | `entity.*` |
| **Sheet** | スプレッドシート entity | `sheet.create`, `sheet.query`, `sheet.export` | `entity.*` |
| **Workbook** | ワークブック entity | `workbook.create`, `workbook.sections`, `workbook.export` | `entity.*` |
| **WorkbookShare** | ワークブック共有管理 | `workbook-share.grant`, `workbook-share.revoke`, `workbook-share.list` | `entity.*` |
| **FileShare** | ファイル共有 entity | `file-share.create`, `file-share.permissions`, `file-share.link` | `entity.*` |
| **FileVersion** | ファイルバージョン管理 | `file-version.create`, `file-version.diff`, `file-version.rollback` | `entity.*` |
| **Module** | 学習モジュール entity | `module.create`, `module.content`, `module.prerequisites` | `entity.*`, `graph.traverse` |

#### Learning & Certification Domain

| Entity Agent | 責任 | Agent tools | 権限 |
|---|---|---|---|
| **Course** | 研修コース entity | `course.create`, `course.curriculum`, `course.enroll` | `entity.*`, `agent.call` (→ Module) |
| **Enrollment** | 受講登録 entity | `enrollment.create`, `enrollment.progress`, `enrollment.complete` | `entity.*`, `agent.call` (→ Course) |
| **TrainingSession** | 研修セッション entity | `training-session.schedule`, `training-session.attendance` | `entity.*` |
| **TrainingCisa** | CISA 研修 entity | `training-cisa.curriculum`, `training-cisa.progress` | `entity.*` |
| **TrainingCissp** | CISSP 研修 entity | `training-cissp.curriculum`, `training-cissp.progress` | `entity.*` |
| **QualificationCisa** | CISA 資格 entity | `qualification-cisa.verify`, `qualification-cisa.renewal` | `entity.*`, `agent.call` (→ Certificate) |
| **QualificationCissp** | CISSP 資格 entity | `qualification-cissp.verify`, `qualification-cissp.renewal` | `entity.*`, `agent.call` (→ Certificate) |
| **Quiz** | クイズ entity | `quiz.create`, `quiz.submit`, `quiz.score` | `entity.*` |

#### Calendar & Event Domain

| Entity Agent | 責任 | Agent tools | 権限 |
|---|---|---|---|
| **Calendar** | カレンダー entity | `calendar.create`, `calendar.events`, `calendar.availability` | `entity.*`, `graph.traverse` |
| **Event** | イベント entity | `event.create`, `event.attendees`, `event.reschedule` | `entity.*`, `agent.call` (→ Calendar) |
| **Activity** | アクティビティログ entity | `activity.log`, `activity.timeline`, `activity.search` | `entity.*` |

#### Financial Operations Domain

| Entity Agent | 責任 | Agent tools | 権限 |
|---|---|---|---|
| **BankAccount** | 銀行口座 entity | `bank-account.create`, `bank-account.balance`, `bank-account.transactions` | `entity.*` (org_id=owner のみ write) |
| **CryptoAddress** | 暗号通貨アドレス entity | `crypto.create`, `crypto.balance`, `crypto.transactions` | `entity.*` |
| **Product** | 製品 entity | `product.create`, `product.catalog`, `product.pricing` | `entity.*`, `graph.traverse` |
| **ServiceTicket** | サポートチケット entity | `ticket.create`, `ticket.assign`, `ticket.resolve` | `entity.*`, `agent.call` (→ Employee) |

#### Manufacturing Process Domain (tukuru)

| Entity Agent | 責任 | Agent tools | 権限 |
|---|---|---|---|
| **AutomobileManufacturingProcess** | 自動車製造工程管理 (ISIC C29) | `auto-mfg.process-step`, `auto-mfg.bom`, `auto-mfg.quality` | `entity.*`, `agent.call` (→ ManufacturingPlant, MaterialSource*) |
| **ComputerManufacturingProcess** | コンピュータ製造工程管理 (ISIC C26) | `computer-mfg.process-step`, `computer-mfg.bom`, `computer-mfg.yield` | `entity.*`, `agent.call` (→ ManufacturingPlant) |
| **BuildingConstructionProcess** | 建設工程管理 (ISIC F41) | `construction.phase`, `construction.schedule`, `construction.safety` | `entity.*`, `agent.call` (→ LocationBuilding) |
| **SmartphoneManufacturingProcess** | スマートフォン製造工程管理 (ISIC C26) | `smartphone-mfg.process-step`, `smartphone-mfg.bom`, `smartphone-mfg.test` | `entity.*`, `agent.call` (→ ManufacturingPlant) |

#### Misc / System

| Entity Agent | 責任 | Agent tools | 権限 |
|---|---|---|---|
| **Cell** | データセル entity (表の最小単位) | `cell.create`, `cell.update`, `cell.formula` | `entity.*` |
| **2** | 汎用 entity v2 (レガシー互換) | `entity-v2.crud` | `entity.*` |
| **A3znhncn** | 汎用 entity (scaffold) | `entity.crud` | `entity.*` |

### Agent Routing Rules

1. **Capability discovery**: `kotoba-kotodama.Invoke("", "contact.search", params)` → Host が Contact agent を自動発見して呼び出し
2. **Domain broadcast**: domain lead agent (Party, Capital, Ci, Project) は `kotoba-kotodama.Invoke("", method, params)` で domain 内 agent に通知
3. **Cross-domain call**: `agent.call` 権限を持つ agent は `kotoba-kotodama.Invoke(did, method, params)` で直接他 domain の agent を呼べる
4. **Org isolation**: conversation task は `org_id` でスコープ。異なる org の agent 間の通信は禁止
5. **AT record trail**: 全 conversation state は `wproto.convo.*` 系レコードで永続化

## SQL Removal (2026-04-13)

**Status: REMOVED.** SQL architecture (host imports + transpiler + Drizzle ORM) is fully archived. Use Kysely + Hyperdrive RisingWave for all graph queries.

### Removed (2026-04-13)

| Component | Location |
|---|---|
| `sqlQuery` / `sqlQueryJson` / `sqlBatchExec` host imports | deleted from `host-imports.ts` + `types.ts` (HostImports interface) |
| `sql.ts` (host-sdk) | deleted (was deprecation stub) |
| `setSqlRpc` / `setSqlFetch` / `sqlQueryAsync` / `sqlExecAsync` / `getKagamiRpc` | removed |
| `SQL*` types (`SqlResult`, `SqlParam`, `SqlBatchStmt`, `SqlBatchStatementRaw`) | removed from `types.ts` |
| `drizzle.ts` (host-sdk) | archived → `_archive/2026-04-13-non-kysely/` |
| `30-graph/graph-schema/src/{schema,repo-log,promoted-columns,graphar-db.gen}.ts` | archived → `_archive/2026-04-13-non-kysely/` |
| `30-graph/kagami/src/sql/` (5 files) | archived → `_archive/30-graph/2026-04-13-kagami-sql/` |
| `30-graph/kagami-sql-compiler/` (entire package) | archived → `_archive/30-graph/kagami-sql-compiler-260412/` |
| `30-graph/kagami-provider/` (entire package) | archived → `_archive/30-graph/kagami-provider-260412/` |
| `30-graph/graph-schema/src/p10.gen.ts` | relocated to `50-infra/cloudflare/workers/graph/p10-tables.ts` (worker-local; sole consumer was the graph Worker SQL emitter) |
| `70-tools/scripts/lint/p10-write-schema-guard.mjs` | archived (referenced non-existent `p10.ts`, dead lint script) |

### Migration Pattern

```typescript
import { createKyselyDb } from "@etzhayyim/kotoba-kotodama-host-sdk";
import type { Database } from "@etzhayyim/graph-schema";

const db = createKyselyDb(env.HYPERDRIVE);
const rows = await db
  .selectFrom("vertex_employee")
  .select(["name", "salary"])
  .where("id", "=", empId)
  .execute();
```

### Pending Work

- 60-apps 内に残る `sqlQueryJson` callsite (baminiku appview.svelte, tsukuru test, states convert script) は別 phase で順次移行
