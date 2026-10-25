# com-backblaze-secure

A **secure Backblaze B2 MCP server**: bucket + capability allowlisting,
mandatory redaction of credential material from every tool response and
audit-log line, and an append-only audit ledger of every call.

Design is authoritative in
**`90-docs/adr/2607152322-kotoba-lang-com-backblaze-secure-b2-mcp-server.md`**
(superproject `com-junkawasaki/root`).

## Why not the community `backblaze-mcp` (npm)?

That server takes `B2_APPLICATION_KEY_ID`/`B2_APPLICATION_KEY` as plain env
vars and gives any connected MCP client full, unfiltered access to whatever
buckets that key can reach — no bucket allowlist, no capability gate
(list/read vs. write vs. delete), and no redaction of the raw key material
that `b2` CLI JSON output happens to include. This project exists because
that failure mode is not hypothetical: in the session that led to this repo,
manually running `b2 account authorize` and printing its JSON output
leaked a scoped application key into a chat transcript. Every invariant
below exists to make that specific mistake structurally impossible for an
MCP tool call.

## Security invariants

1. **Redaction is mandatory, not best-effort.** Every `b2` CLI subprocess
   result is passed through `com-backblaze-secure.redact/redact`
   (recursive, denylist-keyed: `applicationKey`, `applicationKeyId`,
   `accountAuthToken`, `secretAccessKey`, `accessKeyId`, etc.) before it is
   returned to an MCP caller *or* written to the audit ledger.
2. **Bucket + capability allowlist.** A tool call can only touch a bucket
   and capability (`:list`/`:read`/`:write`/`:delete`) explicitly present in
   `config/com-backblaze-secure.edn`. An unlisted bucket/capability is
   rejected before any `b2` subprocess is spawned. `config/example.edn`
   ships with `:list`/`:read` only — `:write`/`:delete` are opt-in per
   bucket.
3. **No new secret-storage scheme.** Credentials resolve via
   `env → 1password → keychain`, the exact order and reference shape
   already used by the superproject's `manifest/repos.edn` `:b2
   :credentials` / `scripts/b2-creds.cljs`, generalized to any number of
   named buckets.
4. **Stateless auth per call.** Credentials are passed to `b2` only via
   `B2_APPLICATION_KEY_ID`/`B2_APPLICATION_KEY` env vars scoped to a single
   subprocess invocation. `b2 account authorize` (which persists to
   `~/.b2_account_info`, global mutable state, and is what leaked a key in
   the first place) is never called.
5. **Append-only audit ledger.** Every tool call appends one line to
   `~/.com-backblaze-secure/audit.jsonl` (or the configured `:audit :path`)
   — `{ts, tool, bucket, capability, outcome}`, never secret values.

## Requirements

- [`nbb`](https://github.com/babashka/nbb) (the runtime — this repo runs as
  a long-lived stdio process, which per this workspace's runtime-priority
  rule has no practical kotoba-wasm/clojurewasm/cljs hosting path yet, so
  nbb is the current correct choice).
- The official [`b2` CLI](https://github.com/Backblaze/B2_Command_Line_Tool)
  on `PATH` (data-plane operations shell out to it — no B2/S3 signing is
  reimplemented here).
- A sibling checkout of [`kotoba-lang/mcp`](https://github.com/kotoba-lang/mcp)
  (portable `.cljc` MCP manifest + JSON-RPC dispatch kernel this repo
  depends on for everything except the stdio transport and tool
  implementations).
- A sibling checkout of
  [`kotoba-lang/secret-resolve`](https://github.com/kotoba-lang/secret-resolve)
  (shared env/1Password/Keychain credential resolution, ADR-2607161000 —
  this repo's own `credentials.cljs` is a thin wrapper around it, not an
  independent implementation).

## Setup

```bash
cp config/example.edn config/com-backblaze-secure.edn
# edit config/com-backblaze-secure.edn: which buckets, which capabilities,
# which credential refs (op:// paths / keychain service names — never a
# raw secret value)
```

## Run

```bash
kbb --backend sci --classpath "src:../org-anthropic-mcp/src:../secret-resolve/src" src/com_backblaze_secure/server.cljk
```

(`../org-anthropic-mcp` and `../secret-resolve` are the sibling
`kotoba-lang/mcp` / `kotoba-lang/secret-resolve` checkout paths when all
three repos are laid out side by side under `orgs/kotoba-lang/` — adjust
the `--classpath` argument directly if your layout differs. Set
`COM_BACKBLAZE_SECURE_CONFIG` to point at a config file outside the repo.)

### MCP client config (e.g. Claude Code `.mcp.json`)

```json
{
  "mcpServers": {
    "com-backblaze-secure": {
      "command": "nbb",
      "args": ["--classpath", "src:../org-anthropic-mcp/src:../secret-resolve/src", "src/com_backblaze_secure/server.cljk"],
      "cwd": "/absolute/path/to/orgs/kotoba-lang/com-backblaze-secure"
    }
  }
}
```

## Tools

Only registered when at least one configured bucket grants the
corresponding capability:

| Tool | Capability | Purpose |
|---|---|---|
| `b2_list_buckets` | `:list` | List allowlisted buckets (response filtered to allowlisted names). |
| `b2_list_files` | `:read` | Recursively list files in one allowlisted bucket. |
| `b2_file_info` | `:read` | Metadata for one file. |
| `b2_download_file` | `:read` | Download one file to a local path. |
| `b2_upload_file` | `:write` | Upload one local file. |
| `b2_delete_file` | `:delete` | Delete the current version of one file — never recursive/wildcard. |

## Test

```bash
kbb -M:test   # redact/config pure-logic tests (portable .cljc)
```

## Known limitations

- **Single-threaded and synchronous.** Every `b2` CLI call and every
  credential-resolution call (`op read`, `security find-generic-password`)
  runs via `execFileSync`, which blocks the whole stdio server until it
  returns. A slow upload/download blocks every other tool call until it
  finishes. Credential-resolution calls have a fixed 5s timeout per source
  (confirmed empirically: a stale `op` CLI session hangs indefinitely on
  `op read` rather than failing fast, which would otherwise wedge the
  server on the very first tool call). `b2` data-plane calls default to a
  300s timeout, overridable via `COM_BACKBLAZE_SECURE_B2_TIMEOUT_MS` for
  legitimately large transfers.
- **Output size ceiling.** `execFileSync` buffers a subprocess's entire
  stdout in memory; a recursive `b2_list_files` on a bucket with enough
  objects can exceed Node's default 1MB `maxBuffer` (confirmed empirically —
  a few hundred files already did). Raised to 200MB by default, overridable
  via `COM_BACKBLAZE_SECURE_B2_MAX_BUFFER_BYTES`; there is no pagination, so
  an extremely large bucket can still fail this call outright rather than
  return a partial/truncated listing.
- The stdio transport implements the current MCP wire format (newline-
  delimited JSON) and a minimal `initialize`/`tools list`/`tools call`
  surface via `kotoba-lang/mcp`; it has not been validated against every
  MCP client's protocol-version negotiation nuances. Report gaps as
  issues rather than assuming full spec parity.
- `redact` matches on map **key** names; a secret value placed somewhere
  other than a denylisted key's value (e.g. embedded inside a free-text
  error message from `b2`) is not caught. `b2-cli`'s `:err`/`:stdout`
  fields are still passed through `redact` for defense in depth, but this
  is not a substitute for the key-based denylist being complete.
