# lg-curpus2skill — clj-native LangGraph twin

Clojure/`bb` port of the Python LangGraph app in `../lg/` per **ADR-2606280030**
(langgraph-python → langgraph-clj). **Additive / coexisting**: the Python in
`../lg/` stays the deployed runtime (`langgraph.json` / `Dockerfile`); this twin
runs alongside until a human cuts over. Nothing in `../lg/` was changed.

## Layout

| File | Ports |
|---|---|
| `src/lg_curpus2skill/graphs/health.cljc` | `_make_health_graph()` — `START → ping → END` |
| `src/lg_curpus2skill/graphs/extract_evidence.cljc` | `_make_single_node_graph(task_curpus2skill_extract_evidence)` — `START → execute → END`, `{:result}`/`{:error ≤300}` node contract |
| `src/lg_curpus2skill/store.cljc` | RisingWave/psycopg persistence → **injectable store seam** (kotoba Datom-log target); pure corpus→skill `extract` + `extract-evidence` task |
| `src/lg_curpus2skill/server.cljc` | FastAPI/uvicorn → `org.httpkit.server`; `GET /ok /health`, `POST /runs`, `POST|GET /xrpc/{nsid}`; `GRAPHS` + NSID map verbatim |
| `src/lg_curpus2skill/audit.cljc` | `httpx`→`babashka.http-client` audit emit shim (honors `LG_AUDIT_DISABLED`) |
| `test/lg_curpus2skill/smoke_test.cljc` | `clojure.test` analogue of `tests/test_smoke.py` + offline extraction tests |
| `run_tests.clj` | repo-rule test runner (NOT `.sh`) |

## Run

```bash
kbb -M:test          # clojure.test suite (17 tests / 35 assertions green)
kbb -M:serve 2024    # XRPC/runs server on httpkit
```

## Faithfulness / deviations

- Same graph topology, node behavior, NSID surface, and `{output, elapsed_s}` /
  `{error, elapsed_s}` envelopes as `server.py`.
- **Substrate boundary**: the kotodama handler's RisingWave reads/writes become
  the injectable `*query-corpus*` / `*persist-skills*` edges (default = in-process
  seam, INERT unless `C2S_STORE_ENABLED=1`/`RW_URL` — the unconfigured Python
  path), so the corpus→skill transform is verifiable offline with stubs.
- LLM/inference edges (if later wired) target the Murakumo loopback per
  ADR-2605215000. No `RetryPolicy` analogue (not in langgraph-clj).
