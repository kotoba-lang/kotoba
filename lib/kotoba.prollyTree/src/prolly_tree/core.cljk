(ns prolly-tree.core
  "Content-addressed probabilistic B-tree (Prolly Tree) over CID-addressed
  dag-cbor blocks.

  Ports for storage are injected -- `put!` (cid, bytes -> ignored, called
  once per node built) and `get-fn` (cid -> bytes) are passed in by the
  caller. This namespace performs no I/O itself.

  Chunk boundaries are probabilistic (~1/256 average chunk size), matching
  the deleted kotoba-store Rust implementation. LEAF-level boundaries are
  keyed on the entry's key; INTERNAL-level boundaries are keyed on the
  CHILD's CID, never on the child's max-key -- keying an internal boundary
  on max-key re-triggers the same boundary decision at every level for the
  same key, which is an infinite-recursion bug the original Rust
  implementation hit and fixed.

  Update: `multiformats.core/sha256` and `cbor.core/encode` have grown real
  `:cljs` branches (SHA-256 via org-nist-sha2 through io-multiformats, portable CBOR byte buffers).
  `utf8-bytes` below used `.getBytes` unconditionally despite the `.cljc`
  extension -- a genuine gap in this namespace's own portability, not just
  its dependencies' -- now split per-platform. Verified end to end under
  ClojureScript (nbb), not just reasoned about: `build-tree`/`lookup` run
  and byte-identically match the :clj path for the same input.

  Update 2 (tag-42): child references in internal nodes are now REAL IPLD
  links -- CBOR tag 42 over the binary CID, via `kotoba-lang/ipld` -- not
  plain CID strings. This closes the honesty note the first landing
  carried (`cbor.core` had no tag support then; it does now). A generic
  DAG-CBOR/IPFS tool can walk the tree. NOTE: this changes every node's
  bytes and therefore every CID -- a clean break, nothing in production
  consumed the old format (see superproject ADR). Boundary math is
  unchanged (still keyed on the child's CID string), so tree SHAPE is
  identical; only the on-block encoding moved."
  (:require [kotoba.lang.text :as str]
            [multiformats.core :as mf]
            [ipld.core :as ipld]
            [prolly-tree.schema :as schema]))

(def boundary-bits
  "Chunk boundary fires when the low `boundary-bits` bits of the determinant
  hash are all zero. 8 bits == ~1/256 average chunk size (BOUNDARY_MASK=0xFF
  in the deleted Rust implementation)."
  8)

(defn- utf8-bytes [s]
  #?(:clj (.getBytes ^String s "UTF-8")
     :cljs (.encode (js/TextEncoder.) s)))

(defn- boundary?
  "True ~1/(2^boundary-bits) of the time: the last byte of
  sha256(str(x)-as-utf8) is all-zero under `boundary-bits`."
  [x]
  (let [h (mf/sha256 (utf8-bytes (str x)))
        b (bit-and 0xff (aget h (dec (alength h))))]
    (zero? (bit-and b (dec (bit-shift-left 1 boundary-bits))))))

(defn- put-node!
  "DAG-CBOR-encode `node` (links become tag 42), CID it, call
  `(put! cid bytes)`, return the cid string."
  [put! node]
  (ipld/put-node! put! node))

