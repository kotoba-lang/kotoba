# ADR 0195: T8.3 pure memory-scan HTTP header name/value/pair

- Status: Accepted
- Date: 2026-07-31
- Depends: ADR 0187–0188 typed header policies; ADR 0194 request/result scan

## Context

ADR 0194 landed pure memory-scan for request URL + result/error surfaces.
Header **name tchar** and **value CTL** policies still existed only as
typed-string packages (0187–0188) that cannot enter a Component world without
a `kotoba:typed` WIT binding (compiler ADR 0076 4a). Pure ptr/len parity for
headers closes the hand-WAT path used by secret/scoped-fs.

## Decision

Hand WAT core (+ Component embed):

| export | codes |
|---|---|
| `http_header_name_scan(ptr,len)` | `-1` empty; `-2` >128; `-3` non-tchar; `0` ok |
| `http_header_value_scan(ptr,len)` | `-2` >8192; `-3` NUL/CR/LF; `0` ok (empty ok) |
| `http_header_pair_scan(nptr,nlen,vptr,vlen)` | name `-1/-2/-3`; value `-2→-5`, `-3→-6` |

tchar matches RFC 7230 token / ADR 0187.

| artifact | role |
|---|---|
| `src/http_header_memory_scan.wat` | hand source |
| `http-header-memory-scan-v1.wasm` | core |
| `http-header-memory-scan-v1.component.wasm` | Component embed |

Registry `:http-header-memory-scan` + component; builder `:hand-wat/v1`.

### Honesty

- Does **not** unlock typed Component packaging (still blocked on compiler
  linear-memory / WIT world for `kotoba:typed`)
- Does **not** flip `:wasm-aot` to `:implemented`
- Does not check header set uniqueness / JDK restricted names

## Non-claims

- Not typed-string retirement
- Not live network; not full EDN codec

## Evidence

- Node live vector for name/value/pair error codes
- digest match module + Component

## Related

- T8.3; ADR 0187–0188, 0194; residual pure header scan / typed Component world
