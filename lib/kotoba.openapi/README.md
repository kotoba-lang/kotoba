# kotoba-lang/openapi

[![CI](https://github.com/kotoba-lang/openapi/actions/workflows/ci.yml/badge.svg)](https://github.com/kotoba-lang/openapi/actions/workflows/ci.yml)

Handle **OpenAPI 3 specifications as EDN/Clojure data** in portable Clojure — every
namespace is `.cljc`, with **zero third-party runtime deps**, so it runs on the JVM,
ClojureScript, and Clojure-on-WASM hosts (SCI). An API contract is plain data you can
`assoc`, `diff`, store in Datomic, or generate; the library adds the structural
validation, JSON conversion, and a pure request builder around it.

Sibling of the other reusable kotoba-lang contract kernels such as
[`kotoba-lang/bpmn`](https://github.com/kotoba-lang/bpmn) and
[`kotoba-lang/dmn`](https://github.com/kotoba-lang/dmn).

## Why a shared library

The reusable OpenAPI contract model lives in `kotoba-lang/openapi`. It carries
no domain endpoints and no HTTP engine bindings; those remain host-injected
ports.

## The model: OpenAPI 3 as EDN (`openapi.model`)

Operations are keyed by path + method; parameters and responses use namespaced
`:openapi/*` keys, so the data is self-documenting and diff-friendly:

```clojure
{:openapi/info    {:openapi/title "Pets" :openapi/version "1.0"}
 :openapi/paths   {"/pets/{id}" {:get {:openapi/operation-id "getPet"
                                        :openapi/parameters  [{:openapi/name     "id"
                                                               :openapi/in       :path
                                                               :openapi/required true
                                                               :openapi/schema   {"type" "string"}}]
                                        :openapi/responses   {"200" {:openapi/description "ok"}}}}}
 :openapi/components {}}
```

Graph queries:

```clojure
(require '[openapi.model :as m])

(m/operations model)                    ;=> seq of {:path :method :op}
(m/operation-by-id model "getPet")     ;=> {:path "/pets/{id}" :method :get :op {…}}
(m/parameters-for op)                  ;=> [{:openapi/name "id" :openapi/in :path …}]
(m/path-params "/pets/{id}/photos/{photoId}") ;=> ["id" "photoId"]
```

## JSON conversion (`openapi.json`)

```clojure
(require '[openapi.json :as j])

;; parsed JSON map (string keys) → EDN model
(j/from-data {"info" {"title" "Pets" "version" "1.0"} "paths" {…}})

;; EDN model → string-keyed map (round-trippable)
(j/to-data model)
```

## Validation (`openapi.validate`)

`problems` returns a vector of `{:openapi/severity :error|:warn :openapi/code :openapi/id :openapi/msg}`;
`valid?` is true iff there are no `:error`s (warnings are advisory):

```clojure
(require '[openapi.validate :as v])
(v/valid? model)            ;=> true
(v/problems broken)         ;=> [{:openapi/severity :error :openapi/code :op/duplicate-id …}]
```

Errors: duplicate operationId, undeclared path parameter, operation with no responses,
unresolved local `$ref`. Warnings: external `$ref` (cannot be resolved locally).

## Execution (`openapi.execute` + `openapi.ports`)

A **pure request builder**. State is plain data — inspectable, testable offline. The
host injects `IHttp` (`openapi.ports`):

```clojure
(require '[openapi.execute :as e])
(require '[openapi.ports   :as p])

;; Build a request map without performing I/O:
(e/request-for model "getPet" {"id" "42"})
;=> {:method :get :url "/pets/42"}

;; Invoke via an injected IHttp (default-ports echoes the request):
(e/invoke p/default-ports model "getPet" {"id" "42"})
;=> {:status 0 :echo {:method :get :url "/pets/42"}}
```

For real work, inject an IHttp that calls an HTTP client (clj-http, hato, js/fetch);
the request builder stays pure.

## Test

```
kbb -M:test
```
