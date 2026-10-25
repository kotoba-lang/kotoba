# com-cloudflare-workers

A `kotoba/host` capability layer for the Cloudflare Workers **storage
bindings** -- KV, D1, R2 -- so `.kotoba` application code can drive them
without ever holding ambient authority over them.

Sibling repo, different plane: [`com-cloudflare`](../com-cloudflare) is the
**control plane** (Cloudflare API v4: zones, DNS, Workers routes, Pages,
analytics, Logpush). This repo is the **data plane** (`env.SESSIONS`,
`env.APP_DB`, `env.ASSETS` inside a running Worker). They share no code and
answer different questions.

## Why this is not a set of host imports

The obvious design would be to add `kv_get` / `d1_query` / `r2_put` to
`kotoba-core-contracts`' closed `:host-imports` table, next to `pg_*` and
`db_*`. That design is unsound here and the reason is worth stating plainly,
because it is the whole shape of this repo:

**Wasm host imports are synchronous. D1, KV and R2 are not, and a Worker
cannot block.** The JVM host can block a thread inside `pg_query`; the browser
host can, with COOP/COEP, block on `Atomics.wait` over a SharedArrayBuffer.
workerd gives you neither -- there is no blocking wait on the request thread
and no JSPI. A synchronous `kv_get` import could therefore only be implemented
by lying: returning a stale value, an empty one, or wedging the isolate. So it
is not implemented. A capability that cannot be honoured is not added to a
closed contract.

Instead this family lives on the **typed effect-command plane** described in
`kotoba-lang/kotoba`'s `docs/lang/application-profile.md`:

```text
[host]  materialize declared reads (async)
          v  input
[guest] pure planner: state + event -> next state + effect commands
          v  commands (inert data)
[host]  admission: policy ∩ grants ∩ request -> quota -> execute -> receipts
          v  typed result events
```

The guest gets no new import, no handle, and no `env`. There is no capability
for it to leak because it is handed none: it emits *proposals*, and the host
decides. Design record: **ADR-2607253500**.

## The safety properties, concretely

**Guest-authored SQL is unrepresentable, not filtered.** A D1 command names a
statement id (`"order-by-id"`); the SQL text lives in host policy. A command
carrying `:sql` is denied by name (`:raw-sql-forbidden`). There is no escaping
or sanitizing step to get wrong.

**The required capability comes from the statement, not the command.** Policy
registers `insert-order` as `:mode :write`, so naming it requires
`:cf/d1-write` no matter what the guest calls the operation. A read-only grant
cannot be widened by relabeling.

**Absence never grants.** No `:caps` means nothing permitted; no
`:key-prefixes` means no key is reachable; no `:statements` means no D1 call is
possible; `:policy/forbid-wildcard` defaults to *true*. The safe policy is the
one you get by writing nothing, following
`kotoba.host-providers/resource-scope`, where a missing network allowlist means
no URLs rather than all of them.

**Command maps are closed.** An unknown key is a denial, so a provider option
a guest learned about before the policy did cannot be smuggled through.

**Batches are fail-closed as a unit.** A guest plans "write the row, then set
the key" as one thought. If the tail is denied, running the prefix leaves
storage in a state the guest never reasoned about -- so by default *nothing*
runs (`:on-deny :abort`). `:on-deny :skip` exists and must be asked for.

**No ambient fallback.** A policy that names a binding the deployment lacks is
a failure, not a silent skip and not an in-memory stand-in -- otherwise a
Worker deployed without its D1 database appears to work while writing nothing.
Binding *kind* is verified by shape (`getWithMetadata` / `prepare` / `head`),
so a policy that calls an R2 bucket a KV namespace is caught before use.

**Every attempt is receipted, including denials** (`capability-semantics.edn`:
`:attempt-always-receipted`), and denial (`:denied`) is kept distinct from
provider failure (`:failed`). Conflating "you were not allowed to" with "it did
not work" hides an authorization bug and an availability one at the same time.

**The pure core reads no clock.** `now` is a parameter everywhere. A pure core
that reaches for the current time has taken an authority nobody granted it.

## Layout

```text
src/cloudflare/workers/
  command.cljc     structural gate: shape, types, bounds. No authority questions.
  policy.cljc      operator-owned, deny-by-default policy + SQL/arity cross-check
  admission.cljc   policy x quota x command -> allow / one enumerated denial reason
  receipt.cljc     audit receipts (:receipt/cap :at :call :outcome)
  provider.cljs    workerd executor -- the only code that touches a real binding
resources/cloudflare/workers/capability_descriptors.edn
                   typed descriptors, denial-reason enumeration, completion-gate status
examples/          session_planner.kotoba (guest shape), worker.cljs (host wiring)
```

`provider/execute!` re-runs admission itself rather than trusting an
already-admitted list, so no code path -- including a future refactor --
reaches `env.DB` without passing the gate.

## Usage

```clojure
(require '[cloudflare.workers.provider :as provider])

(provider/execute!
 {:env env                                  ; the Worker's env
  :policy policy                            ; host-owned, see examples/worker.kotoba
  :commands [{:cmd :cf.d1/exec :binding "APP_DB" :statement "insert-order"
              :params ["o-1" 2]}
             {:cmd :cf.kv/put :binding "SESSIONS" :key "user:42"
              :value "pending" :ttl 300}]
  :now (.toISOString (js/Date.))})
;; => Promise of {:outcome :allowed :events [...] :receipts [...]}
;;             | {:outcome :denied  :reason kw :index i :receipts [...] :events []}
;;             | {:outcome :failed  :reason kw :index i :events [...] :receipts [...]}
```

Call `provider/preflight` once at module scope to catch a deployment whose
bindings do not match its policy.

## Tests

```bash
npm test                 # nbb: full suite incl. the .cljs provider (42 tests)
kbb -M:test          # JVM: the same .cljc core, second runtime (34 tests)
kbb -M:lint
```

The dual run is the parity evidence for the core: one set of `.cljc` sources,
two independent readers and runtimes. Conformance fixtures live in
`test/cloudflare/workers/conformance_test.kotoba`, with one fixture per denial
reason -- an enumerated reason no test can produce is a reason nobody has
checked is reachable.

## What is not done

Measured against the six-item completion gate in `application-profile.md`
(machine-readable status in `capability_descriptors.edn`):

| # | Gate item | Status |
|---|---|---|
| 1 | Typed descriptors in the closed capability contract | partial -- typed and closed here; kinds not yet registered in `kotoba-lang/kotoba-lang` |
| 2 | Effect inference and compiler admission | **not started** -- needs the guest frame ABI plus `effect-for-kind` / `op->kind` entries across two core repos |
| 3 | Policy-gated provider, no ambient fallback | done |
| 4 | Positive and denial conformance fixtures | done |
| 5 | Quota, cancellation, fuel/memory, audit | partial -- quota and audit done; request-abort cancellation not threaded through `execute!` |
| 6 | Parity across two applicable runtimes | partial -- core yes (nbb + JVM); provider has one applicable runtime, miniflare live test outstanding |

Per the application profile: **a family may be documented as planned before
the gate passes, but must not claim runtime support.** The host-side gate in
this repo is real, tested and usable from ClojureScript today. The
`.kotoba` guest -> provider path is not wired; `examples/session_planner.kotoba`
shows its shape and says so at the top.

## License

MIT (c) 2026 Jun Kawasaki
