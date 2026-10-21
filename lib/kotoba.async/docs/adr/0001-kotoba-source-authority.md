# ADR 0001: bounded channel state machines are sovereign Kotoba

The production implementation is `src/kotoba/lang/async.kotoba`. JVM
Clojure is used only to host compiler qualification tests, never as the
production runtime.

Channel payloads use canonical `:document` values. Capacity is restricted to
1–32 items, matching the document container budget. Unknown buffer kinds and
invalid capacities fail closed. Lookup is option-returning; persistent updates
cannot mutate host-owned values.

The state machine has no threads, clocks, I/O, or scheduler authority. A host
or durable loop may thread states through it, but must obtain those effects
through separately admitted capabilities.

Conformance compares observable state transitions, typed ABI behavior,
resource bounds, and rejection behavior across reference execution,
restricted JavaScript, and instantiated typed Wasm. Wasm byte identity is not
a compatibility requirement.

## Amendment, 2026-08-13 — authority is not the same thing as load path

Everything above stands, with one sentence corrected: *the production
implementation is `src/kotoba/lang/async.kotoba`* was implemented as *`src/`
contains only that file*, and those are not the same claim. Removing
`src/kotoba/lang/async.cljk` on 2026-07-20 did not make the `.kotoba` the thing
consumers run. It made `kotoba.lang.async` **unloadable**, because no Clojure,
ClojureScript or nbb loader can require a `.kotoba` file.
`kotoba-lang/scheduler` requires this namespace from `src/kotoba/lang/scheduler.cljc`
and `src/kotoba/lang/scheduler/driver.cljc` — not only from its tests. It kept
working solely because its `deps.edn` pins a pre-migration sha of this repo;
the first person to advance that pin would have broken it, and any consumer
loading this repo from a local checkout (nbb, shadow-cljs) was broken already.

This is the same class of defect `com-junkawasaki/root` ADR-2608071000 recorded
for `kotoba-lang/dsl-core`, found in this repo afterwards by
`scripts/verify-require-graph.cljs`. See ADR-2608130900.

So `src/kotoba/lang/async.cljk` is restored, and the two files divide as
follows:

- **`async.kotoba` is the semantic authority.** It is what the typed-ABI,
  restricted-JavaScript and typed-Wasm conformance tests execute, and it is
  what the resource bounds above describe. Where the two disagreed, it won: the
  restored `.cljc` takes the guest's `can-put?` (a closed channel accepts
  nothing — the original returned `true` for a closed non-full fixed channel
  while its own `put` refused it) and the guest's boolean `closed?`.
- **`async.cljc` is the load path.** It exists so consumers can `require` the
  namespace on runtimes that cannot load the guest.

They are held in agreement by `test/kotoba/lang/async_parity_test.cljk`, which
compiles the `.kotoba`, runs it through the KIR interpreter in the same JVM,
and threads identical operation scripts through both implementations,
comparing the entire channel state after every transition. `kotoba-lang/compiler`
is therefore a **test-only** dependency.

### The capacity bound is a guest bound, and it is narrower than the consumer

Capacity 1..32 is not a decision about channels; it is the KIR document
container budget. `kotoba-lang/scheduler` opens its ready queue as
`(chan :dropping 64)`. **The guest cannot represent that channel at all.** The
restored `.cljc` therefore keeps capacity unbounded, and the parity gate
asserts agreement for capacities 1..32 while asserting the divergence outside
that range explicitly, including a run of the scheduler's actual 64-slot
dropping queue. Narrowing the `.cljc` to 32 would not be parity — it would be
breaking the only consumer to flatter the port.

The retirement condition for the `.cljc` is that consumers gain a load path
that does not need it, *and* that the guest can represent the channels they
actually open. Until both hold, removing the `.cljc` is not a migration step;
it is an outage.

The enforcement test `production-source-authority` is kept and narrowed rather
than deleted: `src/` must contain exactly these two files.
