# ci-clj (CI ワークフロー)

Handle **GitHub Actions workflows as EDN/Clojure data** and plan their
**job-DAG** in portable Clojure — every namespace is `.cljc`, with **zero
third-party runtime deps**, so it runs on the JVM, ClojureScript, and
Clojure-on-WASM hosts (SCI). A workflow is plain data you can `assoc`, `diff`,
store in Datomic, or generate; the library adds the DAG queries, structural
validation, YAML-data I/O, and a pure wave-based planner around it.

Sibling of the other reusable `*-clj` kernels in this org
([bpmn-clj](https://github.com/com-junkawasaki/bpmn-clj),
[dmn-clj](https://github.com/com-junkawasaki/dmn-clj)). This library is also
a natural fit for describing and validating the CI workflows that power this
very superproject's own pipeline, without pulling in a YAML parser as a
transitive runtime dep.

## Why a shared library (org placement)

Per the three-org rule, the **reusable** CI workflow model lives in
**com-junkawasaki**; **public-benefit actor instances** that emit or interpret
concrete pipelines live in **etzhayyim**; any **business/private deployment**
lives in **gftdcojp**. ci-clj is the dep — it carries no domain workflow and
no engine bindings (those are host responsibilities).

## The model: workflow as EDN (`ci.model`)

Jobs are id-keyed maps; topology comes from each job's `:ci/needs` vector,
never document order:

```clojure
{:ci/name "CI"
 :ci/on   {"push" {"branches" ["main"]}}
 :ci/jobs {"build" {:ci/id      "build"
                    :ci/runs-on "ubuntu-latest"
                    :ci/needs   []
                    :ci/steps   [{:ci/uses "actions/checkout@v4"}
                                 {:ci/run  "make"}]}
           "test"  {:ci/id      "test"
                    :ci/runs-on "ubuntu-latest"
                    :ci/needs   ["build"]
                    :ci/steps   [{:ci/run "make test"}]}}}
```

A threading-friendly builder, plus DAG queries (`dependents` returns jobs
whose `:ci/needs` list a given id; `topo-order` is deterministic — sorted at
each Kahn step):

```clojure
(require '[ci.model :as m])

(def wf
  (-> (m/workflow "CI" {:on {"push" {"branches" ["main"]}}})
      (m/add-job (m/make-job "build" {:runs-on "ubuntu-latest"
                                      :steps   [{:ci/uses "actions/checkout@v4"}
                                                {:ci/run  "make"}]}))
      (m/add-job (m/make-job "test"  {:runs-on "ubuntu-latest"
                                      :needs   ["build"]
                                      :steps   [{:ci/run "make test"}]}))))

(m/topo-order wf)          ;=> ["build" "test"]
(m/dependents wf "build")  ;=> ["test"]
```

When a cycle exists, `topo-order` returns a `{:ci/cycle [...]}` sentinel
(never throws) listing the involved job ids.

## Validation (`ci.validate`)

`problems` returns a vector of `{:ci/severity :error|:warn :ci/code :ci/id :ci/msg}`;
`valid?` is true iff there are no `:error`s (warnings are advisory):

```clojure
(require '[ci.validate :as v])
(v/valid? wf)            ;=> true
(v/problems broken)      ;=> [{:ci/severity :error :ci/code :job/dangling-need …}]
```

Errors: a job's `:ci/needs` references a non-existent job; the job DAG is
cyclic; a step carries more or less than one action among `:ci/uses`,
`:ci/run`, and the shell-free `:ci/argv` form.
Warnings: a job has no `:ci/runs-on`.

## YAML data I/O (`ci.yaml`)

`from-data` / `to-data` operate on an **already-parsed** YAML map (string keys
as a YAML library such as `clj-yaml` or `snakeyaml` would produce) — ci-clj
itself never parses YAML text, keeping it dep-free and host-agnostic:

```clojure
(require '[ci.yaml :as y])

;; a parsed YAML map from e.g. (clj-yaml.core/parse-string yaml-text)
(def parsed {"name" "CI"
             "on"   {"push" {"branches" ["main"]}}
             "jobs" {"build" {"runs-on" "ubuntu-latest"
                              "needs"   nil
                              "steps"   [{"uses" "actions/checkout@v4"}]}
                     "test"  {"runs-on" "ubuntu-latest"
                              "needs"   "build"     ; bare string — normalised to vec
                              "steps"   [{"run" "make test"}]}}})

(def model (y/from-data parsed))
;; => {:ci/name "CI" :ci/on {…} :ci/jobs {"build" {:ci/needs [] …} "test" {:ci/needs ["build"] …}}}

(y/to-data model)         ; round-trips back to string-keyed shape
```

`needs` is normalised: absent/nil → `[]`, a bare string → `["build"]`, a list
→ vec as-is.

## Execution / planning (`ci.execute`)

`plan` partitions the job DAG into **waves** — each wave holds the id-sorted
jobs that can run in parallel once all prior waves have completed:

```clojure
(require '[ci.execute :as e])

(e/plan wf)
;=> [["build"] ["test"]]
```

When the DAG has a cycle, `plan` returns the `{:ci/cycle [...]}` sentinel
rather than a wave vector. Pure — no ports, no I/O.

## Portable run state (`ci.run`)

`new-run` binds an immutable source descriptor to a validated workflow and its
wave plan. `transition` permits only legal queued/leased/running/terminal
transitions, increments a revision, and appends plain-data events. Clocks,
persistence, execution, and receipt signing remain host responsibilities.

## Test

```
kbb -M:test
```
