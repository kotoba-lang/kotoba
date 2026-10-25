# ADR-0001: Architecture — genspark → browser-agent-clj

**Status**: accepted · **Date**: 2026-06-25

Workspace-level design: `90-docs/adr/2606250956-browser-agent-clj-genspark-style-super-agent.md`.
This repo-level ADR pins the genspark → component correspondence.

## Layering

browser-agent-clj adds one orchestration layer + an owned-browser layer
on top of the existing stack; it writes no new LLM/graph/store
primitives.

```
browser-agent-clj  →  browser-use-clj  →  langgraph-clj  →  langchain-clj
```

`agent-browser` はこの repo では外部 CLI 依存ではなく、上記 stack の
capability role として扱う。CLI が必要な環境では
`browser-agent-clj` + `browser-use-clj` + `playwright-clj` を包む薄い
adapter を置く。

## Correspondence

| genspark | browser-agent-clj | namespace |
| --- | --- | --- |
| AI Browser the agent **owns** (own profile/session, watchable, take-over) | managed provider + session datoms + live screencast + interrupt | `browser/{provider,session,live}` |
| Mixture-of-Agents (router + multiple LLMs + aggregator) | StateGraph: route → delegate → aggregate; `:models` per role | `supervisor` |
| Super Agent (autonomous multi-step) | plan-and-execute + replan, persisted | `planner` |
| agentic browsing | web sub-agent over the owned browser | `fleet/web-agent` (browser-use-clj) |
| research / code / authoring agents | ReAct sub-agents w/ injected host fns | `fleet/{research,coder,author}-agent` |
| 80+ tools | tool maps + (planned) MCP bridge | `fleet`, `*.mcp` (P5) |
| deliverables (slides/sheet/doc/page) | `render_artifact` → `:artifact/*` datoms | `fleet/author-agent` |
| factuality / cross-check | aggregator synthesis + `:mem/source-url` | `supervisor`, `memory` |
| **(beyond genspark)** audit + reproducibility | whole run is datoms + `as-of` time-travel | `schema`, `memory` |

## Invariants

1. **All `.cljc`, no third-party runtime deps** — runs on JVM / WASM /
   cljs. (Playwright lives behind the `:playwright` alias / examples; UI
   rendering is host-adapter owned.)
2. **I/O injected** — models, browser provider, store, and
   search/fetch/exec/render/emit are host capabilities passed in.
3. **State is datoms** — one `langchain.db`-compatible conn carries the
   task, owned browser session, plan (+ replan history), delegations,
   the browser-use action log, semantic memory and artifacts.

## Status / roadmap

- **Done (this commit)** — P0 supervisor MVP, P1 owned-browser layer
  (mock provider + session datoms + live frames), P2 planner + memory,
  P3 fleet (web/research/coder/author). End-to-end test + offline demo.
- **Next** — P1 Playwright provider, P4 host UI adapter, P5 MCP bridge +
  multi-model routing/cross-check, P6 etzhayyim deployment.
