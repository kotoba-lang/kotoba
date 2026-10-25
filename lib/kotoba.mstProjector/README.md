# mst-projector

`kotoba.lang.mst-projector` — the LanceDB-indexer + XRPC query-server half of
`etzhayyim/root:50-infra/mst-projector/py`'s Python `mst_projector` package,
ported directly to Clojure (no intermediate physical-move-as-Python stage).

| Original (Python) | Ported to |
|---|---|
| `indexer.py` (LanceDB write/query path) | `kotoba.lang.mst-projector.indexer` (pure core + injected storage protocol) |
| `query_api.py` (aiohttp XRPC server, 4 NSIDs + healthz) | `kotoba.lang.mst-projector.query-api` |
| `subscriber.py` (AT-Proto firehose / CBOR-frame websocket subscriber) | **NOT ported** — see below |
| `main.py` (CLI entrypoint) | `kotoba.lang.mst-projector.cli` |

## Why `subscriber.py` stays Python

`20-actors/etzhayyim-sdk-py/MIGRATION-TODO.md` (a prior, independent py→cljc
migration of the `etzhayyim_sdk` package that `subscriber.py` depends on)
already recorded explicit founder guidance on this exact file: porting the
AT Protocol firehose / CBOR-frame websocket subscriber to babashka/Clojure is
"impractical," and it's deliberately left in place to coexist with the
now-mostly-Clojure `etzhayyim_sdk` package. This repo respects that decision
rather than re-litigating it — only `indexer.py`/`query_api.py`/`main.py`
(the parts *not* covered by that guidance) are ported here.

## Storage protocol: `IIndex`

`indexer.py` was hard-wired to LanceDB. LanceDB has no real JVM/Clojure
story, and this ecosystem is deliberately wary of bolting a specific
centralized DB dependency onto a `kotoba-lang` library, so this port does
NOT bring LanceDB along. Instead `kotoba.lang.mst-projector.indexer` defines
its own storage protocol, `IIndex`, and the pure indexer logic (record
flattening, row assembly, the public `index-op!`/`delete-op!`/`count-rows`/
`list-collections`/`query` orchestration functions) drives that protocol
only — mirroring `kotoba-lang/ipfs`'s injected `IHttp` seam (same
`-verb!`/`-verb` naming convention, same "core builds everything, the host
only moves/stores bytes" split):

```clojure
(defprotocol IIndex
  (-upsert!          [this collection row])            ; true upsert by (did,rkey); creates collection lazily
  (-delete!          [this collection did rkey])        ; no-op, does NOT create collection, if absent
  (-query            [this collection filter-map limit]) ; filter-map: nil | {:field String :value String}
  (-count-rows       [this collection])
  (-list-collections [this])
  (-describe         [this]))                           ; short diagnostic string, e.g. for /healthz
```

Design notes:

- **`filter-map` replaces raw SQL.** `query_api.py` built a literal SQL
  where-clause string (`f"{field_name} = '{safe_value}'"`) and handed it to
  LanceDB. Every filter it ever constructs is a single equality predicate,
  so `IIndex` instead takes plain data — `{:field "did" :value did}` or
  `{:field field-name :value field-value}` — which is trivially
  SQL-compilable for a hypothetical SQL-backed `IIndex`, but commits no
  implementor to SQL at all.
- **Upsert semantics moved into the backend.** The python original spelled
  out `index_op`'s mechanics explicitly: delete-then-add to maintain
  (did, rkey) uniqueness. Here `-upsert!` IS the upsert (create-or-replace)
  — the pure core just calls it once; the delete-then-add (or
  `INSERT ... ON CONFLICT REPLACE`, or whatever a given engine prefers) is
  the backend's own business. The observable result is identical: an update
  replaces the prior row and moves it to the end of iteration order.
- **No LanceDB table-name translation.** LanceDB rejects `.` in table
  names, so `indexer.py` mapped NSIDs like `app.bsky.feed.post` to table
  names via `.replace(".", "_")`, and `list_collections` did a lossy
  reverse mapping back. `IIndex` does not commit to any naming restriction,
  so this port drops the translation entirely — collections are keyed by
  the exact NSID string throughout, making `list-collections` *exactly*
  correct (an improvement over the original's lossy diagnostic-only
  reverse mapping).
- **A latent bug fixed, not ported faithfully.** `query_api.py`'s
  `_healthz` read `indexer.data_dir`, an attribute the `Indexer` class
  never actually set — every real call would have raised `AttributeError`
  and always hit the `except` → 503 branch. `-describe` replaces it with an
  intentional short diagnostic string (see below), fixing the bug while
  keeping the wire key name (`"data_dir"`) unchanged for response-shape
  compatibility.

### Reference implementation: `mem-index`

