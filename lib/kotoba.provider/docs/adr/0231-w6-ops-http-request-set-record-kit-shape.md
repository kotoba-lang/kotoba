# ADR 0231: T8.3 pure kit-shaped request with set-of-header-records

- Status: Accepted
- Date: 2026-08-01
- Depends: compiler set-in-record (`8952a068`); ADR 0223–0224 name/set EDN;
  ADR 0229 pure multi-export set package

## Context

HTTP kit `:request` declares
`[:headers [:set [:record :kotoba.http/header …]]]`. Prior pure packages held
either host-sequenced packing walks (0189/0193) or **string** EDN vectors with
name-set side channel (0224/0229). No pure guest record yet mirrored the kit
set-of-header-records shape while still enforcing HTTP **name** uniqueness.

## Decision

1. Ship **`http-request-set-record`** (wasm32, `kotoba:typed`):
   - `:hdr/pair` record `{name,value}`
   - `:hdr/req` record with `:headers [:set [:ref :hdr/pair]]`, parallel
     `:names [:set :string]`, url/body/timeout, sticky `:code`
   - Exports: `http_req_{begin,add_header,code,count,edn}` + `main` → **-9002**
2. Name uniqueness via `typed-set-contains` on `:names` (not full-record-only).
3. `http_req_edn` is a fixed-depth skeleton with **headers-n** from set count
   (typed-set has no iterator; full set→vector EDN fold residual).

Honesty:

- Bounded sets (≤32); not W4 recursive nested EDN ADT / unbounded hash-set.
- Does **not** flip `:wasm-aot :implemented`.
- Complements string EDN path (0229) and Component multi-ns (0230).

## Evidence

- Package sha `59a182cc…`; KIR `main` → `-9002`
- ops kit registry + sha tests

## Related

- T8.3; ADR 0189, 0209–0211, 0223–0230
- Follow-up: typed-set fold/seq for full headers EDN; W4; wasm-aot
