# ADR 0243: T8.3 scoped-fs kit fixed-depth EDN request+reply package

- Status: Accepted
- Date: 2026-08-01
- Depends: fs path walk 0181 / path Component 0207; process/git EDN package pattern 0238–0241

## Context

Scoped-fs kit request/result is a fixed-depth variant (read/write request;
content/written/error result). Process and git gained pure fixed-depth EDN
packages (0238–0241). Scoped-fs needs the same pure codec surface; host store
stays host-injected.

## Decision

1. Ship **scoped-fs-edn-package** (wasm32, kotoba:typed):
   - Request: `fs_req_read_edn` (root+path), `fs_req_write_edn` (root+path+value)
   - Reply: `fs_reply_content_edn` / `fs_reply_written_edn` / `fs_reply_error_edn`
   - Path policy slice: non-empty, no leading `/`, no `..` segment, path ≤ 1024,
     value ≤ 65536, dual quote/backslash scan on string leaves
   - Root: simple keyword body `[A-Za-z0-9_-]+`
   - main → **-2313**
2. Host store remains host-injected — pure EDN codec only.
3. Does not flip wasm-aot to implemented (W4 recursive nested EDN open).

## Evidence

- Package sha `c5a52bd3…`; KIR main → -2313
- ops kit registry + sha tests

## Related

- T8.3; scoped-fs 0169/0174–0181/0207; process/git 0238–0241 pattern
