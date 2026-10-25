# ADR 0229: T8.3 pure multi-export EDN kit body with true-set uniqueness

- Status: Accepted
- Date: 2026-08-01
- Depends: ADR 0224 pure EDN append-set; ADR 0209–0211 pure multi-export encode;
  compiler set-in-record (`8952a068`)

## Context

ADR 0224 ships set-backed multi-header EDN append (`[:set :string]` + guest
record accumulator). ADR 0209–0211 ship pure multi-export request/result EDN
with **substring** `:name "…"` uniqueness. Component multi-export (0221–0227)
closed the reject-path Component plane with element-bound membership. Hosts
still lacked a **single pure package** that composes true-set append with
request/result encode — the multi-export pure surface and true-set append
lived as separate packages.

## Decision

1. Ship **`http-edn-set-package`** (wasm32, `kotoba:typed`): multi-export
   pure kit body —
   - `http_headers_edn_set_{begin,append,edn,code,count}` (ADR 0224 surface)
   - `http_request_edn_set(st, url, body, timeout-ms)` — fail-closed on sticky
     code / timeout / forbidden atoms / headers shape
   - `http_result_ok_edn` / `http_result_err_edn` (fixed-depth pure arms)
   - `main` → **`-9002`** (two unique headers, non-empty request+results, then
     dup name → code `-9`, count was 2)
2. Uniqueness is **`typed-set-contains`** only (not substring marker scan).

Honesty:

- Pure/compiler twin multi-export; does **not** replace Component multi-export
  (0221–0227 element-bound / names-add remain Canonical WAT path).
- Bounded set (≤32) — not unbounded hash-set / W4 recursive nested EDN ADT.
- Does **not** flip `:wasm-aot :implemented`.

## Evidence

- compiler ≥ `8952a068`
- Package sha `f6dd4b1b…`; KIR `main` → `-9002`
- ops kit registry + sha tests

## Related

- T8.3; ADR 0209–0211, 0221–0227
- Follow-up: W4 recursive nested EDN; only then `:wasm-aot :implemented`
