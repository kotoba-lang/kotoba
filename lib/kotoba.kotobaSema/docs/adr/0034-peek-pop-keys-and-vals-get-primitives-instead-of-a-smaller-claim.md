# 0034 — peek, pop, keys and vals get primitives instead of a smaller claim

Status: accepted
Date: 2026-09-03

## The decision this reverses

ADR 0032 landed `count` and the pair accessors onto the collections that
already had primitives, and deliberately did NOT implement `peek`, `pop`,
`keys` or `vals`. Its reasoning was sound as far as it went: Clojure's `peek`
and `pop` on a VECTOR take from the END, the only sequence-shortening
primitive was `vector-drop`, which drops from the FRONT, there was no
`vector-pop`, and there was no `typed-map-keys` or `typed-map-vals` to
dispatch to. Implementing only `peek` would have left the language authority's
own fixture — `lang/conformance/collections/vector.kotoba`, which is written
as `(peek (pop [7 8 9]))` — still refused while making the claim half true.
So `lang/surface-status.edn` was corrected instead, to stop claiming the four.

The owner's direction on 2026-09-03 was the other way round: **add the
missing primitives so the language actually has these operations, rather than
shrink the authority.** That is what this does.

## What was measured

Against this repository at `7d46f89e` and kotoba-kir at `233bd6b3`, one
`(defn main [] <body>)` per cell, analysed and then executed on KIR:

    (peek [7 8 9])                    operation has no admitted lowering
    (pop [7 8 9])                     operation has no admitted lowering
    (peek (pop [7 8 9]))              operation has no admitted lowering
    (keys (typed-map-new [:map :i64 :i64] 1 10 2 20))
                                      operation has no admitted lowering
    (vals ...)                        operation has no admitted lowering
    (defn peek [a] :i64 a)            ACCEPTED
    (vector-take [1 2 3] 2)           operation has no admitted lowering
    (nth (typed-list-new [:list :i64] 7 8) 1)
                                      nth indexes a bounded vector; got [:list :i64]
    (count (typed-list-new [:list :i64] 1 2))
                                      count requires a bounded vector, ...
    (vector-count (typed-list-new [:list :string] "a" "b"))   2

The last two are the interesting pair. `count` refused a `[:list T]` saying
the type had "no accessor primitive at all", and `vector-count` beside it was
counting that exact carrier, for any item type, and had been all along. So the
list needed a dispatch for counting and a real primitive for indexing, not two
primitives — and `typed-list-count` was written during this change and then
removed. **A primitive whose work an existing one already does is a second
spelling, not a capability, and two counts over one carrier is the shape that
lets the two disagree later.**

## The primitives (kotoba-kir `b021a0d1`)

  * `vector-take` / `vector-f64-take` — `vector-drop`'s mirror. Drop keeps the
    TAIL after the first n; take keeps the HEAD, the first n. Named for what it
    does rather than `vector-pop`, because `pop` is one call to it.
  * `typed-list-nth` — the `[:list T]` accessor. `vector-at`, `vector-get` and
    `vector-drop` all require `:vector-i64` and refuse a list by type.
  * `typed-map-keys` / `typed-map-vals` — in the map's own entry order, the
    order `typed-map-entry-at` walks, so index i names one entry in both.

Both projections answer `[:list T]` and neither is a set. A map's KEYS are
distinct, so a set would carry one of the two faithfully — and its VALUES are
not, so the same carrier for `vals` would silently drop every repeated value
and answer a shorter collection than the map has entries. `typed-list-nth` is
in the same change for that reason: a projection nothing can read an element
out of is a value no program can use.

## Per receiver, and where a reading is refused

Clojure's `peek`/`pop` are RECEIVER-DEPENDENT — the END of a vector, the FRONT
of a list — and this profile has both a bounded vector and a `[:list T]`. So:

