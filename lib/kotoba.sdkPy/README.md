# etzhayyim-sdk — SDK for the etzhayyim religious-corp substrate (cljc port in progress)

Client library for the etzhayyim AT Protocol + IPFS + Base L2 substrate. Used by religious-corp Pregel cells (shinka, joucho, yoro, maps_sentinel) running on the Murakumo distributed fleet.

Per ADR-2605172000 (kotoba substrate), ADR-2605214000 (no commercial K8s), ADR-2605215000 (no commercial GPU rental).

## Migration status (py → cljc, httpx → babashka.http-client)

Per the repo-wide clj/bb rule (root AGENTS.md §"Operational code = clj/bb over the kotoba
Datom log"), the HTTP-bearing modules have been **ported off `httpx` to `babashka.http-client`**
(no new dependency — bb-native). The python and cljc surfaces **coexist** during the migration:

| Module | cljc (`src/etzhayyim_sdk/*.cljc`, ns `etzhayyim-sdk.<m>`) | python (`*.py`) | HTTP |
|---|---|---|---|
| `errors` | ✅ `errors.cljc` (ex-info + keyword `isa?` hierarchy) | removed | — |
| `mst_projector` | ✅ `mst_projector.cljc` | removed (was httpx) | babashka.http-client |
| `mst` | ✅ `mst.cljc` (M3 stubs, parity) | removed (was httpx) | babashka.http-client (M3) |
| `llm` | ✅ `llm.cljc` (retry/backoff) | removed (was httpx) | babashka.http-client |
| `metrics` | ✅ `metrics.cljc` | **kept** (no httpx; `__init__`/subscriber need the package importable) | — |

The four httpx-bearing `.py` modules (`errors`, `mst_projector`, `mst`, `llm`) + `test_mst_projector.py`
were **removed** — nothing outside the package imported them. `metrics.py` + `__init__.py` are
**kept** so the `etzhayyim_sdk` package stays importable for the still-python `mst-projector`
subscriber (`50-infra/mst-projector/py/src/mst_projector/subscriber.py`), which depends on
`etzhayyim_sdk.cursor` (firehose/CBOR websocket) + `etzhayyim_sdk.pds` (PDS client) — deep
python-only AT-Proto deps **not** in this package and impractical to port to bb. See `MIGRATION-TODO.md`.

## Quick start (cljc — bb)

```clojure
(require '[etzhayyim-sdk.mst-projector :as mp])

;; Query indexed view (server-side filter via mst-projector)
(def result (mp/query-by-collection "com.etzhayyim.shinka.heartbeat" :limit 50))
(doseq [record (:records result)] (println record))

;; Count records in a collection
(:count (mp/count-by-collection "com.etzhayyim.shinka.heartbeat"))

;; Query by author DID (collection optional)
(mp/query-by-did "did:plc:abc123" :collection "com.etzhayyim.shinka.kyumeiSignal" :limit 100)

;; Query by field value (wire keys are camelCase fieldName/fieldValue)
(mp/query-by-field "com.etzhayyim.shinka.heartbeat" "nodeName" "levi")
```

Errors surface as `ex-info` with a `:type` keyword; classify with
`(etzhayyim-sdk.errors/sdk-error? e :etzhayyim-sdk.errors/mst-projector-server-error)`.

`metrics` deviates slightly from the python method style: `(metrics/inc! (metrics/counter "x"))`,
`(metrics/gauge-set! (metrics/gauge "g") 3.0)`, and `(metrics/with-timer "lat" …)` replace
`counter().inc()` / `gauge().set()` / `with timer():`. Same names/semantics + Prometheus output.

## Environment variables

| Var | Default | Purpose |
|---|---|---|
| `ETZHAYYIM_MST_PROJECTOR_URL` | **required** | mst-projector base URL |
| `ETZHAYYIM_LLM_URL` | **required** | LiteLLM proxy base URL |
| `ETZHAYYIM_LLM_KEY` | *(none — no header sent)* | bearer token, sent to `ETZHAYYIM_LLM_URL` |
| `ETZHAYYIM_LLM_MODEL` | `gemma-4-e4b-it` | model name |

The two endpoints are **required and have no default**. They previously fell back to
`http://levi.local:4000` and `http://simeon.local:8765` — `.local` is the mDNS/Bonjour
namespace (RFC 6762), so those names are claimable by any host on the same link, and `levi`
and `simeon` are private murakumo fleet nodes that exist only on the operator's own network.
Unconfigured, the LLM client would send `Authorization: Bearer $ETZHAYYIM_LLM_KEY` to
whoever answered. Both now raise a config error (`::errors/llm-config-error`,
`::errors/mst-projector-config-error`) before any request is made, rather than contacting a
host nobody chose. Values are trimmed and stripped of trailing slashes; one that names no
host — blank, whitespace, or only slashes — is treated as absent.

## Tests (cljc — bb, no shell)

```bash
kbb 20-actors/etzhayyim-sdk-py/run_tests.cljk   # 25 tests / 92 assertions; run from anywhere
# or, from the actor dir:
kbb -M:test
```

The HTTP tests inject a stub transport via `(binding [mst-projector/*request* stub] …)` — the
bb-native analogue of the python `httpx.MockTransport` injection — so no network access is needed.

The kept python `metrics` module still has `tests/test_metrics.py` (no httpx) for the coexisting
python surface; the forward path is the cljc suites above.

## Architecture

The SDK follows a kotoba substrate pattern per ADR-2605172000. All state lives on:
- **AT Protocol MST** — mutable record store via PDS (shinka / joucho / yoro records)
- **IPFS** — immutable content + pinning
- **Base L2** — anchor contracts + land registry

No centralized databases, no commercial Kubernetes, no commercial GPU rental.

## References

- ADR-2605172000 — kotoba substrate
- ADR-2605214000 — Murakumo no-VKE mesh
- ADR-2605215000 — Murakumo-fleet-only inference
- ADR-2605215500 — mst-projector server-side filter
