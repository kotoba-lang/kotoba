# sigma-clj (検知ルール)

[![CI](https://github.com/kotoba-lang/sigma/actions/workflows/ci.yml/badge.svg)](https://github.com/kotoba-lang/sigma/actions/workflows/ci.yml)

Handle **Sigma detection rules as EDN/Clojure data** in portable Clojure — every
namespace is `.cljc`, with **zero third-party runtime deps**, so it runs on the JVM,
ClojureScript, and Clojure-on-WASM hosts (SCI). A Sigma rule is plain data you can
`assoc`, `diff`, store in Datomic, or generate; the library adds structural
validation, a YAML-shape ↔ EDN converter, and a pure event matcher around it.

Natural companion to
[ghosthacker](https://github.com/com-junkawasaki/ghosthacker) (security tooling)
and a sibling of the other reusable `*-clj` kernels in this org
([bpmn-clj](https://github.com/com-junkawasaki/bpmn-clj),
[dmn-clj](https://github.com/com-junkawasaki/dmn-clj)).

## Why a shared library (org placement)

Per the three-org rule, the **reusable** detection model lives in **com-junkawasaki**;
**public-benefit actor instances** that drive concrete detection pipelines live in
**etzhayyim**; any **business/private deployment** lives in **gftdcojp**. sigma-clj
is the dep — it carries no domain rules and no engine bindings (those are
host-injected ports). Sigma rules themselves belong to the consuming org.

## The model: Sigma rule as EDN (`sigma.model`)

Rules are namespaced `:sigma/*` maps; selections are string-keyed (preserving the
YAML field-key format including `|modifier` suffixes):

```clojure
{:sigma/id    "bf-01"
 :sigma/title "Brute Force Login Attempt"
 :sigma/level :high
 :sigma/logsource {:sigma/product "windows" :sigma/service "security"}
 :sigma/detection
   {:sigma/selections
      {"sel"  {"EventID" [4625] "TargetUserName|contains" ["adm"]}
       "filt" {"IpAddress" ["127.0.0.1"]}}
    :sigma/condition "sel and not filt"}}
```

A threading-friendly builder:

```clojure
(require '[sigma.model :as m])

(def rule
  (-> (m/rule "bf-01" "Brute Force Login" {:level :high
                                            :logsource {:sigma/product "windows"
                                                        :sigma/service "security"}})
      (m/add-selection "sel"  {"EventID" [4625] "TargetUserName|contains" ["adm"]})
      (m/add-selection "filt" {"IpAddress" ["127.0.0.1"]})
      (m/set-condition "sel and not filt")))

(m/selection-names rule)   ;=> #{"sel" "filt"}
(m/condition rule)         ;=> "sel and not filt"
```

## Validation (`sigma.validate`)

`problems` returns a vector of `{:sigma/severity :error|:warn :sigma/code :sigma/id :sigma/msg}`;
`valid?` is true iff there are no `:error`s (warnings are advisory):

```clojure
(require '[sigma.validate :as v])
(v/valid? rule)            ;=> true
(v/problems broken)        ;=> [{:sigma/severity :error :sigma/code :condition/unknown-selection …}]
```

Errors: condition references undefined selection, unknown field modifier.
Warnings: unknown `:sigma/level` (advisory — Sigma evolves; known levels are
`:informational` `:low` `:medium` `:high` `:critical`), glob in condition matches no
defined selection.

## YAML shape ↔ EDN (`sigma.yaml`)

`from-data` converts an **already-parsed** Sigma YAML map (string keys, as a YAML
library like `clj-yaml` would produce) to the `:sigma/*` model. `to-data` does the
reverse. **YAML text is never parsed here** — inject your platform's YAML parser:

```clojure
(require '[sigma.yaml :as y])

;; Host already parsed YAML to a Clojure map with string keys:
(def data {"title" "Brute Force Login" "id" "bf-01" "level" "high"
           "logsource" {"product" "windows" "service" "security"}
           "detection" {"sel"  {"EventID" [4625] "TargetUserName|contains" ["adm"]}
                        "filt" {"IpAddress" ["127.0.0.1"]}
                        "condition" "sel and not filt"}})

(def rule (y/from-data data))
(:sigma/level rule)          ;=> :high

(= data (y/to-data rule))    ;=> true  (round-trip lossless)
```

## Ports (`sigma.ports`)

The host injects `IField` so sigma-clj never assumes the event schema:

```
IField   extract  [field-name event]   — String field name + event map → value
```

`default-ports` tries string key then keyword key — sufficient for plain maps.
For structured log schemas (nested maps, schema registries, typed fields), supply
a custom `IField` implementation.

## Execution (`sigma.execute` + `sigma.ports`)

A **pure event matcher** — no I/O, no side effects. Compiles each named selection
to a predicate, then evaluates the condition expression:

```clojure
(require '[sigma.execute :as e]
         '[sigma.ports   :as p])

(def pts (p/default-ports))

(e/matches? pts rule {"EventID" 4625 "TargetUserName" "administrator" "IpAddress" "10.0.0.1"})
;=> true   (sel=true, filt=false)

(e/matches? pts rule {"EventID" 4625 "TargetUserName" "administrator" "IpAddress" "127.0.0.1"})
;=> false  (filtered: filt=true)
```

**Condition expression** supports identifiers, `and` / `or` / `not`, parentheses,
`1 of <glob>` (any selection whose name matches the glob, e.g. `sel*`), and
`all of them`.

**Field modifiers** (pipe-suffix on field keys):

| Modifier     | Semantics                                          |
|--------------|----------------------------------------------------|
| `contains`   | field value (as string) contains the criterion     |
| `startswith` | field value starts with the criterion              |
| `endswith`   | field value ends with the criterion                |
| `re`         | `re-find` match of criterion regex in field value  |
| `gt`         | field value (numeric) > criterion (numeric)        |
| `lt`         | field value (numeric) < criterion (numeric)        |
| `all`        | AND over the value list instead of OR              |

Modifiers combine: `"Cmd|contains|all"` means the field must contain **all** listed
values. `default-ports` handles plain string/keyword-keyed event maps; replace with
a custom `IField` for structured schemas.

**Security synergy**: sigma-clj pairs naturally with
[ghosthacker](https://github.com/com-junkawasaki/ghosthacker) — ghosthacker can
produce structured event maps from its security tooling output, and sigma-clj
evaluates Sigma detection rules against them without any additional dependencies.

## Test

```
kbb -X:test
```

## Kotoba bounded profile

`src/sigma/bounded_vocabulary.kotoba` is a capability-free port of
`sigma.model`'s **closed** detection-rule vocabulary — the five severity
levels (`known-levels`) and the seven field-key pipe-modifiers
(`known-modifiers`) — plus a name-keyed selection registry
(selection-name → criteria count) as `kotoba-lang/compiler`'s canonical
bounded typed-map (`[:map :string :i64]`, ≤31 entries). The open, nested
criteria maps, the condition-string parser (and/or/not, quantifiers, glob
matching), and the JSON/YAML I/O stay the CLJC oracle
(`sigma.model`/`sigma.validate`/`sigma.execute`/`sigma.yaml`). See
[migration/bounded-vocabulary-and-selection-registry-v1.edn](migration/bounded-vocabulary-and-selection-registry-v1.edn).
