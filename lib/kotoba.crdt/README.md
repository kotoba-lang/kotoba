# crdt

[![CI](https://github.com/kotoba-lang/crdt/actions/workflows/ci.yml/badge.svg)](https://github.com/kotoba-lang/crdt/actions/workflows/ci.yml)

Portable CLJC convergent-replica primitives for Kotoba document editors
(slides, docs, sheets, KAMI scenes...). Pure data, pure functions — no network,
no storage, no actor identity. Hosts own every effect; this package only knows
how to merge.

One runtime dependency, and it is the point rather than an accident: this used
to say "zero-dependency", and that stopped being true when `clock.kotoba`
stopped being a checked replica and became what runs. See [Where the Lamport
rules live](#where-the-lamport-rules-live).

## Why

Before this package, nothing in `kotoba-lang` merged concurrent edits.
`kotobase`'s `IStore` gives durable, host-swappable persistence and an
append-only log for free (`put/get` = last-writer-wins, `append/read(since)`
= a Kafka-offset-style history stream) — but its documents are LWW: two
editors racing on the same key silently drop one write. `mst` gives a
merkle-diff primitive for efficient state comparison. Neither gives you
"two editors add different shapes to the same deck at the same time and both
survive," which is table stakes for real collaborative editing. `crdt` fills
that gap.

## Layers

```
kotoba.crdt.clock     Lamport (counter, actor) stamps — the merge tiebreak
kotoba.crdt.register  LWW-Register — one field, one winner by stamp
kotoba.crdt.orset     Observed-Remove Set (add-wins) — entity membership
kotoba.crdt.doc       entity-attribute doc = orset of ids + per-field registers
```

The `.kotoba` files are explicit bounded profiles, not silent replacements
for the arbitrary CLJC domains. `clock.kotoba` uses registry-backed positive
i64 actor IDs, `register.kotoba` stores strings, and `orset.kotoba` uses i64
entity IDs plus nominal Lamport-stamp tags. The OR-set stores canonical typed
maps rather than host maps/sets, returns typed options for absence, and merges
by fuel-bounded canonical entry traversal. Its conformance module proves
add-wins behavior plus commutativity, associativity and idempotence on the
reference, restricted Web and Wasm runtimes. Consumers whose IDs or values do
not have a reviewed mapping continue to use the CLJC API.

`doc.kotoba` composes that OR-set with the `string-v1` register as
`string-document-v1`: i64 entities, keyword field IDs and string field values.
Its operations are a closed add/remove/set-field variant; state merge walks
canonical nested maps and resolves registers by nominal Lamport stamps. The
conformance graph proves op replay idempotence, deterministic LWW selection,
and commutative/associative/idempotent state merge on reference, Web and Wasm.

`kotoba.crdt.doc` is the integration surface. A document is an OR-Set of
entity ids (slide ids, shape ids, block ids, row ids...) plus, per entity, a
map of field -> LWW-Register:

```clojure
(require '[kotoba.crdt.clock :as clock]
         '[kotoba.crdt.doc :as doc])

(def alice (clock/init "alice"))
(def bob (clock/init "bob"))

(let [[d alice op-add] (doc/add-entity (doc/init) alice "shape-1")
      [d alice op-set] (doc/set-field d alice "shape-1" :slides/x 1.5)]
  (doc/snapshot d))
;;=> {"shape-1" {:slides/x 1.5}}
```

Every mutation returns `[doc' clock' op]`. `op` is a plain EDN map — broadcast
it to other replicas (a WebSocket fan-out, a `kotobase` `append`, whatever the
host wires up) and each one converges by calling `apply-op`/`receive`:

```clojure
;; on another replica, receiving alice's op:
(let [[remote-doc remote-clock] (doc/receive remote-doc remote-clock op-add)]
  ...)
```

Two synchronization strategies, both supported:

- **op-based** — `apply-op`/`apply-ops`/`receive` replay individual ops.
  Pairs naturally with `kotobase`'s `append`/`read(since)`: ops ARE the log
  entries, and a reconnecting editor replays everything after its last-seen
  `:seq`.
- **state-based** — `merge-docs` merges two full document snapshots directly,
  for reconciling a replica that's been offline with no op history at all.

Both are commutative, associative, and idempotent: apply the same ops twice,
or in either order, on any replica, and every replica converges to the same
`snapshot`.

## Where the merge rules live

`kotoba.crdt.clock`'s `init`, `tick`, `observe` and `before?`, and
`kotoba.crdt.register`'s `init`, `write`, `value` and `merge-register`, do not
compute anything in Clojure. They run `src/kotoba/crdt/clock.kotoba` and
`src/kotoba/crdt/register.kotoba` — compiled and shipped as
`resources/kotoba/crdt/oracle/*.kir.edn`, executed through
`kotoba.crdt.kotoba-oracle`. That is why `io.github.kotoba-lang/kotoba-kir` is
a runtime dependency; the compiler that produced the artifacts stays under
`:test` and never reaches a consumer.

The register's artifact is `register.kotoba` **linked against**
`clock.kotoba`, so the stamp comparison that settles an LWW race arrives inside
it. The tiebreak is stated once, in one file, and no longer restated in Clojure
anywhere.

Before this, each `.kotoba` and its `.cljc` were two implementations of one
rule bound by a parity test. Two implementations bound by a test are still two
implementations — the parity tests are still here and still green, but they are
no longer what makes them agree. `kotoba-oracle-test` adds the two questions a
parity test structurally cannot ask: whether the shipped artifact is the
current source compiled, and whether the host actually reads it.

### `orset` and `doc` are not delegated, and the reason is a number

Both compile, link and run, and both are bound to their `.cljc` twins by parity
tests. Neither is in `kotoba-oracle/cores`, because neither *can* be: they hold
collections whose size is the user's document, and the KIR interpreter refuses
an ADT value past a node limit. Measured against the pinned interpreter, with
one add-tag per element:

| core                              | crosses | refused |
| --------------------------------- | ------: | ------: |
| `orset`, elements                 |      10 |      11 |
| `orset`, tags on one element      |      14 |      15 |
| `doc`, entities                   |       4 |       5 |

A document with five shapes in it is not an edge case, so there is no version
of this seam that puts `merge-orset` or `merge-docs` behind a shipped artifact.
That is a property of those cores — an OR-Set merge *is* a whole-collection
operation — not a shortfall in the port, so they keep their parity gates and
nothing pretends otherwise.

`register` is the opposite shape, which is why it is delegated: `merge-register`
is handed exactly two registers no matter how large the document grows, so one
decision's worth of data is a constant. `doc.cljc` reaches it once per field —
so a document whose *state* cannot cross still has its per-field winner decided
by the shipped core.

### Boundaries, stated rather than discovered

- **Actors.** `clock.kotoba` types actors `:i64`; this library has always taken
  any comparable id, and the example above passes `"alice"`. So delegation is
  conditional on the data: integer actors are answered by the shipped core,
  everything else by the host path, unchanged. A non-integer actor is therefore
  served by code no `.kotoba` checks.
- **Values.** `register.kotoba` types values `:string`, bounded at 65536 UTF-8
  bytes. A non-string value, or a longer one, takes the host path rather than
  raising — a document field is allowed to be something the guest cannot hold.
- **Whole registers.** Unlike a clock, which is a host map the guest decides one
  field of, a register *is* the guest value. A register map carrying keys beyond
  the two the artifact declares takes the host path, rather than coming back
  without them.
- **ClojureScript.** There is no classpath to read the artifacts from, so a
  ClojureScript host must call `kotoba-oracle/register-kir!` before a delegated
  call will work. Values that never reach the guest are unaffected.

### ClojureScript is not covered by the test suite

**This repository has no ClojureScript test path** — every test is `.clj`, run
on the JVM, and there is no `package.json`, no `shadow-cljs.edn` and no cljs
dependency. A green suite says nothing about the `:cljs` reader branch, and it
is worth saying so, because one of the two runtime differences is silent on the
JVM:

`kir/execute` coerces a **top-level** `:i64` argument and accepts a host
integer, but an `:i64` **inside a record** goes through
`bounded-typed-value!`, which on ClojureScript requires a `js/BigInt` and
rejects a `js/Number`. A seam that passes record fields unconverted works on
the JVM and throws `value is not a signed i64` on ClojureScript.
`kotoba-lang/calendar` was broken that way for a day under a green suite.

Both seams here convert every `:i64`, including `register`'s stamp nested
inside its register, and
`every-i64-crosses-converted-including-the-ones-nested-in-a-record` holds them
to it. That test gets at the question from the JVM by feeding host maps whose
numbers are `Integer`: on this runtime `oracle/i64` is `(long n)`, so an
unconverted field stays an `Integer` and is visible. **The inbound direction is
not covered** — `oracle/i64-value` is identity on the JVM, so a missing
conversion there cannot be detected here by any means, only read.
- **`stamp`, `after?`, `max-stamp`** have no Kotoba counterpart and still
  compute here. `after?` and `max-stamp` are phrased in terms of `before?`, so
  the order they use did move; `stamp` is a `select-keys`.

Regenerate the artifacts after editing any `.kotoba` under `src/`:

```bash
kbb -M:test:gen
```

## What this does *not* do

**Concurrent writes to the same field of the same entity are not merged
character-by-character.** `kotoba.crdt.register` is a plain LWW-Register: one
write wins (by Lamport stamp, deterministically the same on every replica),
the other is silently discarded. There is no RGA/OT text-merge layer here.
Two editors typing in the same text box at the same moment is out of scope —
concurrent edits to *different* shapes, or *different* fields of the same
shape, are the actual guarantee this package makes.

**No transport, no auth, no persistence.** Wiring `doc/add-entity`'s returned
`op` onto a wire, authenticating who's allowed to write, and durably storing
the op log are all host concerns — see `kotobase` (`IStore` `append`/`read`)
for the storage/transport substrate and AGENTS.md's kotoba-server CACAO
section for per-actor signing identity.

## Test

```bash
kbb -M:test
kbb -M:coverage
```
