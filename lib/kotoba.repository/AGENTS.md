# etzhayyim-project-repository

ADR-0039 **Repository-in-Graph** backing Worker for `repository.etzhayyim.com`. Owns the git object model (blob / tree / commit / ref) over Actor DID, and drives FaaS build dispatch via Cloudflare Workers for Platforms.

## Scope

- SSoT: `vertex_repository_{blob,tree,commit,ref}` + 6 edge labels (ADR-0039 §1).
- Repository ≡ Actor DID. `vertex_actor` is reused; no new repository entity.
- Lexicons: `00-contracts/lexicons/com/etzhayyim/repository/*.json` (13 files — 12 method + 1 record).
- **Not a PDS replacement.** `com.etzhayyim.repository.*` is served by this Worker directly; PDS (`atproto.etzhayyim.com`) still owns `app.bsky.*`, `com.atproto.*`, `chat.bsky.convo.*`, `com.etzhayyim.vault.*`, `com.etzhayyim.signal.*` per ADR-0036.

## Architecture

```
Browser / CLI / yoro code-editor
  → repository.etzhayyim.com/xrpc/com.etzhayyim.repository.*
  → this Worker (etzhayyim-wasm-repository-r3p0s1t0)
     ├─ createBlob / createTree / createCommit  → vertex_repository_* INSERT (Hyperdrive, 1-RTT per ADR-0036)
     ├─ createRef / updateRef                   → vertex_repository_ref + edge_repository_ref_points rewrite
     │                                             ↓ sdk.pds.dispatch({type: "com.etzhayyim.repository.refUpdate"})
     │                                             → firehose broadcast
     │                                             → CF Container build runner (trigger)
     ├─ getBlob / getTree / getCommit           → Kysely SELECT on vertex_repository_*
     ├─ log / diff / blame                      → commit DAG walk (edge_repository_parent)
     └─ listRefs                                → subtree query via edge_path_child (ADR-0019)
```

## Component

| Component | Folder | Role |
|---|---|---|
| repository-api | `appview/etzhayyim-wasm-repository-r3p0s1t0/` | XRPC API + static SPA (minimal UI shell; authoring surface is yoro/code-editor) |

## Graph Tables

See `30-graph/graph-schema/migrations/20260420100000_vertex_repository_tables.ts`.

| Table | Role |
|---|---|
| `vertex_repository_blob` | content-addressed file (sha256 hex), >16KB tiered to B2 |
| `vertex_repository_tree` | directory snapshot, tree_hash = sha256(canonical entry list) |
| `vertex_repository_commit` | commit object with ES256 signature (ADR-0010) |
| `vertex_repository_ref` | branch / tag / head pointer |
| `edge_repository_parent` | commit → commit (N parents for merge) |
| `edge_repository_tree` | commit → root tree |
| `edge_repository_entry` | tree → blob\|tree (`path` + `mode`) |
| `edge_repository_authored_by` | commit → author DID (`vertex_actor`) |
| `edge_repository_ref_points` | **唯一の mutable edge** — rewritten on updateRef |
| `edge_repository_ref_owner` | ref → owning Actor DID |

## Build & Deploy

```bash
cd 60-apps/etzhayyim-project-repository/appview/etzhayyim-wasm-repository-r3p0s1t0
etzhayyim deploy --smoke-url https://r3p0s1t0.etzhayyim.com/health
```

Routes (per `kotodama.jsonld`):
- `r3p0s1t0.etzhayyim.com/*` (nanoid direct)
- `repository.etzhayyim.com/*` (vanity)

## Key Invariants (ADR-0039)

1. `vertex_repository_{blob,tree,commit}` は append-only。UPDATE / DELETE 禁止。
2. `edge_repository_ref_points` が唯一の mutable write。rollback / fast-forward / force 全て 1 edge 差し替えで完結。
3. `createCommit` は `signature_es256` required。bootstrap 例外のみ許容。
4. Repository 概念は `vertex_actor` (Actor DID) を再利用。新規 `vertex_repository` は作らない。
5. Project / App level の "repo view" は `edge_path_child*` subtree スキャンで derived query として得る。

## Related

- ADR-0039: `90-docs/adr/0039-repository-in-graph-faas.md`
- ADR-0019: atproto-native identifier topology (path-DID hierarchy = sub-repo tree)
- ADR-0010: per-DID ES256 signing key custody (commit 署名)
- ADR-0036: Worker-direct Hyperdrive persistence (write path)
- ADR-0038: Actor-as-Data (manifest side — この repository は code side)
- Lexicons: `00-contracts/lexicons/com/etzhayyim/repository/`
- Schema: `30-graph/graph-schema/migrations/20260420100000_vertex_repository_tables.ts`

## Phase Status

| Phase | Scope | Status |
|---|---|---|
| A | Object DB (blob/tree/commit + edges) | **this PR — schema + lexicon + skeleton** |
| B | Ref layer (vertex_repository_ref + ref_points + ref_owner) | schema included in this PR; handler impl pending |
| C | WFP dispatcher + CF Container build runner | not started |
| D | yoro WebContainer code-editor | not started |
| E | Full rollout to existing T3 actors | not started |
