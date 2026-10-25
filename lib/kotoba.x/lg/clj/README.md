# lg-x clj — langgraph-clj port (ADR-2606280030)

Clojure (babashka) port of the Python `lg_x` LangGraph server (`../lg_x/**`),
per ADR-2606280030 (langgraph-python → langgraph-clj). Same graph topology, same
node behavior, same NSID surface.

## Layout (port ↔ source)

| clj ns | ports | notes |
|---|---|---|
| `lgx.graphs.health` | `lg_x/graphs/health.py` | check-rw → summarize → emit-audit |
| `lgx.graphs.agent-chat` | `lg_x/graphs/agent_chat.py` | resolve-actor → llm-call → emit-audit |
| `lgx.graphs.compose-tweet` | `lg_x/graphs/compose_tweet.py` | compose → emit-audit |
| `lgx.audit` | `lg_x/audit.py` | httpx → babashka.http-client; json → cheshire; fire-and-forget = `future` |
| `lgx.llm` | (shared LLM client) | OpenAI-compat /chat/completions |
| `lgx.server` | `lg_x/server.py` | dispatch core: GRAPHS / NSID map / camel→snake / run / xrpc |
| `lgx.cron` | `lg_x/cron.py` | langgraph.json cron-spec loader + fire closure |

## Run

```bash
kbb -M:test            # or: kbb run_tests.cljk   (17 tests / 34 assertions, network-free)
```

`bb.edn` pins langgraph-clj to the same sha as the repo-root bb.edn. State is a
clj map (the Python TypedDict); each node returns a partial-update map merged into
state by langgraph-clj.

## Deviations from the Python (faithful where it matters)

- **LLM endpoint** — Python defaulted to a RunPod vLLM proxy. This port defaults
  to the **Murakumo loopback LiteLLM gateway** (`http://127.0.0.1:4000/v1`,
  ADR-2605215000); still overridable via `MURAKUMO_URL` / legacy `VLLM_URL`.
- **health RW probe** — the Python node opened a RisingWave/Postgres `SELECT 1`.
  RisingWave is the charter-PROHIBITED substrate (root AGENTS.md §State), so this
  port does NOT reintroduce a PG driver: with no `RW_URL` it returns `:rw-ok false`
  exactly as the Python no-RW branch. A kotoba-engine probe is the proper swap-in.
- **HTTP framing + checkpointer** — the FastAPI/uvicorn app shell
  (`/runs`, `/runs/stream`, `/threads/{tid}/state`) and the RisingWave-backed
  `AsyncPostgresSaver` (`lg_x/checkpointer.py`, prohibited substrate) are NOT
  ported. `lgx.server` provides the framework-independent dispatch CORE; the
  in-process APScheduler residency (`lgx.cron`) defers to a launchd LaunchAgent
  per the operational-code rule.

## Coexistence (CRITICAL — app is in active use)

This clj port is **additive**. Every `.py` under `../lg_x/**` is still the live
runtime: `langgraph.json` graph entrypoints, `server.py` imports, and the
`Dockerfile` (`uvicorn lg_x.server:app`) all reference them. NONE were removed.
Wiring the clj port into deploy (and retiring the .py) is a human-reviewed
follow-up — this PR is a DRAFT for that review.
