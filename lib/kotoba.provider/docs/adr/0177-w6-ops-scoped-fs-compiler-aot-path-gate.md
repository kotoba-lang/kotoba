# ADR 0177: T8.3 compiler-AOT scoped-fs path state-machine gates

- Status: Accepted
- Date: 2026-07-31
- Depends: ADR 0169 hand path-scan; ADR 0174 path-len; ADR 0176 secret char-class pattern

## Context

ADR 0174 landed pure path-length. Secret char-class (ADR 0176) showed a
host-walk pure gate pattern without `kotoba:typed`. Scoped-fs still needed
**dot/slash state-machine** AOT (`..`, `.`, absolute `/`, home `~`, NUL,
backslash).

## Decision

Pure exports (host walks path bytes):

| export | role |
|---|---|
| `fs_path_first_ok(c)` | `/` → -5, `~` → -6, else 0 |
| `fs_path_step(state,c)` | packed state `prev*4+dots`; errors -3/-4/-7 |
| `fs_path_finish(state)` | trailing `.` / `..` segment → -7 |

Initial walk state after first-char check: **4** (prev_slash=1, dots=0),
matching hand WAT. Length half remains `fs_path_len_ok` (ADR 0174).

| artifact | role |
|---|---|
| `src/fs_path_gate.kotoba` | source |
| `fs-path-gate-v1.wasm` | kotoba-compiler wasm32 |
| `fs-path-gate-v1.component.wasm` | Component embed |

Registry `:fs-path-gate{,-component}`, `:builder :kotoba-compiler/v1`.

### Honesty

- Does **not** delete hand WAT one-shot `fs_path_ok(ptr,len)`
- `:wasm-aot` stays `:partial`
- Composition is host-side walk, not a single pure memory-load export

## Non-claims

- Not typed-string single-call packaging
- Not OS store success
- Not full request/result EDN codec AOT

## Evidence

- digest match; Node live walks: ok paths → 0; abs/home/nul/\\/./../ → codes
- provenance `:builder :kotoba-compiler/v1`

## Related

- T8.3; ADR 0169, 0174–0176
