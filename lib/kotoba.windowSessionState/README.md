# kotoba-lang/window-session-state

Zero-dep portable `.cljc` — restored from the legacy `kami-engine/kami-os` Rust crate
(deleted in kotoba-lang/kami-engine PR #82 "Remove Rust workspace from kami-engine") as
part of the **clj-wgsl migration** (ADR-2607010930, `com-junkawasaki/root`).

**Renamed from `kotoba-lang/os` to `window-session-state`** (2026-07-02, owner request) —
"os" collided in spirit with the already-registered `kotoba-lang/shell` (kotoba-shell, a
Tauri replacement) and `kotoba-lang/aiueos` (a capability-secure Wasm component OS); this
repo is neither an OS nor a shell, it's desktop app-shell *session state*.

## What this is

`kami-os` was a wgpu-based desktop environment: window management, taskbar, app
launcher, notification/consent system, file explorer, and an embedded XRPC terminal,
composited over an `hecs` ECS world. This repo ports every module's **portable
app-shell state machine** (window/taskbar/launcher/notification/file-explorer/terminal
state + focus routing) to pure CLJC data + pure functions, so the same logic runs on
JVM Clojure, ClojureScript, and (via `.cljc` reader conditionals where needed) WASM
targets.

## Modules restored

| Namespace | From | Purpose |
|---|---|---|
| `src/window-session-state.cljc` | `lib.rs` (109 lines) | Top-level `OsDesktop` orchestration: open/close/focus windows, notification helpers, fixed-30fps clock tick accumulator. |
| `src/window-session-state/window.cljc` | `window.rs` (95 lines) | Window lifecycle state (`:normal`/`:minimized`/`:maximized`), content-variant tags, rect + title-bar hit-testing. |
| `src/window-session-state/compositor.cljc` | `compositor.rs` (103 lines) | Z-stack ordering, focus tracking, title-bar drag state, usable desktop area. |
| `src/window-session-state/input_router.cljc` | `input_router.rs` (61 lines) | Focus-aware input target resolution (`[:panel id]` / `[:modal id]` / `[:global-overlay]` / `[:none]`), consent-modal stack, launcher overlay flag. |
| `src/window-session-state/taskbar.cljc` | `taskbar.rs` (77 lines) | Agent status list, budget display, pending-consent badge count, launcher-open toggle. |
| `src/window-session-state/launcher.cljc` | `launcher.rs` (93 lines) | App-grid visibility, case-insensitive search filter, keyboard selection navigation. |
| `src/window-session-state/notification.cljc` | `notification.rs` (93 lines) | Toast stack with expiry ticking + FIFO consent-request queue with resolve/response tracking. |
| `src/window-session-state/terminal.cljc` | `terminal.rs` (140 lines) | Command-history buffer, scrollback with trimming, history up/down navigation, submit/append-output. |
| `src/window-session-state/file_explorer.cljc` | `file_explorer.rs` (126 lines) | Directory-listing view state: navigate/navigate-up, multi-select, sort/view-mode fields. |

`hecs` ECS entity storage (windows/notifications/taskbar items as entities) has no
portable equivalent and is adapted to plain integer window IDs used as map keys on the
`window-session-state/window-session-state-desktop` map — the same entity-as-plain-ID pattern used in `kotoba-lang/scene-graph`
and `kotoba-lang/core`. `window-session-state.input-router` mirrors the `[:panel id]`/`[:modal id]`/
`[:global-overlay]`/`[:none]` focus-resolution pattern already established in the
sibling `kotoba-lang/input` restoration, reimplemented locally to keep this repo
zero-dependency.

## Out of scope (intentionally not ported)

- **wgpu compositor draw calls** (`compositor.rs`'s per-frame render: desktop background,
  window shadow/rect/title-bar/content rendering via `kami-ui-gpu`, SDF text via
  `kami-text`) — GPU rendering, native substrate only.
- **Native OS input capture** (`kami-bridge`) and **device mesh** (`kami-knp`), referenced
  in `lib.rs`'s architecture doc — native-substrate dependencies with no portable CLJC
  equivalent; callers on the native substrate are expected to translate raw input into
  the abstract events `window-session-state.input-router` consumes.
- **XRPC network calls** (`terminal.rs` routing submitted commands to
  `atproto.etzhayyim.com`, `file_explorer.rs`'s R2/IPFS `app.etzhayyim.window-session-state.sync.*`
  fetches) — network IO; this repo owns only the resulting view/buffer state.
- **`kami_ui_gpu::ToastStack`** — the original re-exported a generic GPU toast-rendering
  stack; `window-session-state.notification` reimplements just its portable expiry-timer semantics.
- **`kami_core::time::GameClock`** — a separate not-yet-restored crate; `window-session-state/advance`
  reimplements the original's fixed-30fps-timestep tick-counting semantics locally as a
  simple accumulator rather than pulling in unrelated timing code.

## Tests

The pre-deletion Rust source (verified at commit
`a8368f9c0d784dbc9d11e8fa8f407aa95c7ce4fa`) contained **zero `#[test]` functions** across
all 9 files, so there was nothing to port 1:1. `test/os_test.cljc` instead provides
original coverage of every ported function across all modules, plus the pre-existing
namespace-loads smoke test.

**26 tests, 98 assertions, 0 failures.**

## Develop

```bash
kbb -M:test
```
