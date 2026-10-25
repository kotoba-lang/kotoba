# kotoba-selfhost-contracts

EDN authority for Kotoba selfhost contracts.

This repo owns shipped selfhost seed values such as provider catalogs, runtime
contracts, SDK/release contracts, updater contracts, and native host contracts.
Launchers and adapters read these resources; they do not own the values.

Run:

```sh
kbb -M:test
```

## `kotoba/` — decisions, not seeds

Most of this repo is values that someone else decides with. `kotoba/` is the
exception: it holds the decisions that belong to a seed, authored in Kotoba.

- `kotoba/safe_analyzer_core.kotoba` — the safe analyzer's op classification
  over `resources/kotoba/selfhost/safe_analyzer_facts.edn`.
- `kotoba/capability_admission_core.kotoba` — effect algebra, minimal policy,
  policy check and admission over the same seed. Effect sets are six bits of an
  `:i64`, so the whole algebra is integer ops and stays word-typed.

`effect-bit` assigns **bit i to index i of `:effect-ops`**, so reordering that
vector is a wire change, not a formatting change. The authority test fails on
it; nothing else would notice.

Admission and sufficiency are different questions. `admission-code` denies only
an *empty* intersection, so a partial policy is admitted with a narrowed scope —
ask `authority-sufficient?` before treating code 0 as "has what it needs".

The seed keeps owning *which* ops are in a class; the `.kotoba` owns *what it
means* to be in one, and `test/kotoba/selfhost/safe_analyzer_core_test.cljk`
refuses to let either move alone. The compiler is a test-only dependency
(ADR-reliability-t63): nothing in `src/` requires it.

## What ships, and what runs it

`resources/kotoba/selfhost/oracle/*.kir.edn` is the compiled artifact.
`kotoba.selfhost.oracle` loads it; `kotoba.selfhost.analyzer` is the host
traversal that calls it. The compiler is **not** a runtime dependency — it
produced the artifacts under `:test` and is not on this classpath. The KIR
interpreter is.

```clojure
(require '[kotoba.selfhost.analyzer :as a])
(a/analyze ["kgraph-query" "llm-infer" "+"]      ; ops the caller's walk found
           declared-mask
           {:delegated g :policy p :now t :expires e})
;; => {:inferred … :undeclared … :unused … :minimal-policy …
;;     :admission {:outcome :admit :sufficient? false :shortfall …}}
```

`:outcome :admit` does **not** mean the program has what it needs — a partial
policy is admitted with a narrowed scope. Check `:sufficient?`.

## Running it natively

The same decisions also compile to machine code for the host ISA. Nothing in
`src/` changes to use them — `oracle/open-native!` swaps the engine under
`oracle/call`, and `kotoba.selfhost.analyzer`, the only caller, does not know
which one answered.

```sh
kbb -M:test:native-build target/native   # compile, sign, stage
kbb -M:test:native                       # the parity gate
```

```clojure
(oracle/open-native! "target/native")   ; every call now runs as aarch64/x86_64
(a/classify "kgraph-query")             ; unchanged
(oracle/close-native!)
```

It is opt-in and never a fallback: if the build is missing or unverifiable this
throws rather than quietly interpreting instead. `test-native/` binds the three
columns that must agree — the EDN table, the native ISA, and the interpreter —
across every op in every table, both directions, plus each core's own `test-*`
exports (578 assertions).

Which engine you want depends on the work per call, not on which is "faster".
Measured on an M4 for `safe_analyzer_core`: the interpreter answers a predicate
in about 2 ms; a native session costs ~4 s to open and then ~20–50 ms per call,
nearly all of it process spawn, because a word in and a word out is the case
where a process boundary costs more than the computation. Native earns its
boundary when the call does real work. For this repo, native is qualification
evidence — proof that what ships decides the same thing with nothing
interpreting it.

After editing any `kotoba/*.kotoba`:

```sh
kbb -M:test:gen     # regenerate the shipped artifact
kbb -M:test         # the drift test fails if you forget
```

Cross-target run (`:jvm-kir`, `:js`, `:wasm`), from an `amu` checkout:

```sh
kbb -M:run test  <path>/kotoba/safe_analyzer_core.kotoba
kbb -M:run check <path>/kotoba/safe_analyzer_core.kotoba --profile pure-product
```
