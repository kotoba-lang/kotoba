# etzhayyim-project-os — KAMI + Kotodama OS

etzhayyim OS はユーザーのデスクトップ上で動作する **Web4 ローカルインターフェース**。
KAMI Engine (wgpu compositor) + Kotodama host-sdk (TS Native) の 2 層で構成。

## Architecture

```
┌─────────────────────────────────────────────────┐
│              KAMI Compositor (kami-os)            │
│  wgpu full-canvas, kami-ui-gpu widgets, 30fps    │
│                                                   │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐         │
│  │ Window   │ │ Window   │ │ Window   │  ...    │
│  │ (IFrame) │ │ (Agent)  │ │ (Term)   │         │
│  └──────────┘ └──────────┘ └──────────┘         │
│  ┌─────────────────────────────────────────────┐ │
│  │ Taskbar: [Launcher] | Windows | Agents | $  │ │
│  └─────────────────────────────────────────────┘ │
└───────────┬─────────────────────────┬─────────────┘
            │ XRPC                    │ ECS
┌───────────▼───────────┐  ┌─────────▼────────────┐
│  Kotodama OS Service  │  │  kami-os Rust WASM    │
│  (src/app.ts)         │  │  (hecs ECS)           │
│  • agent-runtime      │  │  • CompositorState    │
│  • consent            │  │  • WindowComponent    │
│  • directory          │  │  • InputRouter        │
│  • budget             │  │  • TaskbarState       │
│  • audit              │  │  • NotificationQueue  │
│  • sync               │  │  • LauncherState      │
│  • window-manager     │  │  • TerminalState      │
│  • LLM (joucho)       │  │  • FileExplorerState  │
└───────────┬───────────┘  └──────────┬────────────┘
            │ HYPERDRIVE              │ kami-knp
  ┌─────────▼────────┐      ┌────────▼────────────┐
  │ RisingWave Graph│      │ Device Mesh          │
  │ (agent, consent, │      │ (peer input relay,   │
  │  budget, audit)  │      │  clipboard, screen)  │
  └──────────────────┘      └─────────────────────┘
```

## 2 Layer Design

| Layer | Technology | Responsibility |
|---|---|---|
| **Shell (rendering + input)** | kami-os (Rust WASM, `40-engine/kami-engine/kami-os/`) | Window compositor, GPU UI, input routing, taskbar, launcher, notifications, consent modal |
| **Services (OS logic)** | Kotodama host-sdk (TS Native, `src/app.ts`) | Agent lifecycle, consent governance, GCC budget, directory, audit, sync, window events |

## File Structure

```
60-apps/etzhayyim-project-os/
├── AGENTS.md                  # This file
├── kotodama.jsonld            # Kotodama app definition (did:web:os.etzhayyim.com)
├── PROJECT.jsonld             # Metadata
├── OWNERS
├── src/
│   └── app.ts                 # Kotodama OS service (TS Native, single file)
├── wit/
│   └── world.wit              # OS WIT contract (7 capability exports + automaton imports)
└── provider/
    └── automaton/
        └── wit/
            └── automaton.wit  # Autonomous agent interface (survival, policy, memory, soul, replication)
```

### KAMI OS Crate (Shell)

```
40-engine/kami-engine/kami-os/
├── Cargo.toml                 # Depends: kami-core, kami-render, kami-input, kami-ui-gpu, kami-text, kami-knp, kami-bridge
└── src/
    ├── lib.rs                 # OsDesktop: hecs World + GameClock(30fps) + all subsystems
    ├── compositor.rs          # Z-stack, focus, drag, desktop dimensions
    ├── window.rs              # WindowComponent + WindowRect + WindowContent (ECS components)
    ├── taskbar.rs             # AgentStatusEntry, budget display, consent badge
    ├── launcher.rs            # App grid overlay, search filter
    ├── notification.rs        # Delegates to kami-ui-gpu::ToastStack + OS ConsentRequest modal
    ├── input_router.rs        # Delegates to kami-input::FocusManager + OS semantics
    ├── terminal.rs            # XRPC shell (scrollback, history, command parsing)
    └── file_explorer.rs       # R2/IPFS file browser
```

