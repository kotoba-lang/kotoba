# ADR 0181: T8.3 pure multi-step scoped-fs path walk

- Status: Accepted
- Date: 2026-07-31
- Depends: ADR 0174 path-len; ADR 0177 path gates; ADR 0179 secret walk pattern; ADR 0180 typed-string

## Context

Secret gained a pure multi-step host-walk protocol (ADR 0179). Scoped-fs had
pure gates (0177) and typed-string single-call (0180) but no composed
begin/next/end walk for hosts that prefer pure i64 without `kotoba:typed`.

## Decision

### Protocol

| export | meaning |
|---|---|
| `fs_path_begin(len)` | `100` need-first \| `-1` empty \| `-2` oversize |
| `fs_path_next(state, c)` | sticky error \| next state; PRE(100) applies first-char `/`/`~` then step from 4 |
| `fs_path_end(state)` | `0` ok \| `-7` trailing `.`/`..` \| sticky error |

State `0..7` encodes `prev_slash*4+dots` (ADR 0177). Error codes match hand WAT.

| artifact | role |
|---|---|
| `src/fs_path_walk.kotoba` | source |
| `fs-path-walk-v1.wasm` | kotoba-compiler wasm32 + provenance |
| `fs-path-walk-v1.component.wasm` | Component embed |

### Honesty

- Host still walks bytes (not pure memory-scan one-shot)
- Hand WAT + typed-string 0180 retained
- `:wasm-aot` stays `:partial`

## Non-claims

- Not production typed Component world
- Not full request/result EDN codec AOT
- Not OS store success proof

## Evidence

- Node live walks: empty -1; ok 0; abs -5; home -6; `\\` -4; `..` -7
- digest match; Component present

## Related

- Reliability WBS T8.3
- ADR 0174, 0177, 0179, 0180
