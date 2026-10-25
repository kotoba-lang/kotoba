(ns prolly-tree.ordered-map
  "This substrate's OrderedMap declaration, and an adapter built from it.

  `prolly-tree.adl` already gives an IPLD Map view, which is the interface
  schema and selector code want: string keys, lookup, entries. It is
  deliberately not an ordered one -- a standard IPLD Map has no range API --
  so a caller wanting `[lower, upper)` over this tree has been reaching past
  the ADL to `core/scan-range` and getting this substrate's bound semantics
  along with it.

  That is fine until a second substrate answers the same question. The two
  ordered range APIs in this workspace disagree about the row whose key equals
  the upper bound: this one excludes it, `kotobase.projection/decode-range`
  includes it. Neither is wrong; they are different contracts, and the bug is
  only ever in the layer that treats them as one.

  So this namespace declares what this tree actually does, in the vocabulary
  `kotobase.storage.ordered-map` defines, and lets that contract adapt it. The
  declaration is the deliverable -- the adapter is four lines around
  `scan-range`."
  (:require [kotobase.storage.ordered-map :as om]
            [prolly-tree.core :as tree]))

(def profile
  "What a Prolly tree does, stated rather than assumed.

  `:comparator :lexicographic-utf8` -- `core/scan-range` prunes children and
  filters leaves with `compare` on the key string. Whatever encoded a
  composite key into that string owns whether its order survived; this tree
  orders the string it was given, and `scan-range`'s own docstring says so:
  HMAC-blinded keys do not compare as the query range and stay on
  prefix-then-decrypt-then-filter. Such a caller declares `:opaque-unordered`
  and the contract refuses ranges over it rather than answering wrongly.

  `:bounds :half-open` -- `[lo, hi)`, per `core/in-key-range?`.

  `:snapshot :root-cid` -- there is no epoch. A root IS the snapshot: reads
  take a `root-cid`, and a write returns a new root rather than mutating one,
  so a read of one root cannot see another's writes.

  `:duplicates :unique-key` -- a key appears once in a leaf's entries. There
  are no versions to choose between.

  `:tombstones :absent` -- `core/delete` produces a tree without the key. No
  row survives to suppress anything, which is exactly what a Merkle-LSM
  tombstone does do, and why the contract makes the two declare it."
  {:comparator :lexicographic-utf8
   :bounds :half-open
   :snapshot :root-cid
   :duplicates :unique-key
   :tombstones :absent})

(defn adapter
  "An OrderedMap adapter over `root-cid`, for `kotobase.storage.ordered-map`.

  `comparator` overrides the declared one, for a caller whose keys reached
  this tree through an encoding that does not preserve their order -- passing
  `:opaque-unordered` is how such a caller says so, and the contract then
  refuses ranges instead of answering with the wrong rows.

  A nil root is the empty tree, matching `scan-range`, and it agrees with
  every other empty substrate -- which is why the oracle reports that
  agreement as vacuous."
  ([get-fn root-cid] (adapter get-fn root-cid nil))
  ([get-fn root-cid comparator]
   {:profile (cond-> profile comparator (assoc :comparator comparator))
    :scan (fn [lower upper]
            (vec (or (tree/scan-range get-fn root-cid lower upper) [])))}))

(defn scan
  "Read a canonical half-open `om/range` from `root-cid`.

  Identical to `core/scan-range` for this substrate, because this substrate is
  already half-open. That is the point: the adaptation costs nothing where the
  contract and the substrate agree, and is not silently skipped where they do
  not."
  [get-fn root-cid rng]
  (om/scan (adapter get-fn root-cid) rng))