`kotoba.lang.mst-projector.mem-index` ships one concrete, usable `IIndex`:
an in-memory atom (`{collection -> [row ...]}`, insertion-ordered) with
OPTIONAL EDN-file persistence for durability across restarts
(`(make-mem-index {:persist-path "/path/to/file.edn"})` reloads prior state
at construction and re-`pr-str`s the *entire* atom to that file after every
mutating call). This is a simple, zero-extra-dependency reference/small-
scale option (full-rewrite-per-write, O(total data size) each time) — not a
production write path, but adequate for this projector's own test/dev-scale
workload and consistent with the "minimal deps, pure/portable" spirit this
session's sibling `kotoba-lang` ports established. A production deployment
wanting real database throughput/durability guarantees would supply a
heavier `IIndex` implementation; the protocol itself does not change.

## Server: `query-api` + `cli`

`kotoba.lang.mst-projector.query-api` implements the 4 XRPC handlers
+ `/healthz` on top of `com.sun.net.httpserver.HttpServer` — the JDK's
built-in HTTP server, zero extra dependency, the same class this session
used successfully as a test-mock server in `kotoba-lang/checkpointer`'s
`http_jdk_test.clj`; here it is the REAL server, not a mock, matching the
minimal-deps convention over pulling in Jetty/http-kit/etc. Every handler
talks only to an injected `IIndex` — `query-api` has zero storage-backend
knowledge. Error responses return REAL 4xx/5xx HTTP status codes (never a
200 with an error payload), since the existing `etzhayyim_sdk.mst-projector`
client classifies by status code first.

`(query-api/start! index opts)` returns a running `HttpServer`
(`opts` :host/:port, default `127.0.0.1:8765` per ADR-2605215500;
`:port 0` binds an OS-assigned ephemeral port, used by this repo's own
tests — `query-api/port` reads back the actual bound port). `(query-api/stop!
server)` stops it.

`kotoba.lang.mst-projector.cli` is the entrypoint (`kbb -M:run`), ported
from `main.py`'s **`--serve` path only**: it builds a `mem-index` (from
`--data-dir`/`ETZHAYYIM_MST_PROJECTOR_DATA_DIR` if given, else pure
in-memory) and starts `query-api` on `--host`/`--port` (env
`ETZHAYYIM_MST_PROJECTOR_HOST`/`_PORT`, defaulting to `127.0.0.1:8765`),
installs a JVM shutdown hook to stop the server cleanly, then blocks the
main thread forever (mirroring python's `asyncio.Event().wait()`). Passing
`--subscribe` exits(2) with a clear message pointing at the still-python
subscriber, rather than silently ignoring it or shipping a stub.

## Wire compatibility

A Clojure XRPC **client** for this exact query API already exists and is
tested: `etzhayyim_sdk.mst-projector` (in `20-actors/etzhayyim-sdk-py/src/
etzhayyim_sdk/mst_projector.cljc`, 17 tests / 47 assertions green) — same 4
NSIDs (`com.etzhayyim.mstProjector.{queryByCollection,queryByDid,
queryByField,countByCollection}`), same camelCase wire keys. This repo's
`query-api` server is built to be a wire-compatible server for that exact
client.

**How this was verified.** `mst_projector.cljc` lives inside
`etzhayyim/root`, a private monorepo, as a `bb.edn`/babashka project (not a
standalone `deps.edn` package with an independently SHA-pinnable git
coordinate) — so requiring it directly as a test dependency from this
public repo was impractical and undesirable (a public `kotoba-lang` repo
depending on a private one). Instead,
`test/kotoba/lang/mst_projector/query_api_test.cljk` includes a
`reference-client`: a small, deliberately side-by-side-readable
reimplementation of that file's `call*` and its 4 public functions —
identical NSIDs, identical request-map shapes/keys, identical status-code
classification (`>=500` server error / `>=400` client error with parsed
JSON body / else parse the 2xx body) — swapping only the transport
(`java.net.http.HttpClient`, JDK-native, in place of babashka's
`babashka.http-client`) and the error signal (plain `ex-info` in place of
this ecosystem's `etzhayyim-sdk.errors`). The test suite starts a real
`query-api` server on a loopback ephemeral port and drives it through
`reference-client` for every success and error path (including a 5xx path,
exercised with a deliberately-throwing `IIndex`), plus raw HTTP assertions
for status codes / malformed input / wrong HTTP method / unknown routes
that a status-code-classifying client like the real one depends on.

## Provenance

Ported 2026-07-02 from `etzhayyim/root:50-infra/mst-projector/py/src/
mst_projector/{indexer,query_api,main}.py` per the org-taxonomy
library-placement rule. Design authority remains ADR-2605215500, in
`etzhayyim/root`.

## Development

```bash
clj-kondo --lint src test
kbb -M:test
kbb -M:run --host 127.0.0.1 --port 8765           # start the query server
kbb -M:run --data-dir ~/.mst-projector/index.edn   # ...with EDN persistence
```

## License

Apache 2.0 + Charter Compliance Rider v3.6 (`/CHARTER-RIDER.md`).
