# prolly-tree

`kotoba-lang/prolly-tree` is the shared CLJC home for a content-addressed
probabilistic B-tree (Prolly Tree) over CID-addressed dag-cbor blocks — the
IPLD index structure that backed `kotoba`'s 4-index Datalog Arrangement
(EAVT/AEVT/AVET/VAET) before `kotoba-lang/kotoba` deleted its Rust workspace
(`604896171b`, 2026-07-01) with no CLJC replacement. See
`90-docs/adr/2607010930-clj-wgsl-migration.md` Phase 6.

Chunk boundaries are probabilistic (~1/256 average chunk size, matching the
deleted Rust `BOUNDARY_MASK=0xFF`). **Internal-level boundaries are keyed on
the child's CID, never on the child's max-key** — keying on max-key
re-triggers the same boundary decision at every level for the same key,
which is an infinite-recursion bug the original Rust implementation hit and
fixed.

Storage is injected, not owned: `put!`/`get-fn` ports are passed in by the
caller (in-memory atom, IndexedDB, HTTP `block.get`, whatever). This
namespace does no I/O itself.

Child references in internal nodes are **real IPLD links** — CBOR tag 42
over the binary CID, via [`kotoba-lang/ipld`](https://github.com/kotoba-lang/ipld)
— so a generic DAG-CBOR/IPFS tool can walk the tree with no prolly-specific
schema knowledge (`ipld.core/links` suffices). This replaced the first
landing's plain-CID-string encoding (its documented honesty note): every
node's bytes, and therefore every CID, changed — a clean break; nothing in
production consumed the old format. Boundary math is unchanged (still keyed
on the child's CID string), so tree shape is identical.

## Use

```clojure
(require '[prolly-tree.core :as pt])

(def store (atom {}))
(def put!   (fn [cid bytes] (swap! store assoc cid bytes)))
(def get-fn (fn [cid] (get @store cid)))

(def root (pt/build-tree put! (sort-by first [["a" 1] ["b" 2] ["c" 3]])))
(pt/lookup get-fn root "b")                  ;=> 2
(pt/scan-prefix get-fn root "a")              ;=> [["a" 1]]
(pt/scan-range get-fn root "a" "c")           ;=> [["a" 1] ["b" 2]]  ; [lo, hi)
```

Structural replication can transfer only target blocks that are not proven
shared with a base root:

```clojure
(require '[prolly-tree.diff :as diff])

(def blocks
  (diff/sync-blocks get-fn old-root new-root
                    {:max-blocks 1024 :max-bytes 16777216 :max-reads 2048}))
;; Root-first, CID-verified blocks. Apply them to a store that already holds
;; old-root and new-root becomes completely readable.
```

Equal-CID subtrees cost no reads and no transfer. All comparison reads and
outbound block/byte counts are independently bounded and fail closed.

## Diffing one window

`diff` answers "what changed anywhere". `range-diff` answers "what changed
between these two keys", and it is not the first with a filter on it —
skipping a subtree whose key span cannot reach the window is a second,
independent pruning, and it fires on subtrees that *did* change.

```clojure
(diff/range-diff* get-fn old-root new-root "repo/01000" "repo/01010")
;; {:added [] :removed [] :changed [["repo/01000" "pin-1000" "pin-NEW-1000"]]
;;  :blocks-read 5 :pruned {:by-cid 0 :by-range 26}}
```

Measured 2026-08-17 on a 4,000-key tree with 200 keys changed, spread so that
every leaf is dirty: `diff` reads **40 blocks and returns 200 changes**
whatever you actually wanted. A caller needing a ten-key window read all 40
and discarded 199 answers. `range-diff` reads **5**.

That 5 is printed by the call above, not reasoned about. The reasoned figure
was 4 — a root pair and the one leaf pair holding those keys — and it is
wrong, because changing 200 values changes leaf CIDs, which changes the
content-defined boundary decisions above them, so the two trees do not have
the same fanout and their children do not align one for one. `:by-range` is
26 rather than the 32 that symmetric trees would give, for the same reason.

`nil` is an open end, so `(range-diff* g a b nil nil)` is `diff*`. The suite
checks exactly that against 60 pseudo-random windows, because this is a
function that fails by *dropping* keys and a smaller answer contains nothing
that says it should have been bigger.

**`:pruned` counts the two skips apart**, and that separation is the test that
matters: an implementation with the range skip removed is still correct, still
passes every assertion about what it returned, and on a tree where most
subtrees differ still looks fast. Only `:by-range` can tell you the window did
any work.

One thing worth knowing about the shape of these trees, because it bounds what
the saving can be: internal boundaries are hashed on the child CID at the same
~1/256 rate, so the tree stays very flat. Measured on this implementation —
**1,000 keys is a single leaf; 4,000 keys is 17 leaves under one internal
node; 20,000 keys is 92 leaves, still one internal level.** A window therefore
costs about two blocks per side, and the saving is in the leaves not read
rather than in a shortened descent.

## IPLD ADL view

The physical leaf/internal block graph is now exposed as an IPLD Advanced Data
Layout rather than only through Prolly-specific functions:

```clojure
(require '[prolly-tree.adl :as adl]
         '[ipld.data-model :as dm]
         '[ipld.selector :as selector])

(def m (adl/view get-fn root))
(dm/kind m)                         ;=> :map
(dm/lookup m "b")                   ;=> 2
(selector/select m {:selector :explore-fields
                    :fields {"b" {:selector :matcher}}})
;;=> [{:path ["b"], :value 2}]
```

Consumers see one ordinary Data Model Map while `adl/substrate` preserves the
physical root CID. `prolly-tree.schema/node-schema` validates every decoded
substrate block as the expected leaf/internal discriminated union before tree
logic interprets it. This is a runtime schema algebra, not a full IPLD Schema
DSL parser.

## Proving one key to someone who has only the root

```clojure
(def proof (pt/inclusion-proof get-fn root "b"))  ; the blocks along root->leaf
(pt/verify root "b" proof)                        ;=> {:value 2}
(pt/verify root "b" (rest proof))                 ;=> nil
```

`verify` does no I/O — the caller supplies the blocks. That is the point: a
party holding only `root` can check the claim without the tree.

**A proof is the path, not a sibling list.** A node's CID is the CID of the
whole node's DAG-CBOR, and an internal node carries every child's link, so
recomputing a parent's CID needs the parent's entire child list — not one
sibling hash. Ethereum's MPT proofs have the same shape for the same reason.
The cost is worth knowing before you budget for it: a proof carries O(height)
blocks and a block holds a whole chunk (~256 entries), so it is kilobytes
where a binary sibling path would be hundreds of bytes. If proof size is the
binding constraint, commit to a structure built *for* proving; this one is the
database's own index.

`root-cid` and `k` are arguments to `verify` and are never read out of the
proof — a verifier that takes the root from the thing it is checking verifies
nothing.

**Absence is not provable here.** Descending with an absent key does land in
the leaf that would hold it, but that argument needs the tree to be
well-formed (keys sorted, every max-key maximal), and one root→leaf path
cannot establish that. Inclusion needs no such assumption: the verifier sees
the pair inside a block it hashed itself. `inclusion-proof` returning nil
means "no proof to hand out", not "absent".

## Proving one window to someone who has only the root

```clojure
;; a prover records the blocks its own scan read -- that IS the proof
(def touched (atom {}))
(def recording (fn [cid] (let [b (get-fn cid)] (swap! touched assoc cid b) b)))

(def answer (pt/scan-range recording root "key-0100" "key-0400"))

(pt/verify-range root "key-0100" "key-0400" (vals @touched))
;;=> {:entries [...] :blocks 3 :bytes 90211}
;;   (:entries) = answer
```

`verify-range` does no I/O and takes `root-cid`, `lo` and `hi` from its caller,
like `verify`. It takes no CIDs at all: the archive is indexed by re-hashing
every block, so a substituted block cannot be a lie about which CID it sits
under — it decomposes into an omission and a surplus, and both are refused.

**What it proves is narrower than it first looks, and the difference is the
whole point.**

| claim | provable from these blocks? |
|---|---|
| the answer equals what `scan-range` returns for this root | **yes**, and at zero extra cost |
| the answer is every fact in `[lo, hi)` | **no**, and no quantity of blocks from this tree can make it so |

The first holds because an internal node carries **every** child's
`[max-key, link]` inside the bytes its own CID names. A verifier holding only
the root can therefore recompute, at every level, exactly which children the
pruning rule keeps, and demand each one — so a prover cannot answer with fewer
blocks than it read, or with different ones.

Measured over 120 pseudo-random and boundary-exact windows on a 4,000-key
tree: `scan-range` touched **873 blocks / 2,547,074 bytes** on the JVM, and
`verify-range` needed **exactly the same blocks and the same bytes — zero
extra**. Under ClojureScript the same suite reports 852 / 2,458,423, and the
difference is not a discrepancy: the shared pseudo-random helper multiplies
past 2^53, so cljs doubles and JVM longs part company at the first step and the
two runtimes sample different windows. Two independent samples, both zero
extra. That is block bytes; a CARv1 carrying them adds a header, and per block
a varint length and the binary CID, which is the container's cost and not the
proof's.

Also measured, on a hand-built tree whose LAST child's max-key is understated:
`scan-range` and `verify-range` agree on **0 rows**, while `diff/range-diff`,
walking the same root under the conservative rule, finds **313**.

The second fails because pruning turns on a `max-key`, and a `max-key` is the
**prover's claim** about a subtree. `an-understated-max-key-hides-a-key-and-the-
proof-is-still-accepted` builds a tree `build-tree` cannot produce, where one
max-key is understated and the subtree behind it really does hold every key in
the window. The prover prunes there; an honest verifier prunes in exactly the
same place, because a verifier that pruned anywhere else would refuse honest
proofs; and the empty answer verifies. That acceptance is asserted on purpose
and is not a defect to fix in the verifier — closing it needs a different
commitment (max-keys derived from, or signed by, something the prover does not
choose), not a stricter check.

Being conservative instead does not help, and the suite says so rather than
leaving it to be assumed: `prolly-tree.diff` already prunes the last child on
the span's `+infinity` rather than on its claimed max-key, so on that same
doctored tree `range-diff` finds the hidden rows and `scan-range` does not. A
verifier that borrowed that rule would demand a block the prover never read,
and every honest proof would be refused.

So: **`verify-range` is an equivalence proof against a named function, not a
completeness proof against the world.** Absence is still not provable here, for
the reason `inclusion-proof` already gives.

## Scope

Portability is real now, not aspirational: the whole dependency chain
(`multiformats` → `dag-cbor` → `ipld` → this repo) runs on both the JVM and
real ClojureScript (shadow-cljs node-test in CI), producing byte-identical
CIDs on both platforms.

Key-range-pruned scans and structural diff/sync are implemented. Merge policy
and garbage collection of unreferenced nodes remain host/database concerns.

## Test

```bash
kbb -M:test                     # JVM
npm install && npm run test:cljs    # real ClojureScript (shadow-cljs node-test)
```

## License

MIT
