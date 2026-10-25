# ADR 0270: T8.3 guest host inject parity (git/entropy/fs-read)

- Status: Accepted
- Date: 2026-08-01
- Depends: ADR 0265–0268 guest host surfaces; ADR 0262 inject framework

## Context

HTTP/secret/process/scoped-fs-write already had semantic inject arms
(`:ok-200` / `:secret-value` / `:process-ok` / `:fs-written`) plus
deny-closed helpers. Git, entropy, and scoped-fs **read** only had
`:echo` — enough for cap-path proof, incomplete for reply-arm inject
and fail-closed tests.

## Decision

1. Add inject modes on `host-options-js`:
   | Mode | Cap | Fixed reply |
   |------|-----|-------------|
   | `:git-ok` | 22 | `{:tag :ok :exit 0 :stdout "ok" :stderr ""}` |
   | `:entropy-hex` | 23 | `{:tag :hex :hex "0123456789abcdef"}` |
   | `:fs-content` | 19 | `{:tag :content :content "payload"}` |
2. Ship deny helpers: `git-w4-host-run-denied`,
   `entropy-w4-host-draw-denied`, `scoped-fs-w4-host-read-denied`.
3. Kit-readiness: evidence lines for missing `*-w4-host-edn` packages
   (secret/git/entropy/scoped-fs).
4. Does **not** flip `:wasm-aot :implemented` — host I/O remains authority.

## Evidence

- Optional browser-host unit tests for ok/hex/content inject + deny

## Related

- Completes guest host inject surface parity after ADR 0260–0268
