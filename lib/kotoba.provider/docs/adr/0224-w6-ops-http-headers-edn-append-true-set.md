# ADR 0224: T8.3 pure reject-path EDN append with true set uniqueness

- Status: Accepted
- Date: 2026-08-01
- Depends: ADR 0223 name-set; compiler set-in-record (`8952a068`);
  ADR 0216 Canonical WAT `headers_edn_append` (substring twin remains)

## Context

ADR 0216 / multi-export reject kit encode multi-header EDN with **substring**
`:name "…"` uniqueness in hand-WAT. ADR 0223 shipped true set membership for
**name packing** (`[:set :string]`) but did not yet own the reject-path **EDN
append** surface. Hosts need a pure/compiler path where append uniqueness is
the same set ADT as packing — not a second marker scan.

## Decision

1. Ship **`http-headers-edn-append-set`** (wasm32, `kotoba:typed`): guest
   record `:hdr/edn-acc` with `:edn` string + `:names [:set :string]` + sticky
   `:code`.
2. Exports: `http_headers_edn_set_begin` / `_append` / `_edn` / `_code` /
   `_count` + `main` (`-9002` after Host+Accept then dup Host).
3. Dual scan rejects `"` / `\` in name/value (same reject-path atom gate as
   WAT). Uniqueness is **`typed-set-contains`** only.

Honesty:

- Pure/compiler twin of append; **does not** replace Canonical WAT 0216 yet.
- Does **not** re-ship multi-export reject Component on set uniqueness.
- Does **not** flip `:wasm-aot :implemented` (W4 recursive nested EDN +
  Component twin still open).

## Evidence

- compiler ≥ `8952a068`
- Package sha `26f6d2aa…`; KIR main → `-9002`
- ops kit registry + sha tests

## Related

- T8.3; ADR 0216, 0222, 0223
- Follow-up: Component twin; fold into multi-export reject package; W4;
  only then `:wasm-aot :implemented`
