# kotodama.projects.ameno

Python port (Path B) of the ameno agent daemon.

Same StateGraph as the browser appview and the TS daemon — reflection +
active inference (lexical) + ReAct tools — but built on the existing
`kotodama` LangGraph stack so it can deploy as a Murakumo Tier-1
`lg-ameno` pod next to the existing `lg-uhl-right-neural` shape.

ADR: [`90-docs/adr/2605191257-ameno-daemon-path-b-kotodama-python.md`](../../../../../../../90-docs/adr/2605191257-ameno-daemon-path-b-kotodama-python.md).

## Files

```
projects/ameno/
├── __init__.py            # public re-exports
├── __main__.py            # python -m kotodama.projects.ameno
├── pregel.py              # AmenoState (TypedDict) + StateGraph
├── ollama_stream.py       # async streaming Ollama /api/chat
├── tools.py               # ToolDef registry: now / wikipedia / recall
├── file_checkpointer.py   # MemorySaver subclass, JSON snapshot
├── server.py              # FastAPI + SSE endpoints
├── ameno-daemon.service   # systemd unit template (Linux)
└── README.md
```

## Requirements

- `kotodama` installed (this repo's `20-actors/kotoba-kotodama/py` package)
- Ollama running on localhost:11434
- Pull a model:

  ```sh
  ollama pull gemma3:4b
  ```

## Run (dev, interactive)

```sh
# from repo root
cd 20-actors/kotoba-kotodama/py
uv sync                  # or: pip install -e .
python -m kotodama.projects.ameno
```

You should see:

```
ameno-daemon (Path B / Python) listening on http://127.0.0.1:12481
  did:        did:web:host:<hostname>-<uuid>
  home:       /Users/you/.ameno
  model:      gemma3:4b
  endpoint:   http://127.0.0.1:11434/api/chat
```

## HTTP API

| method | path | body | returns |
|---|---|---|---|
| GET | `/healthz` | — | `{status, workerDid}` |
| GET | `/workerInfo` | — | `{did, uptimeMs, model, ollamaReachable, ...}` |
| POST | `/threads/:tid/invoke` | `{messages, maxIterations, activeInference, toolsEnabled}` | `{thread_id, draft}` |
| POST | `/threads/:tid/stream` | same | SSE `data: <GraphChunk JSON>\n\n` per super-step |
| GET | `/threads/:tid/state` | — | latest checkpointed state for thread |

ABI is **identical to Path A (TS daemon)** so the browser appview's viewer
mode (future PR) speaks both transparently.

## Always-on (systemd, Linux)

```sh
sudo cp ameno-daemon.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now ameno-daemon
journalctl -u ameno-daemon -f
```

Edit `User=`, `WorkingDirectory=`, and `ExecStart=` to match your host.

## Always-on (launchd, macOS)

Use the TS Path A's launchd plist with adjusted ExecStart. The Python
daemon and TS daemon can coexist on the same host (different ports;
TS = 12480, Python = 12481; different DIDs in `~/.ameno/worker-did`).

## Configuration (env)

| var | default | meaning |
|---|---|---|
| `AMENO_HOME` | `~/.ameno` | state directory (checkpointer + DID) |
| `AMENO_PORT` | `12481` | HTTP listen port |
| `AMENO_HOST` | `127.0.0.1` | listen address. **Do NOT expose to LAN** without threat modeling |
| `LOCAL_LLM_PROVIDER` | `ollama` | only `ollama` for now |
| `LOCAL_LLM_ENDPOINT` | `http://127.0.0.1:11434/api/chat` | Ollama endpoint |
| `LOCAL_LLM_MODEL` | `qwen3:14b` *(kotodama default)* | model name; recommend `gemma3:4b` for parity with browser |
| `LOCAL_LLM_TIMEOUT_SEC` | `120` | per-request timeout |

## Relationship to other ameno modules

- **Browser appview** (`60-apps/.../svelte`) — Tier 2 tab-resident worker. WebGPU MediaPipe Gemma.
- **TS daemon** (`60-apps/.../daemon`) — Path A. Bun/Node, headless, single-machine.
- **Python daemon** (this) — Path B. Tier 1 statck integration. Future K8s pod (`lg-ameno`).
- **`kotodama.ameno_handlers`** — receive-side XRPC saveResult / listHistory persistence (ADR-2605111200). Independent from this project.

All four can run concurrently against the same substrate (different DIDs).

## License

Apache-2.0.