| receiver | peek / pop |
|---|---|
| bounded i64 / f64 vector | the END. `(vector-at v (- (count v) 1))` and `(vector-take v (- (count v) 1))` |
| the legacy i64 pair chain | **REFUSED** |
| `[:list T]` | REFUSED — it has `vector-count` and `typed-list-nth` and no rear operation, so neither reading is buildable |
| typed set, canonical map, keyword map, string | REFUSED, naming each one's own primitives |

The pair chain is the ambiguous one, and it is refused for that reason rather
than answered by a guess. The pair chain is this profile's list, so Clojure's
list reading says `peek` is `pair-first` — but a pair chain and an ordinary
integer are both `:i64` here, so `(peek 5)` and `(peek some-chain)` are the
same program to this frontend, and answering either way would read an integer
as a heap pair or refuse a chain that really is a list. The heads that say
which was meant already exist and are unambiguous: `first` and `rest`, which
lower to exactly the pair accessors. The refusal names them.

## Emptiness, and what the choice costs

Clojure's `pop` on an empty collection throws and `peek` returns nil. Neither
is available: emptiness is not statically known here, and there is no nil in
this profile to answer with. Four shapes were open — a not-found argument as
`(nth v i default)` takes, a trap, a typed abort, or refusing the operation.

**This takes the trap**, because that is what the neighbours already do:
`vector-at` traps out of range, `vector-drop` traps, `typed-set-nth` traps,
and `nth` WITHOUT a default is already the empty-vector trap spelled
differently. `pop` needs no special case for it at all — an empty vector makes
the count 0 and the argument -1, and -1 is out of `vector-take`'s range, so
emptiness falls out of the neighbour's own bound.

The cost is real and is this: **a program that does not know its vector is
non-empty cannot ask these two heads safely**, and must write
`(if (= (count v) 0) ... (peek v))` — the guard ADR 0032 made spellable.

`[:option T]` was not taken. It would make `peek` the only collection head
that returns one, `(peek (pop v))` would stop composing, and it was measured
on 2026-09-03 that `(option-none)` on an `if` arm makes `amu compile --target
wasm32-browser` refuse the whole project with `unsupported typed Wasm
expression`, exit 70 — measured against both the pinned frontend and this one,
so it is the backend and not this change. A `(peek v not-found)` arity is the
cheap widening if a caller ever wants one; `vector-get` is already the
primitive for it, and it is deliberately not added without one asking.

## Reservation

`peek`, `pop`, `keys` and `vals` are now RESERVED, for the reason `count` and
`conj` are: the rewrite dispatches on the head name before signatures are
consulted, so before this a `(defn peek ...)` was ACCEPTED and its calls would
have been rewritten out from under it silently. ADR 0032's assertion that all
six of `peek`/`pop`/`keys`/`vals`/`seq`/`last` must remain definable is turned
around for the four that gained a lowering and left standing for `seq` and
`last`, which no authority claims and nothing implements.

## What this does NOT reach

The typed-Wasm backend lives in `kotoba-lang/kotoba-wasm` and its host in
amu's `runtime/browser-host.mjs`; both are outside this change. Measured
2026-09-03 through `amu compile --target wasm32-browser --jvm-free` with this
frontend on the classpath:

    (peek [7 8 9])                             compiles; browser-host main() = 9n
    (count (typed-list-new [:list :i64] 7 8))  compiles; browser-host main() = 2n
    (count (pop [7 8 9]))                      unsupported typed Wasm expression
    (nth (keys ...) 1) / (nth (vals ...) 1)    typed Wasm operation is not qualified
    (nth (typed-list-new [:list :i64] 7 8) 1)  typed Wasm operation is not qualified

`pop` needs a `kotoba:typed/vector-take` intrinsic in kotoba-wasm and its
implementation in `browser-host.mjs`, next to the `vector-drop` that is
already in both. `keys`, `vals` and list `nth` need more than an intrinsic:
there is no `[:list T]` value kind in that host at all. The language
authority's per-operation records are written per backend against these
measurements rather than restored flat.
