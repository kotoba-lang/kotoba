# ADR 0001: Validation problems are sovereign Kotoba

`src/kotoba/dsl/problem.kotoba` is the sole production language source. JVM
Clojure is a compiler/test host only and is not a production runtime.

The former open EDN API becomes a typed boundary: domains, field names,
severities, and codes are keywords; subjects and problem collections are
bounded canonical documents; messages are bounded strings. The public
`severities` value becomes a zero-argument typed-set getter. The common
five-argument `problem` constructor is retained. The former six-argument
subject-key overload becomes `problem-field`, with `[keyword, subject]` carried
as one canonical bounded document so the shared five-parameter native fuel ABI
is not weakened. Filtering is explicit bounded recursion over at most 32
problems.

Unsupported severities, missing domain severity fields, malformed canonical
documents, value-budget overflow, and recursion/fuel exhaustion fail closed.
The program declares no effects. Conformance covers observable values, typed
ABI, effect declarations, resource bounds, and rejection behavior across
reference execution, restricted JavaScript, and instantiated typed Wasm.

## Amendment, 2026-08-13 — authority is not the same thing as load path

Everything above stands, with one sentence corrected: *sole production language
source* was implemented as *sole file in `src/`*, and those are not the same
claim. Removing `src/kotoba/dsl/problem.cljk` on 2026-07-21 did not make the
`.kotoba` the thing consumers run. It made `kotoba.dsl.problem` **unloadable**,
because no Clojure, ClojureScript or nbb loader can require a `.kotoba` file
and nothing in this repo emitted one they could. Eleven repos
(`org-oasis-open-xmile`, `org-omg-sysmlv2`, `org-omg-uml`, `org-sbml`,
`org-w3-owl2`, `org-w3-rdf`, `policy`, `sigma`, `statechart`, `states`,
`torch`) require this namespace, and six XMILE execution paths in
`loop-system-dynamics` sat behind them. They were broken for 17 days and no CI
noticed, because this repo's CI is green — it drives the `.kotoba` through a
JVM host, and it does not look at consumers. See `com-junkawasaki/root`
ADR-2608071000 and ADR-2608130900.

So `src/kotoba/dsl/problem.cljk` is restored, and the two files divide as
follows:

- **`problem.kotoba` is the semantic authority.** It is what the typed-ABI,
  restricted-JavaScript and typed-Wasm conformance tests execute, it declares
  no effects, and it is what the resource bounds above describe. When the two
  disagree, it is right and the `.cljc` is wrong.
- **`problem.cljc` is the load path.** It exists because consumers must be able
  to `require` the namespace today, on runtimes that cannot load the guest.

They are held in agreement by `test/kotoba/dsl/problem_parity_test.cljk`, which
compiles the `.kotoba` and runs it through the KIR interpreter in the same JVM,
then compares its typed documents against the `.cljc` output encoded into the
same document form. `kotoba-lang/compiler` is therefore a **test-only**
dependency: consumers get the `.cljc` and nothing else. This is the shape
`kotoba-lang/css` already uses, where `css.core` stayed put behind a
byte-equality gate while `kotoba/css_core.kotoba` was added beside it.

Two divergences are deliberate and are properties of the guest's execution
sandbox rather than of the semantics:

- **Bounds.** The guest is bounded (32 items per container, 256 nodes, depth 8,
  64 KiB of text). The `.cljc` is not. A validator emitting 40 problems is
  representable in the `.cljc` and is not representable as one document. The
  parity gate asserts agreement *inside* the guest's bounds and says so.
- **Failure mechanism.** The guest fails closed by trapping and surfaces as
  `ExceptionInfo` at the execution boundary; the `.cljc` throws `ex-info`
  directly. The gate asserts *both refuse*, not that both throw the same
  object.

The retirement condition for the `.cljc` is unchanged in spirit and now
explicit: **it goes away when consumers have a load path that does not need
it** — that is, when this namespace can be executed by consumers directly from
the guest. For the native route that is ADR-2607279200 W4 (recursive logical
values), because `problem`/`problem-field` return `:document` and `errors`
returns a collection, and the native backend carries neither. Until then,
removing the `.cljc` is not a migration step; it is an outage.

The enforcement test `production-source-authority` is kept and narrowed rather
than deleted: `src/` must contain exactly these two files. A third file, or a
second `.cljc`, would be a fork of the authority and is still refused.
