# ADR 0248: T8.3 / W4 third ops slice — true nested pair(k,v) map EDN

- Status: Accepted
- Date: 2026-08-01
- Depends: ADR 0246 headers; ADR 0247 entry-atom request/result

## Context

ADR 0247 encoded request/result maps as right-nested spines of **preformatted
entry atoms** (`":url \"…\""`). That stayed under `parametric-adt-depth 8` but
is not true nested key/value structure. Residual honesty asked for nested
records inside recursive variants — the closed schema profile **rejects**
record arms on recursive variants (compiler: schema outside closed profile /
infer crash on `[:ref :record]`).

## Decision

1. Ship **recursive-kv-edn** (wasm32, kotoba:typed):
   - Same sealed `:edn/node` = `:atom string | :pair [node node]`
   - **True kv** = `pair(atom key, atom value)` (not preformatted `"k v"` atom)
   - `header_kv_edn` — 2-field true-kv map `{:name … :value …}`
   - `headers_list_edn` — pair spine of header-map strings
   - `request_kv_edn` — **3-field** true-kv map `{:url :headers :body}`
   - `result_ok_kv_edn` / `result_err_kv_edn` — 3-field true-kv arms
   - main → **-2403**
2. Measured limits under `parametric-adt-depth 8`:
   - true-kv map entries **≤3** compile; **4** fails depth
   - therefore `timeout-ms` / `:retryable` 4th fields deferred
3. Nested records in recursive variants remain **outside closed schema** —
   language/compiler residual, not another fixed-depth string fold.
4. Does **not** flip `:wasm-aot :implemented` (host I/O + record-in-variant +
   depth budget for 4+ field maps still open).

## Evidence

- Package sha `540e939d…`; browser-host main → -2403
- ops kit registry + sha tests

## Related

- T8.3 residual W4; ADR 0246–0247; compiler `parametric-adt-depth 8`
