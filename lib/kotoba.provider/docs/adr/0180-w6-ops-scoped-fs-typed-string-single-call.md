# ADR 0180: T8.3 typed-string single-call fs_path_ok (kotoba:typed host)

- Status: Accepted
- Date: 2026-07-31
- Depends: ADR 0174/0177 pure path-len + path gates; ADR 0178 secret typed-string pattern

## Context

Scoped-fs pure path gates (0177) require a host walk. Secret typed-string
single-call (0178) showed how to package a compiler-AOT module that imports
`kotoba:typed` for one-call string policy. Scoped-fs still lacked the same
surface for full path validation (abs, home, NUL, backslash, `.` / `..`).

## Decision

### Ship typed-host-coupled compiler-AOT module

| piece | role |
|---|---|
| `src/fs_path_ok.kotoba` | single-call path policy + `main` live vector |
| `fs-path-ok-v1.wasm` | kotoba-compiler wasm32 + provenance |

Exports:

- `fs_path_ok` — typed string → i64  
  `-1` empty, `-2` >1024, `-3` NUL, `-4` `\\`, `-5` abs `/`, `-6` home `~`,
  `-7` `.` / `..` segment, `0` ok
- `main` — live vector → `-15470`  
  (`ok=0`, `empty=-1`, `abs=-5`, `backslash=-4`, `dotdot=-7`, `ok2=0`)

Registry `:fs-path-ok` with `:typed-host :kotoba.typed`, no Component
(`wasm-tools component new` needs typed world).

### Honesty

- Not pure Component packaging
- `:wasm-aot` stays `:partial`
- Hand WAT + pure gates retained

## Non-claims

- Not production signed Component for typed host
- Not full request/result EDN codec AOT
- Not pure memory-scan one-shot without typed host

## Evidence

- browser-host `main` → `-15470n`
- digest match; exports `fs_path_ok` + `main`; imports `kotoba:typed`

## Related

- T8.3; ADR 0169, 0174, 0177–0178
