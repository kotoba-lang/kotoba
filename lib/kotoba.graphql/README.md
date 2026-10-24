# graphql-clj (GraphQL スキーマ実行)

[![CI](https://github.com/kotoba-lang/graphql/actions/workflows/ci.yml/badge.svg)](https://github.com/kotoba-lang/graphql/actions/workflows/ci.yml)

Handle **GraphQL SDL → EDN schema AST** and execute queries over **host-injected
resolvers** in portable Clojure — every namespace is `.cljc`, with **zero
third-party runtime deps**, so it runs on the JVM, ClojureScript, and
Clojure-on-WASM hosts (SCI). A GraphQL schema is plain data you can `assoc`,
`diff`, store in Datomic, or generate; the library adds SDL parsing, query
parsing, structural validation, and a pure field-resolution executor around it.

Sibling of the other reusable `*-clj` kernels in this org
([bpmn-clj](https://github.com/com-junkawasaki/bpmn-clj),
[koe-clj](https://github.com/com-junkawasaki/koe-clj),
[langgraph-clj](https://github.com/com-junkawasaki/langgraph-clj)).

## Why a shared library (org placement)

Per the three-org rule, the **reusable** schema model and query executor live in
**com-junkawasaki**; **public-benefit actor instances** that drive concrete
GraphQL APIs live in **etzhayyim**; any **business/private deployment** lives in
**gftdcojp**. graphql-clj is the dep — it carries no domain schema and no
runtime bindings (those are host-injected ports).

## The schema model: GraphQL as EDN (`graphql.model`)

Types are name-keyed maps; fields carry their modifiers inline:

```clojure
{:graphql/types
 {"Query" {:graphql/name "Query" :graphql/kind :object
           :graphql/fields [{:graphql/name "user"
                             :graphql/type "User"
                             :graphql/list? false
                             :graphql/non-null? false
                             :graphql/args [{:graphql/name "id"
                                            :graphql/type "ID"
                                            :graphql/non-null? true}]}]}
  "User"  {:graphql/name "User" :graphql/kind :object
            :graphql/fields [{:graphql/name "name" :graphql/type "String"
                              :graphql/list? false :graphql/non-null? false}]}}
 :graphql/query-root "Query"}
```

Kinds: `:object` `:input` `:enum` `:interface` `:union` `:scalar`.
Builder functions (`type-def`, `field-def`, `arg-def`, `add-type`,
`set-query-root`) and queries (`get-type`, `field-by-name`, `all-types`,
`query-root`) compose a threadable API.

## SDL parsing (`graphql.sdl`)

`parse-schema` converts a GraphQL SDL string into a `graphql.model` schema map
using a hand-rolled tokenizer and recursive-descent parser:

```clojure
(require '[graphql.sdl :as sdl])

(def schema
  (sdl/parse-schema
    "type Query { user(id: ID!): User }
     type User  { id: ID! name: String }
     scalar Date"))

(get-in schema [:graphql/types "User" :graphql/kind])  ;=> :object
```

Supported SDL subset: `type`, `input`, `interface`, `enum`, `union`, `scalar`,
`schema { query: … }`, `!` non-null, `[T]` list, `#` comments, `@directive`
(ignored). If no `schema` block is present and a type named `"Query"` exists,
it is automatically used as the query root (per the GraphQL spec default).

Not supported: nested list types (outermost modifiers only retained), `extend
type`, fragment definitions, default-value type-checking.

## Query parsing (`graphql.query`)

`parse-query` converts a GraphQL query string into a selection AST — a vector
of selection maps — using the same tokenize-and-descend approach:

```clojure
(require '[graphql.query :as q])

(q/parse-query "{ user(id: \"1\") { name } }")
;=> [{:graphql/field "user"
;     :graphql/args {"id" "1"}
;     :graphql/selections [{:graphql/field "name" :graphql/args {} :graphql/selections []}]}]
```

Supported: anonymous `{ … }` shorthand, named `query Name { … }` and
`mutation` operations, field aliases (resolved to the real field name), nested
selection sets, argument literals (string, integer, float, boolean, enum).
Not supported: variable binding (`$var`), input-object literals, directives on
fields, fragment spreads (silently skipped).

## Validation (`graphql.validate`)

`problems` returns a vector of `{:graphql/severity :graphql/code :graphql/id
:graphql/msg}` maps; `valid?` is true iff there are no `:error`s:

```clojure
(require '[graphql.validate :as v])
(v/valid? schema)      ;=> true
(v/problems broken)    ;=> [{:graphql/severity :error :graphql/code :field/unknown-type …}]
```

Errors: `:schema/missing-query-root` (query-root type not defined),
`:field/unknown-type` (field references an undefined type),
`:field/duplicate-name` (two fields share a name in the same type),
`:arg/unknown-type` (argument references an undefined type).

## Execution (`graphql.execute` + `graphql.ports`)

A **pure field-resolution executor**. State is plain data — inspectable,
replayable, testable offline. The host injects one port (`graphql.ports`):

```
IResolver  resolve  [type-name field-name parent args ctx] → value
```

For each selected field, `IResolver/resolve` is called with the parent object;
if the field has sub-selections the result is recursed; if the resolved value is
a sequence, sub-selections are mapped over each element producing a vector;
scalars are returned as-is. `default-ports` makes any schema runnable with no
host (resolves via `(get parent (keyword field-name))`):

```clojure
(require '[graphql.execute :as e]
         '[graphql.ports   :as p])

(e/execute-query
  (e/default-ports)
  schema
  (q/parse-query "{ user { name } }")
  {:user {:name "Alice"}}
  nil)
;=> {"user" {"name" "Alice"}}
```

For real work, inject a resolver that calls a database or service; the executor
stays pure orchestration.

## Test

```
kbb -M:test
```