## WIT Contract

`wit/world.wit` exports 7 OS capabilities:

| Export | NSID | Description |
|---|---|---|
| `agent-runtime` | `com.etzhayyim.apps.os.agent*` | Agent spawn/stop/pause/resume/migrate |
| `consent` | `com.etzhayyim.apps.os.consent*` | Human-in-the-loop approval queue |
| `directory` | `com.etzhayyim.apps.os.directory*` | Agent discovery by capability tags |
| `budget` | `com.etzhayyim.apps.os.budget*` | GCC token allocation and balance |
| `audit` | `com.etzhayyim.apps.os.audit*` | Agent behavior audit trail |
| `sync` | `com.etzhayyim.apps.os.sync*` | Local-cloud state synchronization |
| `window-manager` | `com.etzhayyim.apps.os.window*` | KAMI compositor window bridge |

Imports `etzhayyim:automaton@0.1.0` (survival, policy, memory, soul, replication) from `provider/automaton/`.

## SDK Dependencies (promoted from OS to SDK)

| Primitive | SDK Module | Used By OS |
|---|---|---|
| `FocusManager` | `kami-input` (Rust) | `input_router.rs` delegates focus routing |
| `ToastStack` | `kami-ui-gpu` (Rust) | `notification.rs` delegates toast rendering |
| `createConsentHelper` | `@etzhayyim/kotodama-host-sdk` (TS) | `src/app.ts` consent commands |
| `createAgentLifecycle` | `@etzhayyim/kotodama-host-sdk` (TS) | `src/app.ts` agent commands |
| `createAuditHelper` | `@etzhayyim/kotodama-host-sdk` (TS) | `src/app.ts` audit trail |

## Graph Labels (kagami)

```
(:OsAgent {agentId, did, appId, name, status, config})
(:OsAgentEvent {agentId, event, target})
(:OsConsentRequest {requestId, agentDid, action, riskTier, estimatedCost, status})
(:OsConsentResponse {requestId, verdict, reason})
(:OsBudgetAllocation {agentId, amount, expiresAt})
(:OsDirectoryEntry {did, name, tags})
(:OsAuditEntry {agentId, action, toolCall, verdict})
(:OsSyncEvent {direction, path, dataSize})
(:OsWindowEvent {windowId, event, appId, title, contentType, contentUrl})
```

All labels include RLS columns: `org_id`, `user_id`, `actor_id`, `created_at`.

## Protocol Exposure (4-protocol from single service)

| Protocol | Transport | Caller |
|---|---|---|
| XRPC | HTTP/2 | Peer apps, KAMI compositor, Svelte frontend |
| MCP | HTTP POST JSON-RPC | External AI agents (Claude, etc.) |
| cross-actor | HTTP POST cross-actor | Autonomous agent-to-agent |
| wRPC | W Protocol stream | Reactive subscribers |

## Nested References

- KAMI Engine: `40-engine/kami-engine/AGENTS.md`
- Kotodama SDK: `kotoba-lang/kotodama-host/AGENTS.md`
- WIT contracts: `_archive/00-contracts/wit/` (archived 2026-04-12)
- Automaton WIT: `provider/automaton/wit/automaton.wit`
- Projects rules: `60-apps/AGENTS.md`

## Build & Deploy

```bash
# KAMI OS crate (Rust WASM)
cd 40-engine/kami-engine
wasm-pack build --target web kami-os

# Kotodama OS service (TS Native)
cd 60-apps/etzhayyim-project-os
etzhayyim build
etzhayyim deploy --smoke-url https://os-etzhayyim-01.etzhayyim.com/health
```