(defn- chunk-by
  "Split `items` into chunks; a chunk ends right after any item for which
  `boundary-fn` returns true, or at the end of `items`. Never splits an
  empty input."
  [boundary-fn items]
  (if (empty? items)
    []
    (loop [remaining items chunk [] out []]
      (if (empty? remaining)
        (if (seq chunk) (conj out chunk) out)
        (let [item (first remaining)
              chunk' (conj chunk item)]
          (if (boundary-fn item)
            (recur (rest remaining) [] (conj out chunk'))
            (recur (rest remaining) chunk' out)))))))

(defn- build-leaf-level
  "`sorted-entries`: seq of `[k v]`, already sorted by k. Returns a seq of
  `[max-key cid]` summaries after put!-ing each leaf node."
  [put! sorted-entries]
  (mapv (fn [chunk]
          (let [node {"kind" "leaf" "entries" (mapv vec chunk)}
                cid (put-node! put! node)
                max-key (first (last chunk))]
            [max-key cid]))
        (chunk-by (fn [[k _]] (boundary? k)) sorted-entries)))

(defn- build-internal-level
  "`child-summaries`: seq of `[max-key cid]`, already sorted by max-key.
  Boundary is determined by the CHILD CID (see namespace docstring), not by
  max-key. On-block, each child reference is a real IPLD link (tag 42);
  in-memory summaries stay plain CID strings so the boundary math is
  encoding-independent."
  [put! child-summaries]
  (mapv (fn [chunk]
          (let [node {"kind" "internal"
                      "children" (mapv (fn [[max-key cid]]
                                         [max-key (ipld/link cid)])
                                       chunk)}
                cid (put-node! put! node)
                max-key (first (last chunk))]
            [max-key cid]))
        (chunk-by (fn [[_ cid]] (boundary? cid)) child-summaries)))

(defn build-tree
  "Build a Prolly Tree from `sorted-entries` (seq of `[k v]`, sorted by `k`
  ascending, `k` comparable via `compare`), calling `(put! cid bytes)` for
  every node created. Returns the root CID string, or nil for empty input."
  [put! sorted-entries]
  (when (seq sorted-entries)
    (loop [level (build-leaf-level put! sorted-entries)]
      (if (= 1 (count level))
        (second (first level))
        (recur (build-internal-level put! level))))))

(defn- verified-node [expected-cid bytes]
  (let [actual (ipld/cid bytes)]
    (when-not (= expected-cid actual)
      (throw (ex-info "prolly-tree: block CID mismatch"
                      {:type :ipld/cid-mismatch :expected-cid expected-cid
                       :actual-cid actual})))
    (schema/unify-node (ipld/decode bytes))))

(defn- get-node [get-fn cid]
  (verified-node cid (get-fn cid)))

(defn- child-cid
  "A decoded internal-node child entry is `[max-key <tag-42 link>]`; return
  the link's CID string."
  [[_ link]]
  (ipld/link-cid link))

(defn- descend-cid
  "The child CID that owns `k`, given a decoded internal node's `children`:
  the first whose max-key >= k, else the last.

  Kept in one place because `lookup`, `inclusion-proof` and `verify` must
  descend identically. A verifier that follows a different rule from the
  prover accepts proofs for the wrong leaf -- and `child-index` above already
  states this same rule for the `[max-key cid-string]` summary shape, so
  there were two statements of it before this one and now there are two
  again, one per shape, rather than four."
  [children k]
  (or (some (fn [entry]
              (when (<= (compare k (first entry)) 0)
                (child-cid entry)))
            children)
      (child-cid (last children))))

;; ---------------------------------------------------------------------------
;; key spans -- what a subtree can possibly contain
;;
;; `descend-cid` above sends a key to "the first child whose max-key >= k, else
;; the LAST". So child i holds keys in (max-key[i-1], max-key[i]], and the last
;; child's upper bound is +infinity rather than its own max-key: a key larger
;; than every max-key still descends into it. Getting that one wrong prunes a
;; subtree that can hold wanted keys, so it is stated once, here, and every
;; range walk in this library reads it from this function.
;;
;; No tree this library builds can exhibit that last case: `insert` and
;; `insert-many` are byte-identical to `build-tree`, so the last max-key is
;; always the tree's maximum key. The +infinity is defence against a tree from
;; a writer that is not this one, and `prolly-tree.range-diff-test` tests it
;; against a hand-built node with an understated max-key -- because a test that
;; used `build-tree` for it would pass with the bound removed, which is exactly
;; what the first draft of that test did.
;;
;; This lived in `prolly-tree.diff` until `verify-range` needed it. A verifier
;; that restated the span arithmetic would be a fourth copy of one sentence,
;; and the copy that drifts is the one that accepts the wrong answer.
;; ---------------------------------------------------------------------------

(defn child-spans
  "`[[lower upper cid] ...]` for an internal node, in key order. `lower` is
  EXCLUSIVE and nil means -infinity; `upper` is INCLUSIVE and nil means
  +infinity, which only the last child gets."
  [node]
  (let [cs (get node "children")
        last-i (dec (count cs))]
    (into []
          (map-indexed (fn [i entry]
                         [(when (pos? i) (first (nth cs (dec i))))
                          (when (< i last-i) (first entry))
                          (child-cid entry)]))
          cs)))

(defn lookup
  "Point lookup of `k` under `root-cid`, fetching nodes via `(get-fn cid) ->
  bytes`. Returns the value, or nil if `k` is absent or `root-cid` is nil
  (empty tree)."
  [get-fn root-cid k]
  (when root-cid
    (loop [cid root-cid]
      (let [node (get-node get-fn cid)]
        (case (get node "kind")
          "leaf" (some (fn [[ek ev]] (when (= ek k) ev)) (get node "entries"))
          "internal" (recur (descend-cid (get node "children") k)))))))

(defn- prefix-past?
  [k prefix]
  (and (pos? (compare k prefix)) (not (str/starts-with? k prefix))))

(defn- scan-prefix-walk
  "Recursive prefix walk. `left` is a volatile of remaining matches, or
  nil when unlimited. Stops descending once the budget is spent."
  [get-fn cid prefix left]
  (when (or (nil? left) (pos? @left))
    (let [node (get-node get-fn cid)]
      (case (get node "kind")
        "leaf"
        (let [ms (filterv (fn [[k _]] (str/starts-with? k prefix))
                          (get node "entries"))]
          (if (nil? left)
            ms
            (let [got (vec (take @left ms))]
              (vswap! left - (count got))
              got)))
        "internal"
        (loop [children (get node "children")
               prev-max nil
               out (transient [])]
          (cond
            (empty? children) (persistent! out)
            (and left (not (pos? @left))) (persistent! out)
            :else
            (let [entry (first children)
                  mk (first entry)]
              (cond
                (and (some? prev-max) (prefix-past? prev-max prefix))
                (persistent! out)
                (neg? (compare mk prefix))
                (recur (rest children) mk out)
                :else
                (recur (rest children) mk
                       (reduce conj! out (or (scan-prefix-walk get-fn (child-cid entry) prefix left) [])))))))))))

(defn scan-prefix
  "All `[k v]` pairs whose string key starts with `prefix`, fetching nodes via
  `(get-fn cid) -> bytes`. Key-range pruned: since keys are sorted and an
  internal node's children are `[max-key cid]` in order, a prefix-matching key
  can only live in a child whose `max-key >= prefix` AND whose predecessor's
  `max-key` has not already passed the prefix range. So we skip children entirely
  below the prefix and stop once past it — descending into O(path) blocks for a
  keyed read instead of the whole tree (ADR-2607022330 addendum 3 / #16). With an
  empty `prefix` this is a full ordered scan, unchanged.

  Optional `limit` (positive int) stops after that many matching pairs.
  `nil` is unlimited. `0` or negative is empty without walking. A caller
  that takes `limit` after a full scan still paid O(tree); this is the
  bound that makes `datoms` `:limit 1` O(path), not O(database)."
  ([get-fn root-cid prefix]
   (scan-prefix get-fn root-cid prefix nil))
  ([get-fn root-cid prefix limit]
   (when root-cid
     (if (and (some? limit) (not (pos? limit)))
       []
       (vec (or (scan-prefix-walk get-fn root-cid prefix
                                  (when (some? limit) (volatile! limit)))
                []))))))

(defn- in-key-range?
  "True when `k` is in `[lo, hi)`. A nil bound is unbounded."
  [k lo hi]
  (and (or (nil? lo) (not (neg? (compare k lo))))
       (or (nil? hi) (neg? (compare k hi)))))

(defn- range-spans
  "The child spans a range walk over `[lo, hi)` descends into, from
  `child-spans`.

  One function because `scan-range` (the prover) and `verify-range` (the
  verifier) must prune IDENTICALLY. A verifier that follows a different rule
  from the prover refuses honest answers, or accepts short ones -- the same
  argument `descend-cid` makes for point lookups, one dimension up.

  A child with claimed max-key `mk` owns `(prev-max, mk]`. Skip it when
  `mk < lo`. Stop when `prev-max >= hi` -- every remaining key is
  `> prev-max`, so outside an exclusive hi. This is the value-range analogue
  of `scan-prefix`'s prefix prune: the tree is cut in the middle, not scanned
  then filtered.

  Two things here differ from `prolly-tree.diff`'s `span-intersects?`, which
  reads the same spans, and both differences are deliberate:

  1. This STOPS at the first child whose `lower` has reached `hi` instead of
     filtering. `lower` is non-decreasing across a node's children, so on any
     tree with sorted max-keys the two agree; on one without, stopping is what
     `scan-range` does and therefore what a verifier must reproduce.

  2. The `lo` test uses the child's CLAIMED max-key, not the span's `upper`.
     They are the same except for the LAST child, where `upper` is nil for
     +infinity. `diff` honours that +infinity and keeps a last child whose
     max-key is understated; `scan-range` does not, and skips it. So the two
     namespaces answer differently on a tree no `build-tree` can produce --
     `diff` conservatively, `scan-range` by trusting the claim. That trust is
     exactly what `verify-range` cannot verify away, and
     `the-last-childs-claim-is-trusted-too-and-diff-disagrees` is the test
     that says so -- it is also the only test the difference in (2) can
     redden, because `upper` and the claimed max-key are the same value for
     every child except the last."
  [node lo hi]
  (let [claimed (mapv first (get node "children"))]
    (loop [spans (child-spans node), i 0, acc []]
      (if-let [[lower _ _ :as span] (first spans)]
        (cond
          (and (some? lower) (some? hi) (not (neg? (compare lower hi))))
          acc
          (and (some? lo) (neg? (compare (nth claimed i) lo)))
          (recur (rest spans) (inc i) acc)
          :else
          (recur (rest spans) (inc i) (conj acc span)))
        acc))))

(defn scan-range
  "All `[k v]` pairs whose key is in `[lo, hi)`, fetching nodes via
  `(get-fn cid) -> bytes`. `lo` inclusive, `hi` exclusive; a nil bound is
  unbounded. Key-range pruned the same way `scan-prefix` is: children whose
  whole span sits below `lo` are skipped, and the walk stops once past `hi`.

  This is the primitive `index-range` and AVET value intervals need.
  `scan-prefix` cannot express `[\"attr|n0000000010\" \"attr|n0000000050\")`
  without reading every key under `attr|` and filtering — which is exactly
  the full-attribute scan this exists to avoid. Keys must already compare
  as the query range (order-preserving encoding). HMAC-blinded leaf keys
  do not; those stay on prefix + decrypt + filter.

  Empty tree / nil root → nil (same as `scan-prefix`)."
  [get-fn root-cid lo hi]
  (when root-cid
    (letfn [(walk [cid]
              (let [node (get-node get-fn cid)]
                (case (get node "kind")
                  "leaf" (filterv (fn [[k _]] (in-key-range? k lo hi))
                                  (get node "entries"))
                  "internal"
                  (into [] (mapcat (fn [[_ _ cid]] (walk cid)))
                        (range-spans node lo hi)))))]
      (walk root-cid))))

#?(:cljs
   (def ^:private scan-prefix-async-batch-size
     "Max in-flight child fetches at once for `scan-prefix-async`, same
     rationale/value as `kotobase-peer.core`'s `pmap-async-batch-size`
     (duplicated here rather than shared -- prolly-tree has no dependency on
     kotobase-peer, and this codebase's own precedent is per-repo test/
     concurrency helper duplication over a forced shared dependency in the
     wrong direction). 24 is a starting point, not load-tested against
     Workers' exact per-plan subrequest ceiling."
     24))

#?(:cljs
   (defn- pmap-async
     "cljs only: map `f` (returns a `js/Promise`) over `coll` in bounded
     batches of `scan-prefix-async-batch-size` concurrent calls, return one
     `js/Promise` of the resolved results, order-preserved. See that var's
     docstring for why unbounded concurrency is unsafe."
     [f coll]
     (let [batches (partition-all scan-prefix-async-batch-size coll)]
       (reduce (fn [acc-promise batch]
                 (.then acc-promise
                        (fn [acc]
                          (-> (js/Promise.all (into-array (map f batch)))
                              (.then (fn [batch-results] (into acc batch-results)))))))
               (js/Promise.resolve [])
               batches))))

#?(:cljs
   (defn- scan-prefix-async-full
     "Async, concurrency-batched counterpart to `scan-prefix`, for a `get-fn`
     that returns a `js/Promise<bytes>` (fetches over the network, e.g. R2)
     rather than the synchronous get-fn/block-miss-trampoline contract
     `scan-prefix` assumes.

     `scan-prefix` over a trampoline like `kotobase.cljc-worker.r2/with-
     blocks` does exactly ONE new block discovery per call: `get-fn` throws
     synchronously on the first not-yet-cached CID, the trampoline catches
     it, fetches JUST THAT block, and re-runs `scan-prefix`'s ENTIRE
     recursive walk from `root-cid`. Only raw bytes are cached by the
     trampoline -- `get-node`'s `ipld/decode` is NOT memoized -- so a walk
     touching N distinct blocks costs O(N) SEQUENTIAL round trips (one
     discovered per retry, never batched) and, because every retry re-walks
     and re-decodes every already-fetched node from the root, O(N^2) total
     node decodes. For a mature tree (thousands of leaf blocks) this
     quadratic redundant-decode cost, not raw I/O latency, is a plausible
     dominant contributor to a cold hydrate exceeding a Worker's CPU budget
     (kotoba-lang/kotobase-peer's `hydrate-db`, gftdcojp/app-aozora#78 /
     ADR-2607120730).

     `scan-prefix-async` fetches each internal node's children CONCURRENTLY
     (bounded batch, `pmap-async`) instead of one miss at a time, and decodes
     each node exactly once (no retry-from-root) -- O(N) round trips
     (batched, not sequential) and O(N) decodes, not O(N^2). Same key-range
     pruning as `scan-prefix`; same `[k v]` pair shape.

     get-fn: `(get-fn cid) -> js/Promise<bytes>`. → `js/Promise<[[k v] ...]>`."
     [get-fn root-cid prefix]
     (if (nil? root-cid)
       (js/Promise.resolve [])
       (letfn [(past-prefix? [k]
                 (and (pos? (compare k prefix)) (not (str/starts-with? k prefix))))
               (children-to-walk [node]
                 (loop [children (get node "children"), prev-max nil, acc []]
                   (if (empty? children)
                     acc
                     (let [entry (first children)
                           mk (first entry)]
                       (cond
                         (and (some? prev-max) (past-prefix? prev-max)) acc
                         (neg? (compare mk prefix)) (recur (rest children) mk acc)
                         :else (recur (rest children) mk (conj acc entry)))))))
               (walk [cid]
                 (-> (get-fn cid)
                     (.then #(verified-node cid %))
                     (.then (fn [node]
                              (case (get node "kind")
                                "leaf" (js/Promise.resolve
                                        (filterv (fn [[k _]] (str/starts-with? k prefix))
                                                 (get node "entries")))
                                "internal"
                                (-> (pmap-async (fn [entry] (walk (child-cid entry)))
                                                (children-to-walk node))
                                    (.then (fn [results] (vec (apply concat results))))))))))]
         (walk root-cid)))))

#?(:cljs
   (defn- scan-prefix-async-limited
     [get-fn root-cid prefix limit]
     (cond
       (nil? root-cid) (js/Promise.resolve [])
       (not (pos? limit)) (js/Promise.resolve [])
       :else
       (let [left (volatile! limit)
             past-prefix? (fn [k]
                            (and (pos? (compare k prefix))
                                 (not (str/starts-with? k prefix))))
             take-matching (fn [entries]
                             (let [ms (filterv (fn [[k _]] (str/starts-with? k prefix)) entries)
                                   got (vec (take @left ms))]
                               (vswap! left - (count got))
                               got))
             children-to-walk (fn [node]
                                (loop [children (get node "children")
                                       prev-max nil
                                       acc []]
                                  (if (empty? children)
                                    acc
                                    (let [entry (first children)
                                          mk (first entry)]
                                      (cond
                                        (and (some? prev-max) (past-prefix? prev-max)) acc
                                        (neg? (compare mk prefix)) (recur (rest children) mk acc)
                                        :else (recur (rest children) mk (conj acc entry)))))))
             walk (fn walk [cid]
                    (if-not (pos? @left)
                      (js/Promise.resolve [])
                      (-> (get-fn cid)
                          (.then (fn [bytes] (verified-node cid bytes)))
                          (.then (fn [node]
                                   (if (= "leaf" (get node "kind"))
                                     (js/Promise.resolve (take-matching (get node "entries")))
                                     (reduce (fn [p entry]
                                               (.then p (fn [acc]
                                                          (if-not (pos? @left)
                                                            acc
                                                            (.then (walk (child-cid entry))
                                                                   (fn [more] (into acc more)))))))
                                             (js/Promise.resolve [])
                                             (children-to-walk node))))))))]
         (walk root-cid)))))

#?(:cljs
   (defn scan-prefix-async
     "Async counterpart to `scan-prefix`. Optional `limit` walks children
     left-to-right and stops; `nil` keeps the batched-concurrent full walk."
     ([get-fn root-cid prefix]
      (scan-prefix-async-full get-fn root-cid prefix))
     ([get-fn root-cid prefix limit]
      (if (nil? limit)
        (scan-prefix-async-full get-fn root-cid prefix)
        (scan-prefix-async-limited get-fn root-cid prefix limit)))))

#?(:cljs
   (defn scan-range-async
     "Async counterpart to `scan-range`. Same `[lo, hi)` contract, same
     child pruning, batched concurrent child fetches like `scan-prefix-async`.

     get-fn: `(get-fn cid) -> js/Promise<bytes>`. → `js/Promise<[[k v] ...]>`."
     [get-fn root-cid lo hi]
     (if (nil? root-cid)
       (js/Promise.resolve [])
       (letfn [(walk [cid]
                 (-> (get-fn cid)
                     (.then #(verified-node cid %))
                     (.then (fn [node]
                              (case (get node "kind")
                                "leaf" (js/Promise.resolve
                                        (filterv (fn [[k _]] (in-key-range? k lo hi))
                                                 (get node "entries")))
                                "internal"
                                (-> (pmap-async (fn [[_ _ cid]] (walk cid))
                                                (range-spans node lo hi))
                                    (.then (fn [results] (vec (apply concat results))))))))))]
         (walk root-cid)))))

;; ── Inclusion proof ─────────────────────────────────────────────────────────
;;
;; What a proof for this tree can be, and what it cannot.
;;
;; In a binary Merkle tree a proof is a sibling path: O(log n) hashes, and the
;; verifier recomputes the root by hashing pairs upward. That shape is not
;; available here, and the reason is structural rather than an omission. A
;; node's CID is the CID of the DAG-CBOR encoding of the WHOLE node, and an
;; internal node carries every child's link. To recompute a parent's CID you
;; therefore need the parent's entire child list, not one sibling hash.
;;
;; So a proof is the list of BLOCKS along the root->leaf path, and the verifier
;; re-derives each block's CID and checks that the descent for `k` selects the
;; next block in the list. This is the same shape Ethereum's MPT proofs take
;; -- the encoded nodes along the path, not sibling hashes -- and for the same
;; reason.
;;
;; The cost is worth stating rather than discovering: a proof carries O(height)
;; blocks and a block holds a whole chunk (~256 entries at the default
;; boundary), so a proof is kilobytes where a binary sibling path would be
;; hundreds of bytes. A commitment built FOR proving (one value per leaf) is
;; the right structure when proof size is the binding constraint; this one is
;; the database's own index, and proving against it is the thing that costs.
;;
;; NOT offered: absence proofs. Descending with an absent `k` does land in the
;; leaf that would hold it, but that argument is sound only if the tree is
;; well-formed -- keys sorted, every max-key actually maximal -- and a single
;; root->leaf path cannot establish well-formedness. Inclusion needs no such
;; assumption, because the verifier SEES the pair in a block it hashed itself.

(defn inclusion-proof
  "The blocks along the path from `root-cid` to the leaf holding `k`, root
  first, leaf last. Fetches via `(get-fn cid) -> bytes`.

  Returns nil when `k` is absent or `root-cid` is nil. A nil return does NOT
  prove absence (see the note above); it means there is no inclusion proof to
  hand out.

  The proof is EXACTLY the path -- no envelope carrying the root or the key --
  because `verify` must take both of those from its own caller. A verifier
  that reads the root it checks against out of the thing being checked
  verifies nothing."
  [get-fn root-cid k]
  (when root-cid
    (loop [cid root-cid, path []]
      (let [bytes (get-fn cid)
            node (verified-node cid bytes)
            path' (conj path bytes)]
        (case (get node "kind")
          "leaf" (when (some (fn [entry] (= (first entry) k))
                             (get node "entries"))
                   path')
          "internal" (recur (descend-cid (get node "children") k) path'))))))

(defn verify
  "Check that `proof` proves `k` is present under `root-cid`, and return
  `{:value v}` -- or nil if it proves nothing.

  `root-cid` and `k` come from the CALLER. Neither is read out of `proof`.

  The value is wrapped in a map because a stored value may legitimately be
  nil, and a bare nil return would make `absent` and `present, with value nil`
  indistinguishable -- exactly the confusion a verifier must not have.

  Every one of these is a failure, and each has a test: a block whose bytes do
  not hash to the CID the previous step demanded; an internal node whose
  descent for `k` does not select the next block; a leaf reached before the
  path ends, or a path that ends without reaching a leaf; a leaf that does not
  contain `k`. No I/O -- the caller supplies the blocks, which is the point."
  [root-cid k proof]
  (when (and root-cid (seq proof))
    (loop [expected root-cid, blocks (seq proof)]
      (let [node (try (verified-node expected (first blocks))
                      (catch #?(:clj Exception :cljs :default) _ nil))
            more (next blocks)]
        (when node
          (case (get node "kind")
            "leaf" (when (nil? more)
                     (some (fn [entry]
                             (when (= (first entry) k)
                               {:value (second entry)}))
                           (get node "entries")))
            "internal" (when (some? more)
                         (recur (descend-cid (get node "children") k) more))
            nil))))))

;; ── Range proof ─────────────────────────────────────────────────────────────
;;
;; What a range proof for this tree can be, and what it cannot -- and the gap
;; between the two is the whole point of stating it here.
;;
;; `verify` above proves ONE pair. The natural next question from a caller who
;; has only the root is "and is that ALL of them, between these two keys?", and
;; the honest answer splits in two:
;;
;;   PROVABLE, from the blocks and nothing else: "this is what `scan-range`
;;   returns for `[lo, hi)` under this root". An internal node carries EVERY
;;   child's [max-key, link] inside the bytes its own CID names, so a verifier
;;   holding the root can recompute, at every level, exactly which children the
;;   pruning rule keeps -- and then demand each one. It costs no extra bytes:
;;   the answer is a function of the blocks the prover already had to read.
;;
;;   NOT PROVABLE: "this is every fact in `[lo, hi)`". That claim needs the
;;   tree to be well-formed -- keys sorted end to end, every max-key actually
;;   maximal -- and no block contains that. It is the same wall the note above
;;   `inclusion-proof` hits for absence, and for the same reason: a max-key is
;;   the PROVER's claim about a subtree, so pruning on it is trusting the
;;   prover. A prover that understates one max-key hides every key above it in
;;   that subtree, the verifier prunes in exactly the same place, and the short
;;   answer verifies. `an-understated-max-key-hides-a-key-and-the-proof-is-
;;   still-accepted` asserts that acceptance on purpose. It is the boundary of
;;   what this can claim, not a bug to fix here -- fixing it needs a different
;;   commitment (max-keys signed by, or derived from, something the prover does
;;   not choose), not a different verifier.
;;
;; So: `verify-range` is an equivalence proof against a named function, not a
;; completeness proof against the world.

(defn- byte-count [bytes]
  #?(:clj (if (bytes? bytes) (alength ^bytes bytes) (count bytes))
     :cljs (if (vector? bytes) (count bytes) (.-length bytes))))

(defn- index-blocks
  "`{cid bytes}` for a range proof, keyed by RE-HASHING every block.

  No CID in the result came from the caller, which is why `verify-range` has
  no CID-mismatch refusal: a block whose bytes were changed does not become a
  different truth about the CID it was filed under, it becomes a block nobody
  asked for, and the block that was asked for is missing."
  [blocks]
  (persistent!
   (reduce (fn [acc bytes] (assoc! acc (ipld/cid bytes) bytes))
           (transient {}) blocks)))

(defn- in-span?
  "`lower` exclusive (nil = -infinity), `upper` inclusive (nil = +infinity) --
  the convention `child-spans` states."
  [k lower upper]
  (and (or (nil? lower) (pos? (compare k lower)))
       (or (nil? upper) (not (pos? (compare k upper))))))

(defn verify-range
  "Check that `blocks` prove the answer `scan-range` gives for `[lo, hi)` under
  `root-cid`, and return

      {:entries [[k v] ...] :blocks n :bytes n}

  -- or throw a typed refusal. Returns nil for a nil `root-cid`, so
  `(:entries ...)` is nil there, matching `scan-range` on the empty tree.

  `root-cid`, `lo` and `hi` come from the CALLER. None of them is read out of
  `blocks`, and neither is any CID: `index-blocks` re-hashes. A verifier that
  reads what it is checking against out of the thing being checked verifies
  nothing, which is the same reason `verify` takes `root-cid` and `k`.

  No I/O. `:blocks` and `:bytes` are what the proof actually needed, reported
  rather than left to be assumed -- a range proof whose cost nobody counted is
  a range proof nobody knows the price of, and `prolly-tree.diff` already makes
  that argument for its block counter.

  WHAT IT PROVES: the entries are exactly `(scan-range get-fn root-cid lo hi)`.
  WHAT IT DOES NOT: that those are every fact in the range. See the note above.

  Each refusal is typed and named apart, and each has a test:

  | `:prolly-tree/block-missing`        | the proof omits a block the pruning rule keeps -- also how a tampered or substituted block arrives, since the index is built by hashing |
  | `:prolly-tree/unexpected-block`     | the proof carries a block the pruning rule never asks for |
  | `:prolly-tree/entry-outside-span`   | a leaf holds a key outside the `(lower, upper]` its own parent claims for it |

  The third is the only well-formedness this can check, and it is worth being
  precise about its reach: it is checked against the IMMEDIATE parent's claim,
  and only for blocks the proof actually contains. A subtree that the rule
  pruned is never read, so a lie about ITS max-key is out of reach here by
  construction -- which is exactly the C2 boundary above. Re-checking an
  internal node's max-keys against its own parent's would add code that only
  compares one prover claim to another."
  [root-cid lo hi blocks]
  (if (nil? root-cid)
    (when (seq blocks)
      (throw (ex-info "prolly-tree: range proof for the empty tree carries blocks"
                      {:type :prolly-tree/unexpected-block
                       :cids (vec (keys (index-blocks blocks)))})))
    (let [index (index-blocks blocks)
          visited (volatile! #{})
          demand (fn [cid]
                   (or (get index cid)
                       (throw (ex-info "prolly-tree: range proof omits a block the pruning rule keeps"
                                       {:type :prolly-tree/block-missing :cid cid}))))]
      (letfn [(walk [cid lower upper]
                (let [bytes (demand cid)
                      node (schema/unify-node (ipld/decode bytes))]
                  (vswap! visited conj cid)
                  (case (get node "kind")
                    "leaf"
                    (let [entries (mapv vec (get node "entries"))]
                      (doseq [[k _] entries]
                        (when-not (in-span? k lower upper)
                          (throw (ex-info "prolly-tree: leaf holds a key outside the span its parent claims"
                                          {:type :prolly-tree/entry-outside-span
                                           :cid cid :key k :lower lower :upper upper}))))
                      (filterv (fn [[k _]] (in-key-range? k lo hi)) entries))
                    "internal"
                    (into [] (mapcat (fn [[l u c]] (walk c l u)))
                          (range-spans node lo hi)))))]
        (let [entries (walk root-cid nil nil)
              surplus (remove @visited (keys index))]
          (when (seq surplus)
            (throw (ex-info "prolly-tree: range proof carries a block the pruning rule never asks for"
                            {:type :prolly-tree/unexpected-block :cids (vec surplus)})))
          {:entries entries
           :blocks (count @visited)
           :bytes (reduce + 0 (map (comp byte-count index) @visited))})))))

;; ── Incremental insert ──────────────────────────────────────────────────────
;;
;; Why this can exist at all, and why it must be byte-identical to a rebuild.
;;
;; Chunk boundaries here are CONTENT-DEFINED and purely local: a leaf chunk ends
;; after an entry whose KEY hashes to a boundary, an internal chunk ends after a
;; child whose CID hashes to a boundary. Nothing about a chunk depends on how
;; many entries precede it or on how the tree was assembled. That is the
;; property (history independence) the whole content-addressed design rests on:
;; the same logical content must produce the same CIDs regardless of insertion
;; order, or two replicas holding identical data disagree about their hashes.
;;
;; It also means an insert cannot ripple: adding key K changes exactly the run
;; of entries between the boundary before K and the boundary at or after it.
;; Every other chunk's bytes are untouched and are structurally shared.
;;
;; So `insert` rebuilds a bounded WINDOW at each level rather than the level:
;; the affected child plus its immediate successor. The successor is needed
;; because a replacement changes a child's CID, and a child that WAS a boundary
;; may stop being one -- in which case its chunk must absorb the next one. That
;; merge is the case a naive "re-chunk this node's own children" misses, and it
;; is exactly the case that would silently produce a tree no rebuild could
;; reproduce.
;;
;; `insert-tested-equivalent?` in the tests is the gate: for randomized key
;; sets and insertion orders, inserting into a tree must yield the SAME root CID
;; as building the whole sorted set from scratch. An implementation that is
;; merely "close" is worse than none, because the divergence is invisible until
;; two nodes compare roots.

(defn- leaf-node? [node] (= "leaf" (get node "kind")))

(defn- node-entries
  "Leaf entries as a vector of [k v], with dag-cbor's vectors normalized."
  [node]
  (mapv vec (get node "entries")))

(defn- node-children
  "Internal children as a vector of [max-key cid-string]. In-memory summaries
  stay plain CID strings so boundary math is encoding-independent, matching
  `build-internal-level`."
  [node]
  (mapv (fn [entry] [(first entry) (child-cid entry)]) (get node "children")))

(defn- upsert-sorted
  "Insert or replace [k v] in a sorted vector of entries, keeping key order."
  [entries k v]
  (let [i (count (take-while #(neg? (compare (first %) k)) entries))
        hit? (and (< i (count entries)) (= k (first (nth entries i))))]
    (if hit?
      (assoc entries i [k v])
      (vec (concat (subvec entries 0 i) [[k v]] (subvec entries i))))))

(defn- child-index
  "Index of the child that owns `k`: the first whose max-key >= k, else the
  last. Same rule `lookup` descends by, kept in one place."
  [children k]
  (or (first (keep-indexed (fn [i [max-key _]]
                             (when (<= (compare k max-key) 0) i))
                           children))
      (dec (count children))))

(defn- rechunk-leaves
  "Re-chunk `entries` into leaf nodes and return their [max-key cid] summaries."
  [put! entries]
  (build-leaf-level put! entries))

(defn- rechunk-internal
  "Re-chunk `children` into internal nodes and return their summaries."
  [put! children]
  (build-internal-level put! children))

(defn- splice
  "Replace `n` items of `v` starting at `i` with `replacement`."
  [v i n replacement]
  (vec (concat (subvec v 0 i) replacement (subvec v (min (count v) (+ i n))))))

(defn- tree-height
  "Number of internal levels below `root-cid`. A leaf root has height zero.
  Prolly trees are level-balanced, so following the first child is sufficient."
  [get-fn root-cid]
  (loop [cid root-cid, height 0]
    (let [node (get-node get-fn cid)]
      (if (leaf-node? node)
        height
        (recur (second (first (node-children node))) (inc height))))))

(defn- leaf-summaries-at-height
  [get-fn cid height]
  (let [node (get-node get-fn cid)]
    (cond
      (zero? height)
      [[(first (last (node-entries node))) cid]]

      (= 1 height)
      (node-children node)

      :else
      (into [] (mapcat (fn [[_ child]]
                         (leaf-summaries-at-height get-fn child (dec height))))
            (node-children node)))))

(defn- leaf-summaries
  "Every leaf's `[max-key cid]` under `root-cid`, in key order.

  Walks internal nodes only. There are ~1/256 as many of those as there are
  leaves (and ~1/65536 as many again above them), so collecting the whole leaf
  index costs O(n/256) reads -- for a five-million-entry tree, on the order of
  eighty blocks rather than twenty thousand."
  [get-fn root-cid]
  (leaf-summaries-at-height get-fn root-cid
                            (tree-height get-fn root-cid)))

(defn- mutation-plan
  [leaves additions removals]
  (let [last-index (dec (count leaves))
        addition-indexed (mapv (fn [[k _ :as pair]]
                                 [(child-index leaves k) pair])
                               additions)
        removal-indices (map #(child-index leaves %) removals)
        affected (-> (set (map first addition-indexed))
                     (into (mapcat #(if (< % last-index) [% (inc %)] [%])
                                   removal-indices))
                     sort)
        windows (reduce (fn [ranges i]
                          (if (and (seq ranges)
                                   (= i (inc (second (peek ranges)))))
                            (conj (pop ranges) [(first (peek ranges)) i])
                            (conj ranges [i i])))
                        []
                        affected)]
    {:addition-indexed addition-indexed
     :windows windows
     :removal-set (set removals)}))

(defn insert
  "Insert or replace `[k v]` under `root-cid`, writing only the affected leaf
  and the internal nodes above it, and return the new root CID.

  A nil `root-cid` builds a single-entry tree. The result is byte-identical to
  `(build-tree put! sorted-entries-with-k)` -- the tests treat any divergence
  as a failure rather than a variant, because a content-addressed store whose
  insert can produce a tree a rebuild would not is one where two replicas
  holding identical data disagree about their root hash.

  Only ONE leaf is read and rewritten; every other leaf is shared with the old
  tree. The internal levels are re-chunked in full rather than patched through
  a window. That is deliberate: boundaries are content-defined, so a
  replacement whose new CID stops being a boundary must merge its chunk with
  the following one, and when the affected node is the last child of its
  parent that sibling lives under a different parent. A window that cannot see
  past its parent cannot express that merge, and an earlier draft of this
  function got it wrong in exactly that case. Re-chunking each internal level
  from the whole ordered summary list is equivalent to what `build-tree` does
  by construction, and internal nodes are ~1/256 of the tree -- so the cost is
  a few dozen blocks where a full rebuild pays tens of thousands, and the
  correctness argument is one sentence instead of a case analysis."
  [put! get-fn root-cid k v]
  (if (nil? root-cid)
    (build-tree put! [[k v]])
    (let [leaves (leaf-summaries get-fn root-cid)
          i (child-index leaves k)
          leaf (get-node get-fn (second (nth leaves i)))
          rebuilt (rechunk-leaves put! (upsert-sorted (node-entries leaf) k v))
          level (splice leaves i 1 rebuilt)]
      (loop [level level]
        (if (= 1 (count level))
          (second (first level))
          (recur (rechunk-internal put! level)))))))

(defn insert-many
  "Insert or replace many `[k v]` pairs under `root-cid` in one pass, and
  return the new root CID.

  This is not a convenience wrapper. Calling `insert` in a loop re-chunks the
  internal levels once PER ENTRY, and the internal levels are the part this
  design rebuilds in full — so a thousand entries would rewrite them a
  thousand times and cost more than the rebuild the whole exercise exists to
  avoid. Here every affected leaf is rebuilt, then the internal levels are
  re-chunked exactly once.

  A fold's novelty is precisely this shape: many entries at once, spread over
  a few leaves. `pairs` need not be sorted or distinct; later pairs win for a
  repeated key, matching `insert`'s replace semantics.

  Byte-identical to `(build-tree put! all-sorted-entries)`, same as `insert`,
  and the tests assert it against both a rebuild and a loop of single inserts."
  [put! get-fn root-cid pairs]
  (let [pairs (vec pairs)]
    (cond
      (empty? pairs) root-cid
      (nil? root-cid) (build-tree put! (->> pairs
                                            (reduce (fn [m [k v]] (assoc m k v)) {})
                                            (sort-by first)
                                            vec))
      :else
      (let [leaves (leaf-summaries get-fn root-cid)
            ;; group by the leaf that owns each key, so every leaf is read and
            ;; rebuilt at most once however many keys land in it
            by-leaf (reduce (fn [acc [k v]]
                              (update acc (child-index leaves k) (fnil conj []) [k v]))
                            {}
                            pairs)
            level (reduce
                   (fn [level [i additions]]
                     ;; `i` indexes the ORIGINAL leaves. Splicing shifts every
                     ;; position after it, so this runs right-to-left: a splice
                     ;; at a higher index cannot move a lower one, and `i`
                     ;; stays valid without tracking an offset.
                     (let [at i
                           leaf (get-node get-fn (second (nth level at)))
                           entries (reduce (fn [es [k v]] (upsert-sorted es k v))
                                           (node-entries leaf)
                                           additions)]
                       (splice level at 1 (rechunk-leaves put! entries))))
                   leaves
                   ;; descending so each splice only affects indices after it
                   (sort-by first > by-leaf))]
        (loop [level level]
          (if (= 1 (count level))
            (second (first level))
            (recur (rechunk-internal put! level))))))))

(defn mutate-many
  "Apply `additions` (`[k v]`) and `removals` (keys) in one leaf pass.

  Removal windows include the successor leaf because deleting a boundary key
  can merge its chunk with the following chunk. Additions and removals sharing
  a window are coalesced, and internal levels are rebuilt exactly once.
  Additions win when the same key occurs in both inputs."
  [put! get-fn root-cid additions removals]
  (let [additions (vec additions)
        removals (vec (distinct removals))]
    (cond
      (nil? root-cid) (insert-many put! get-fn nil additions)
      (and (empty? additions) (empty? removals)) root-cid
      :else
      (let [leaves (leaf-summaries get-fn root-cid)
            {:keys [addition-indexed windows removal-set]}
            (mutation-plan leaves additions removals)
            level (reduce
                   (fn [level [start end]]
                     (let [retained (->> (subvec level start (inc end))
                                         (mapcat (fn [[_ cid]]
                                                   (node-entries
                                                    (get-node get-fn cid))))
                                         (remove (fn [[k _]]
                                                   (contains? removal-set k)))
                                         vec)
                           window-additions (keep (fn [[i pair]]
                                                    (when (<= start i end) pair))
                                                  addition-indexed)
                           entries (reduce (fn [es [k v]]
                                             (upsert-sorted es k v))
                                           retained
                                           window-additions)]
                       (splice level start (inc (- end start))
                               (rechunk-leaves put! entries))))
                   leaves
                   (sort-by first > windows))]
        (loop [level level]
          (cond
            (empty? level) nil
            (= 1 (count level)) (second (first level))
            :else (recur (rechunk-internal put! level))))))))

(defn delete-many
  "Delete `keys` under `root-cid` in one pass and return the new root CID.
  Missing and duplicate keys are no-ops; deleting the last entry returns nil."
  [put! get-fn root-cid keys]
  (mutate-many put! get-fn root-cid [] keys))

(defn delete
  "Delete `k` under `root-cid`; one-key convenience over `delete-many`."
  [put! get-fn root-cid k]
  (delete-many put! get-fn root-cid [k]))

;; ── the write path, for a store that answers with a Promise ─────────────────
;;
;; `scan-prefix` grew an async counterpart and the write path never did, so a
;; caller on a Promise-returning store could read a tree it had no way to
;; update. Two consumers hit that asymmetry from opposite sides this week:
;; `arrangement`'s `commit-delta!` had a `:cljs` branch that `.then`ed the
;; synchronous `insert-many` (so it could not complete at all), and
;; `kotobase-storage`'s signed head needed the same treatment one layer up.
;;
;; This is deliberately NOT an async re-implementation of the algorithm. The
;; insert logic is subtle -- the internal levels are re-chunked in full for a
;; correctness reason `insert`'s docstring spends a paragraph on, and an
;; earlier draft got exactly that case wrong. A parallel async copy would be
;; two places to get it right and one place to forget. Instead the I/O is
;; peeled off both ends: fetch what the traversal will read, run the existing
;; synchronous function against that, then flush the writes it buffered.
;;
;; What this buys, precisely: the writes are AWAITED before the new root CID
;; is handed back. `insert-many` calls `put!` and ignores what it returns, so
;; a Promise-returning `put!` was never waited on -- the caller got a root
;; naming blocks that might not have landed yet, and would publish a head
;; pointing at them.

#?(:cljs
   (defn- fetch-node!
     [get-fn cache cid]
     (if (contains? @cache cid)
       (js/Promise.resolve (verified-node cid (get @cache cid)))
       (-> (js/Promise.resolve (get-fn cid))
           (.then (fn [bytes]
                    (swap! cache assoc cid bytes)
                    (verified-node cid bytes)))))))

#?(:cljs
   (defn- warm-height!
     [get-fn cache root-cid]
     (letfn [(walk [cid height]
               (-> (fetch-node! get-fn cache cid)
                   (.then (fn [node]
                            (if (leaf-node? node)
                              height
                              (walk (second (first (node-children node)))
                                    (inc height)))))))]
       (walk root-cid 0))))

#?(:cljs
   (defn- warm-leaf-summaries!
     [get-fn cache cid height]
     (-> (fetch-node! get-fn cache cid)
         (.then
          (fn [node]
            (cond
              (zero? height)
              [[(first (last (node-entries node))) cid]]

              (= 1 height)
              (node-children node)

              :else
              (-> (pmap-async
                   (fn [[_ child]]
                     (warm-leaf-summaries! get-fn cache child (dec height)))
                   (node-children node))
                  (.then (fn [levels] (vec (apply concat levels)))))))))))

#?(:cljs
   (defn- warm-mutation!
     "Warm internal summary blocks plus only the leaf windows a mutation reads.

     The old writer recursively fetched every leaf merely to discover that it
     was a leaf. Height makes that discovery once; a penultimate internal node
     already contains every child's max-key/CID summary."
     [get-fn cache root-cid additions removals]
     (-> (warm-height! get-fn cache root-cid)
         (.then
          (fn [height]
            (-> (warm-leaf-summaries! get-fn cache root-cid height)
                (.then
                 (fn [leaves]
                   (let [{:keys [windows]}
                         (mutation-plan leaves additions removals)
                         leaf-cids
                         (distinct
                          (mapcat
                           (fn [[start end]]
                             (map second (subvec leaves start (inc end))))
                           windows))]
                     (pmap-async #(fetch-node! get-fn cache %) leaf-cids))))))))))

#?(:cljs
   (defn insert-many-async
     "`insert-many` for a `get-fn`/`put!` pair that returns Promises.

     -> `js/Promise` of the new root CID, resolved only after every block it
     wrote has been acknowledged. Byte-identical to the synchronous result for
     the same input, because it IS the synchronous function -- see the note
     above."
     [put! get-fn root-cid pairs]
     (let [pairs (vec pairs)]
       (if (empty? pairs)
         (js/Promise.resolve root-cid)
         (let [cache (atom {})
               writes (atom [])
               ;; `put-node!` uses the return value, so keep `insert-many`'s
               ;; contract: hand back the cid, buffer the bytes.
               buffered-put! (fn [cid bytes] (swap! writes conj [cid bytes]) cid)]
           (-> (if (nil? root-cid)
                 (js/Promise.resolve nil)
                 (warm-mutation! get-fn cache root-cid pairs []))
               (.then (fn [_]
                        (insert-many buffered-put! #(get @cache %) root-cid pairs)))
               (.then (fn [new-root]
                        (-> (pmap-async (fn [[cid bytes]]
                                          (js/Promise.resolve (put! cid bytes)))
                                        @writes)
                            (.then (fn [_] new-root)))))))))))

#?(:cljs
   (defn mutate-many-async
     "`mutate-many` for a Promise-returning store. Resolves only after every
     newly referenced block has been acknowledged."
     [put! get-fn root-cid additions removals]
     (let [additions (vec additions)
           removals (vec (distinct removals))]
       (if (and (empty? additions) (empty? removals))
         (js/Promise.resolve root-cid)
         (let [cache (atom {})
               writes (atom [])
               buffered-put! (fn [cid bytes] (swap! writes conj [cid bytes]) cid)]
           (-> (if root-cid
                 (warm-mutation! get-fn cache root-cid additions removals)
                 (js/Promise.resolve nil))
               (.then (fn [_]
                        (mutate-many buffered-put! #(get @cache %) root-cid
                                     additions removals)))
               (.then (fn [new-root]
                        (-> (pmap-async (fn [[cid bytes]]
                                          (js/Promise.resolve (put! cid bytes)))
                                        @writes)
                            (.then (fn [_] new-root)))))))))))

#?(:cljs
   (defn delete-many-async
     "`delete-many` for a Promise-returning store."
     [put! get-fn root-cid keys]
     (mutate-many-async put! get-fn root-cid [] keys)))

#?(:cljs
   (defn delete-async
     "`delete` for a Promise-returning store."
     [put! get-fn root-cid k]
     (delete-many-async put! get-fn root-cid [k])))

#?(:cljs
   (defn insert-async
     "`insert` for a Promise-returning store. One pair through
     `insert-many-async`, which has identical replace semantics."
     [put! get-fn root-cid k v]
     (insert-many-async put! get-fn root-cid [[k v]])))
