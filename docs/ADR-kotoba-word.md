# ADR: kotoba-word — agent-callable words with a root registry

Date: 2026-06-10
Status: Accepted (R0 implemented)
Reference design study: `~/github/kotoba-design.md` (5-architecture + SSOT comparison)
Inspiration: [HKUDS/CLI-Anything](https://github.com/HKUDS/CLI-Anything)

## Context

kotoba already had the parts of an agent-tool substrate but no unifying
abstraction:

- a handrolled MCP endpoint with **hardcoded** tool dispatch (`kotoba-server/src/mcp.rs`)
- a WASM Component Model runtime with a stateless UDF world (`kotoba-runtime::UdfExecutor`)
- ATProto lexicons under `lexicons/com/etzhayyim/apps/kotoba/`, hand-written
- no registry concept tying "a callable thing" to a name, schema, and permission set

We want local apps, web services, closures, and wasm components wrapped as
uniform agent-callable units, normalized to MCP and ATProto Lexicon.

## Decision

### Vocabulary

- **word** = `NSID + typed input/output schema + executor + caps` — the
  minimal callable unit (`crates/kotoba-word/src/word.rs`)
- **root** = where words are planted: registry + runtime + capability
  boundary + projections (`root.rs`)

### Architecture: D4 hybrid (study score 114/150)

One definition, three derived faces:

```
typed Rust closure  ──extract──▶  manifest (lockfile)  ──project──▶  MCP tools/list+call
   (authoring SSOT)                (interchange SSOT)         └────▶  ATProto lexicon docs
```

### SSOT: S2' closure-first two-stage (study score 90/110)

- **Authoring SSOT** is the typed closure signature: `Fn(I, Ctx) -> O` with
  `I: DeserializeOwned + JsonSchema`, `O: Serialize + JsonSchema`. Schemas are
  extracted by schemars; the compile-time `JsonSchema` bound *is* the
  expressiveness lint (types that can't lower to JSON Schema don't compile).
- **Interchange SSOT** is the extracted manifest (`kotoba.words.json` at repo
  root — Cargo.lock pattern). `kotoba word diff <path>` is the CI gate:
  exit 0 = unchanged, 1 = additive, 2 = breaking (removed/changed words).

### Capability model (closure-style)

A word body cannot reach the OS; it receives a `Ctx` carrying only its
declared caps (`proc:<bin>`, `net:<host>` (+ `*.` wildcard), `fs:ro|rw:<path>`).
`Ctx::exec` / `Ctx::http_get` enforce them. Registration fails if a word
requests caps the root does not grant. Wrapping follows the CLI-Anything
principle — *call the real software*: local app = `ctx.exec`, web service =
`ctx.http_get`, with `with_executor_meta` recording provenance in the manifest.

### Executors

| kind | body | travels between roots? |
|---|---|---|
| closure | in-process typed fn | no (`ref: inline`) — local words |
| process | closure delegating via `ctx.exec` | no, but provenance recorded |
| http | closure delegating via `ctx.http_get` | no, but provenance recorded |
| wasm | `kotoba-udf` component on kotoba-runtime | **yes** (`ref: blake3:<hex>`) — feature `wasm-udf`, JSON↔CBOR row convention |

### Projections (generated, never hand-written)

- **MCP** (`projection/mcp.rs`): same handrolled JSON-RPC 2.0 style as
  kotoba-server. `handle()` is transport-agnostic (mountable behind
  `POST /mcp` later); `serve_stdio()` is a complete MCP stdio server
  (`kotoba word mcp`). Tool name: `word_<suffix underscored>`.
- **Lexicon** (`projection/lexicon.rs`): one doc per word into the existing
  `lexicons/` layout. `WordMode::Query` with flat primitive params → `query`;
  anything else → `procedure`. Caps + executor provenance ride in the
  description. Note: lexicon **publication** (PDS record origination) stays
  etzhayyim-exclusive per the existing operating-entity boundary; kotoba only
  generates the docs.

## CLI

```
kotoba word list
kotoba word invoke <nsid> --input '<json>'
kotoba word manifest [--out kotoba.words.json]
kotoba word diff kotoba.words.json        # CI gate (exit 0/1/2)
kotoba word lexicons [--out-dir lexicons]
kotoba word mcp                           # MCP stdio server
```

Example root: `com.etzhayyim.apps.kotoba.word.{math.add, text.echo,
git.status, web.head}` (`examples.rs`) — pure closure, local-app wrap,
web-service wrap.

## Consequences

- Adding a word = writing one typed function. Manifest, MCP tool, and lexicon
  doc are derived; drift is impossible by construction and breaking changes
  are caught by the diff gate.
- 28 unit tests in kotoba-word; `--features wasm-udf` compiles against the
  pinned wasmtime 22 stack.

## R0 honesty / follow-ups

- wasm word e2e needs a real `kotoba-udf` guest component fixture (kotoba-clj
  `compile_kais_component_str` or a wit-bindgen guest) — executor path is
  implemented but not exercised end-to-end.
- `kotoba-server` `POST /mcp` still dispatches only its hardcoded tools;
  mounting `kotoba_word::projection::mcp::handle` behind it (with the
  AT-session auth gate) is the next increment.
- Root is in-process and static (built in `examples.rs`); dynamic registration
  (e.g. loading wasm words from the BlockStore by CID) is future work.
- `fs:*` caps are defined but no `Ctx` file API enforces them yet.
