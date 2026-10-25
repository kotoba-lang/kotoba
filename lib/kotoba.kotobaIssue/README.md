# kotoba-issue

A generic **issue → proposal(PR) → review → merge → audit** gate, in portable
Clojure (`.cljc`, zero third-party dependencies).

Built by promoting two already-storage-agnostic modules found duplicated in
sibling apps into one shared library: `cloud-itonami`'s `activity.cljc` +
`approval.cljc` (the propose/approve/execute/audit gate) and `manimani`'s
`agent.cljc` (the plan → act → observe agent-run FSM). Both were already pure,
`store`-injected designs — this library is what they generalize to once named
consistently and shared.

```
src/kotoba/issue/
  store.cljc   the IssueStore contract (get/put/list-entities, append-audit!) + a default in-memory impl
  gate.cljc    issue / proposal("PR") / review / audit constructors + propose!/review!/merge!/dry-run!
  run.cljc     the plan -> act -> observe -> {done|error|awaiting-approval|cancelled} run FSM
```

## Concepts

- **issue** — the inbound thing to triage (an email, a support ticket, a
  business activity). `:kotoba.issue/*`.
- **proposal** (the "PR") — an agent's proposed action against an issue.
  Carries a `risk` tier and a `rationale` (the human-readable "what would
  happen" — the PR's diff). `:kotoba.issue.proposal/*`.
- **review** — a verdict on a proposal: `:approve`, `:reject`, or
  `:request-changes` (send it back to replanning — the one addition neither
  source app had). `:kotoba.issue.review/*`.
- **merge** — realizing an *approved* proposal via caller-supplied handlers
  keyed by proposal kind. This is the "PR merge triggers the action" step;
  `gate/merge!` only owns the state machine + audit, handlers own the actual
  side effect (send an email, call an API, ...).
- **audit** — every transition above appends one audit record. `:kotoba.issue.audit/*`.

## Design

- **Storage-agnostic** — every `gate`/`run` function takes a `store`
  satisfying the 4-fn `IssueStore` contract (`kotoba.issue.store`), not a
  concrete database. `store/mem-store` is a ready-to-use in-memory
  implementation for standalone use, tests, and CLIs. A Datomic/kotobase-backed
  deployment supplies its own adapter satisfying the same contract.
- **Namespace-agnostic by convention, not code** — the library's own
  `:kotoba.issue.*` attribute names are just the *default* vocabulary. A
  consumer with its own existing schema (e.g. cloud-itonami's `:itonami.*`
  attrs) is expected to keep it and write a thin adapter layer at the
  boundary rather than migrating live data — see `docs/adr/0001-architecture.md`.
- **`run.cljc` stays a pure reducer** — `plan`/`observe`/`step`/
  `resume-after-review`/`cancel` never touch a store; side effects are
  *described* as `:effects` data (`{:effect :issue/propose ...}`) for the host
  to interpret. `run/interpret-propose!` is a ready-made interpreter over the
  gate for hosts that don't need a custom one. This mirrors manimani's
  original agent.cljc purity property: GUI/TUI/CI can share the same loop,
  and a crashed run can be reconstructed from its ledger.

## Quickstart

```clojure
;; deps.edn
;; {:deps {io.github.kotoba-lang/kotoba-issue {:git/tag "v0.1.0" :git/sha "…"}}}

(require '[kotoba.issue.store :as store]
         '[kotoba.issue.gate :as gate]
         '[kotoba.issue.run :as run])

(def s (store/mem-store))
(gate/open-issue! s {:id "issue-1" :kind :inbox/mail :title "hello"
                      :source "gmail" :source-id "gm-1"})

;; low-risk proposal: auto-mergeable
(def p (gate/propose! s {:id "prop-1" :issue "issue-1"
                          :kind :gmail/archive :risk :read-only}))
(gate/route {:read-only :auto} p)   ;=> :auto-mergeable
(gate/approve! s "prop-1" {:decider "auto"})
(gate/merge! s {:gmail/archive (fn [_] {:archived true})})
;;=> [{:proposal-id "prop-1" :status :merged}]

;; risky proposal: waits for a human review verdict
(def p2 (gate/propose! s {:id "prop-2" :issue "issue-1" :kind :gmail/draft
                           :risk :external-send :rationale "draft a reply"}))
(gate/route {:read-only :auto} p2)  ;=> :awaiting-review
(gate/review! s "prop-2" :request-changes {:decider "jun" :note "wrong tone"})
(gate/approve! s "prop-2" {:decider "jun" :note "fixed"})
(gate/merge! s {:gmail/draft (fn [_] {:drafted true})})
```

Wiring the pure run FSM to the gate:

```clojure
(def run0 (run/new-run {:run-id "r1" :issue-id "issue-1" :ts 0}))
(def plan-fn (fn [run _ts] {:proposal {:id (str "prop-" (:run/id run))
                                       :issue (:run/issue run)
                                       :kind :gmail/archive :risk :read-only}}))
(def step1 (run/step plan-fn run0 {:type :advance :ts 1}))  ; -> :act, emits {:effect :issue/propose ...}
(def result (run/interpret-propose! s {:gmail/archive (fn [_] {})}
                                    {:read-only :auto} (first (:effects step1))))
(run/observe (:run step1) result 2)   ; -> :done (auto-merged) or :awaiting-approval
```

## BCF 3.0 model issues

`kotoba.issue.bcf` provides a portable buildingSMART BCF 3.0 topic, comment,
camera viewpoint, component-selection, visibility, and clipping-plane contract.
Topics adapt directly to the generic issue gate, and IDS validation failures can
be converted into model-linked BCF topics while retaining IFC GlobalIds.

On the JVM, `kotoba.issue.bcf.xml` reads and writes `markup.bcf`, viewpoint
`.bcfv` XML, and complete `.bcfzip` byte streams, including optional PNG/JPEG
snapshot entries. XML parsing disables DTD and external-entity resolution.
Generated markup and visualization XML are checked against the official
buildingSMART BCF 3.0 `markup.xsd` and `visinfo.xsd` schemas.

## OpenCDE service contract

`kotoba.issue.opencde` supplies a transport-neutral OpenCDE boundary for
foundation discovery, project memberships, immutable document versions, BCF
topic synchronization, optimistic concurrency, idempotent retries, and audit
event cursors. JVM hosts can use `kotoba.issue.opencde.http` for real
authenticated JSON/HTTP Foundation discovery, Documents 1.0 exchange, and BCF
3.0 topic exchange. It applies bearer authentication, URL encoding,
idempotency and optimistic `If-Match` headers, timeouts, and structured HTTP
errors while keeping server-framework and persistent-storage choices local to
the host.

## Mapping from source apps

See [`docs/adr/0001-architecture.md`](docs/adr/0001-architecture.md) for the
full cloud-itonami/manimani → kotoba-issue correspondence table.

## Tests

```sh
kbb -M:test
```
