# mcp-clj (MCPプロトコル)

[![CI](https://github.com/kotoba-lang/mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/kotoba-lang/mcp/actions/workflows/ci.yml)

Handle **Model Context Protocol (MCP) server manifests as EDN/Clojure data** in
portable Clojure — every namespace is `.cljc`, with **zero third-party runtime deps**,
so it runs on the JVM, ClojureScript, and Clojure-on-WASM hosts (SCI). An MCP manifest
is plain data you can `assoc`, `diff`, store in Datomic, or generate; the library adds
validation, a JSON ↔ EDN bridge, and a pure JSON-RPC dispatcher around it.

Sibling of the other reusable `*-clj` kernels in this org
([langchain-clj](https://github.com/com-junkawasaki/langchain-clj),
[langgraph-clj](https://github.com/com-junkawasaki/langgraph-clj),
[bpmn-clj](https://github.com/com-junkawasaki/bpmn-clj)).
Used together with langchain-clj / langgraph-clj and a Claude+MCP stack it provides the
server-side manifest and dispatch kernel that agent orchestrators call into.

## Why a shared library (org placement)

Per the three-org rule, the **reusable** MCP kernel lives in **com-junkawasaki**;
**public-benefit actor instances** that define concrete tool sets live in **etzhayyim**;
any **business/private deployment** lives in **gftdcojp**. mcp-clj is the dep — it
carries no domain tool implementations and no transport bindings (those are
host-injected ports).

## The model: MCP manifest as EDN (`mcp.model`)

Tools, resources, and prompts are name/uri-keyed maps; ordering is deterministic
(sorted by name/uri):

```clojure
{:mcp/server    {:mcp/name "weather" :mcp/version "1.0.0"}
 :mcp/tools     {"get_forecast" {:mcp/name "get_forecast"
                                 :mcp/description "Get a weather forecast"
                                 :mcp/input-schema {:type "object"
                                                    :properties {"city" {:type "string"}}
                                                    :required ["city"]}}}
 :mcp/resources {"file:///readme" {:mcp/uri "file:///readme"
                                   :mcp/name "readme"
                                   :mcp/mime "text/markdown"}}
 :mcp/prompts   {"greet" {:mcp/name "greet"
                           :mcp/arguments [{:mcp/name "who" :mcp/required true}]}}}
```

A threading-friendly builder:

```clojure
(require '[mcp.model :as m])

(def weather-server
  (-> (m/server "weather" "1.0.0")
      (m/add-tool "get_forecast"
                  {:description  "Get a weather forecast for a city"
                   :input-schema {:type "object"
                                  :properties {"city" {:type "string"}}
                                  :required   ["city"]}})
      (m/add-resource "file:///readme" {:name "readme" :mime "text/markdown"})
      (m/add-prompt "greet" {:arguments [{:mcp/name "who" :mcp/required true}]})))

(m/tool weather-server "get_forecast")
;=> {:mcp/name "get_forecast" :mcp/description "..." :mcp/input-schema {…}}
```

## Validation (`mcp.validate`)

`problems` returns a vector of `{:mcp/severity :mcp/code :mcp/id :mcp/msg}`;
`valid?` is true iff there are no `:error`s (warnings are advisory):

```clojure
(require '[mcp.validate :as v])
(v/valid? weather-server)     ;=> true
(v/problems broken-manifest)
;=> [{:mcp/severity :error :mcp/code :schema/missing-required …}]
```

Errors: input-schema missing `:type`; `:properties` not a map; `:required` names a
property not in `:properties`; key/name mismatch; resource missing `:mcp/uri`.
Warnings: server manifest has no tools.

## JSON I/O (`mcp.json`)

MCP is JSON-RPC, so the host parses JSON text (e.g. `clojure.data.json` on JVM,
`js/JSON.parse` in CLJS). mcp-clj never parses JSON text itself — it only converts
between *already-parsed* Clojure maps/vectors (string keys) and the EDN model, exactly
like `bpmn.xml/from-elements` accepts neutral elements instead of XML strings:

```clojure
(require '[mcp.json :as j])

;; host parses JSON, hands us the map:
(def data {"server"    {"name" "weather" "version" "1.0.0"}
           "tools"     [{"name" "get_forecast"
                         "inputSchema" {"type" "object"
                                        "properties" {"city" {"type" "string"}}
                                        "required" ["city"]}}]
           "resources" []
           "prompts"   []})

(j/from-data data)    ; → EDN model (namespaced :mcp/* keys)
(j/to-data manifest)  ; → JSON-ready map (string keys), round-trips
```

## Execution (`mcp.execute` + `mcp.ports`)

A **pure JSON-RPC dispatcher**. State is plain data — inspectable, testable offline
with fixture ports. The host injects two ports (`mcp.ports`):

```
ITool      invoke  [tool-name args] → result    — call the real tool function
ITransport call    [method params]  → result    — outbound JSON-RPC client (optional)
```

Supported methods: `initialize`, `tools/list`, `tools/call` (validates `:required`
params → -32602 on missing; otherwise calls `ITool/invoke`), `resources/list`,
`prompts/list`. Unknown method → -32601. `default-ports` make any manifest dispatchable
with no host (echo tool; no-op transport):

```clojure
(require '[mcp.execute :as e])

(e/handle (e/default-ports) weather-server
          {"jsonrpc" "2.0" "method" "tools/list" "params" {} "id" 1})
;=> {"jsonrpc" "2.0" "id" 1
;    "result"  {"tools" [{"name" "get_forecast" "description" "…" "inputSchema" {…}}]}}

(e/handle (e/default-ports) weather-server
          {"jsonrpc" "2.0" "method" "tools/call"
           "params"  {"name" "get_forecast" "arguments" {}}   ; city missing
           "id" 2})
;=> {"jsonrpc" "2.0" "id" 2
;    "error"   {"code" -32602 "message" "missing required param: \"city\""}}
```

For real work, inject a ports map whose `:tool` calls your actual handler functions and
whose `:transport` forwards requests to an upstream MCP host.

## Test

```
kbb -M:test
```
