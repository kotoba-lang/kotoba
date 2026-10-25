# ADR 0207: T8.3 pure Component re-emit of fs_path_ok + header-name misfit fix

- Status: Accepted
- Date: 2026-07-31
- Depends: ADR 0180 typed-string fs_path_ok; kotoba-component#101
  (`:fs-path-ok-with-main`)

## Context

ADR 0180 shipped a typed-host wasm module for scoped-fs path policy. Before
kotoba-component#101, full `fs_path_ok.kotoba` could compile `--target
component` by **misfitting** `:http-header-name-ok-with-main` (tchar allowlist),
producing wrong error codes (`main` → nonsense vs expected `-15470`).

## Decision

| source | module (typed) | Component (pure) | live `main()` |
|---|---|---|---|
| `fs_path_ok.kotoba` | `:fs-path-ok` | `:fs-path-ok-component` | **-15470** |

Policy (Canonical WAT path state machine):

| code | meaning |
|---|---|
| `-1` | empty |
| `-2` | length >1024 |
| `-3` | NUL |
| `-4` | backslash |
| `-5` | absolute leading `/` |
| `-6` | home leading `~` |
| `-7` | `.` or `..` segment |
| `0` | ok |

Also: header-name-ok now requires export name containing `header` (stops
path/secret misfits at the shape layer).

### Honesty

- Does **not** flip scoped-fs `:wasm-aot :implemented` (codec AOT open)
- Does **not** replace host store / path open
- Hand WAT + pure gates retained

## Evidence

- digest match; wasmtime `main()` → `-15470`
- `a/b`→0, `/abs`→−5, `a/../b`→−7, `a\\b`→−4
- ops-kit component twin registration

## Related

- T8.3; ADR 0169, 0177–0180; kotoba-component#101
