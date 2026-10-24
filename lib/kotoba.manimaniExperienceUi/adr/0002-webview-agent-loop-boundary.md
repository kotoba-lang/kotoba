# ADR 0002: WebView Agent Loop Boundary

- Status: Accepted
- Date: 2026-07-21

## Context

The experience design moved from SVG review artifacts into a live macOS
WebView. Home, Inbox, Walk, and Chat now run as ClojureScript compiled by
shadow-cljs, with component styles extracted by shadow-css. Walk must represent
real Codex activity rather than a decorative progress simulation.

The WebView cannot safely spawn terminal processes itself. Codex CLI also needs
an explicit workspace and permission mode, while GitHub Issue and pull-request
creation must remain separate, intentional tools.

## Decision

The native Kotoba Shell owns the AppKit window and WKWebView. The browser UI
talks over loopback to the existing CLJS terminal-agent host:

```text
Kotoba Shell / WKWebView
  → shadow-cljs Web UI
  → http://127.0.0.1:7780/api/manimani/loop/run
  → terminal-agent CLJS host
  → codex exec --sandbox workspace-write
```

Walk sends a repository, a loop identifier, a workspace path, and a stable
session alias. The host verifies that the resolved workspace stays below its
configured workspace root. Each request runs one bounded loop turn. BMC, Lean,
Design, and System Dynamics are data-selected instruction profiles rather than
separate runtimes.

The first native WebView launch may start one Design turn after a short delay.
A `sessionStorage` marker prevents shadow-cljs hot reload from launching the
same turn again. A user can subsequently start a turn explicitly from Walk.

The UI derives `running`, `complete`, and `failed` from the HTTP operation. It
must not infer completion from mascot motion or elapsed time. A completed agent
message is projected into Chat. Stopping a process without an assistant message
is represented as stopped/incomplete, never as success.

Issue and pull-request creation remain separate `/api/manimani/issue` and
`/api/manimani/pr` operations. A loop instruction explicitly forbids pushing or
creating GitHub resources on its own.

## Safety boundaries

- The agent host binds only to `127.0.0.1`.
- Requested workspaces must resolve beneath `MANIMANI_WORKSPACE_ROOT`.
- Read-only Chat and workspace-write Action/Loop modes remain distinct.
- One bounded turn is the unit of execution; continuous autonomous repetition
  requires a later, separately governed supervisor decision.
- Hot reload cannot duplicate the automatic launch within one WebView session.
- Mascot speed is feedback only and never represents authorization or verified
  progress.
- GitHub mutations remain explicit tools and require their own receipts.

## Runtime evidence

On 2026-07-21, Kotoba Shell launched the WebView and the terminal-agent host
created a Codex session for `kotoba-lang/manimani-experience-ui` with
`workspace-write` mode. The session entered `running`. It was explicitly
stopped during shutdown before Codex produced an assistant report, and the host
then reported `running: false`. This validates launch and cancellation wiring,
but is not evidence of a completed design turn.

## Consequences

- WebView presentation and agent execution can restart independently.
- A host outage becomes a visible failed state instead of a fake animation.
- Long turns currently use one request/response operation; streaming events and
  durable reconnect are deferred.
- A future multi-agent supervisor must add concurrency limits, cancellation,
  receipts, and recovery without weakening this boundary.
