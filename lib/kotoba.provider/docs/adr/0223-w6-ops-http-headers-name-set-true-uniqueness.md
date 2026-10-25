# ADR 0223: T8.3 true header-name uniqueness via typed-set

- Status: Accepted
- Date: 2026-08-01
- Depends: ADR 0189 headers-set packing; compiler set-in-record (`8952a068`);
  typed-set `[:set :string]` (max 32)

## Context

ADR 0189/0211/0216 enforce multi-header packing and reject-path uniqueness via
**substring scan** of `:name "…"` markers (or host sequencing without name
storage). That is not a true set: order-dependent, scan-collision risk, and
honest notes still list “true set / W4” as open for `:wasm-aot :implemented`.

Compiler set-in-record (compiler#464) locks that guest records may carry
`[:set T]` fields. Header names are ordinary strings — the residual is product
use of `[:set :string]` membership, not a new language feature.

## Decision

1. Ship **`http-headers-name-set`** (wasm32, `kotoba:typed`): guest record
   `:hdr/name-set` with `[:names [:set :string]]` + sticky `:code`.
2. Exports: `http_headers_names_begin` / `_add` / `_pair` / `_code` / `_count`
   + `main` proof (`-9002` = duplicate after two unique pairs).
3. Codes: 0187/0188 name/value policy plus **`-9` duplicate** via
   `typed-set-contains` (true set membership).

Honesty:

- Bounded set (≤32) — not unbounded hash-set / W4 recursive EDN ADT.
- Does **not** re-ship reject-path EDN Components on set uniqueness yet.
- Does **not** flip `:wasm-aot` to `:implemented` (W4 recursive nested EDN
  + Component twin without substring honesty still open).

## Evidence

- compiler ≥ `8952a068` (set-in-record)
- Package sha `5b61d178…`; KIR main → `-9002`
- ops kit registry + sha tests

## Related

- T8.3; ADR 0189, 0211, 0216, 0222
- Follow-up: Component twin; wire uniqueness into reject-path append;
  W4 recursive EDN; only then `:wasm-aot :implemented`
