(ns kotoba.lang.checkpointer.mst
  "Merkle Search Tree construction, ported from @atproto/repo's
  `src/mst/mst.ts` + `src/mst/util.ts` (read directly from this repo's own
  installed node_modules -- see scripts/gen-mst-vectors.mjs for the
  known-answer vectors this port is checked against).

  Scope note (deliberate, not an oversight): checkpointer.ts's `#commitMst`
  ALWAYS builds a brand-new empty MST (`MST.create(storage)`) and performs
  EXACTLY ONE `.add()` call per `put` -- it never loads a persisted tree,
  never updates/deletes, never lazily fetches subtrees from storage. This
  port therefore implements only the subset of the real MST algorithm that
  `add` (and its helpers `splitAround`/`createChild`/`createParent`/
  `spliceIn`/`replaceWithSplit`) actually exercises -- no `update`/`delete`/
  `trimTop`/lazy-load/`walk*`/proof machinery, none of which `commitMst`
  calls. The `add` algorithm ITSELF is a full, faithful port (not a
  single-entry shortcut): it handles multi-entry trees, layer promotion, and
  subtree splitting exactly like the original, and is verified against a
  deliberately multi-layer tree in the test suite (mst_multi_entry_split
  vector), not just the trivial single-leaf case.

  Because Clojure trees are immutable, there is no need for the TS
  implementation's `outdatedPointer` mutable-cache dance: a node's CID
  (`get-pointer`) is ALWAYS `cid-for-entries` of its current `:entries` --
  recomputing on demand is always correct, just a (here, irrelevant at this
  scale) perf tradeoff instead of a cache.

  DETERMINISM CONTRACT (inherited from checkpointer.ts, see
  kotoba.lang.checkpointer namespace docstring / README): same key/value
  sequence added to a fresh empty tree => same root CID, bit for bit. Any
  divergence from @atproto/repo's actual algorithm here is a silent
  correctness bug, not a crash.

  Fanout/prefix math reuse: `io.github.kotoba-lang/mst` (`mst.core`) already
  implements the pure layer-computation formula
  (`leading-zeros-on-hash`, 2-bit-group leading-zero-count of SHA-256(key))
  and the key-prefix-compression helper (`common-prefix-len`) this
  namespace needs -- reused directly below instead of re-deriving them, to
  avoid two independently-written copies of load-bearing fanout math. Cross-
  verified against the REAL @atproto/repo output (not just `mst.core`'s own
  internal self-consistency test, which only checks two of ITS OWN formulas
  against each other) via the `:leading_zeros` vectors in
  test/kotoba/lang/checkpointer/mst_vectors.edn.

  NOT reused: `mst.core/key-valid?`. Its length cap is 256 chars, but the
  REAL @atproto/repo `isValidMstKey` (src/mst/util.ts, read directly from
  this repo's node_modules) caps at 1024 -- using the 256 cap here would
  make this port reject valid keys (e.g. long checkpoint_ids) the real
  system accepts, a correctness regression. This looks like a bug in
  `kotoba-lang/mst` worth fixing upstream; flagged, not silently worked
  around. `valid-mst-key?`/`ensure-valid-mst-key!` below are this port's own
  1024-cap-correct implementation.

  Portability: this namespace's OWN logic is plain, portable Clojure (the
  only JVM-ism, `ascii-bytes`, is `#?`-conditionalized below); it is `.cljc`
  so it loads under ClojureScript too. It still calls into
  `kotoba.lang.checkpointer.dagcbor` (`get-pointer`/`serialize-node-data`),
  which is itself content-addressing code kept `:clj`-only (see that
  namespace's docstring) -- so this namespace compiles cleanly under cljs
  but any call path that reaches `get-pointer` still throws there, same
  contract as `multiformats.core`'s CID/byte machinery."
  (:require [kotoba.lang.text :as str]
            [mst.core :as mstcore]
            [kotoba.lang.checkpointer.dagcbor :as cbor]
            [kotoba.lang.checkpointer.blockmap :as bm]))

;; ---------------------------------------------------------------------------
;; Nodes
;; ---------------------------------------------------------------------------

(defrecord Leaf [key value])          ; value = CID string
(defrecord MstTree [layer entries])   ; entries: vector of Leaf | MstTree

(defn tree? [x] (instance? MstTree x))
(defn leaf? [x] (instance? Leaf x))

(defn- get-layer
  "An empty, freshly-created root has `:layer nil`; every other node this
  port ever constructs is given an explicit numeric layer at creation time
  (mirrors `MST.getLayer`'s `attemptGetLayer` -> `layerForEntries([]) ->
  null -> defaults to 0`, specialized to the load-free case)."
  ^long [node]
  (or (:layer node) 0))

(defn mst-empty
  "A brand-new, empty MST root (`MST.create(storage)` with no entries/opts)."
  [] (->MstTree nil []))

(defn- mst-create [entries layer] (->MstTree layer (vec entries)))

;; ---------------------------------------------------------------------------
;; util.ts port
;; ---------------------------------------------------------------------------

(defn leading-zeros-on-hash
  "2-bits-of-zero-per-layer fanout hash, over the UTF-8 bytes of `key`
  (@atproto/crypto's `sha256` UTF-8-encodes string input). Delegates to
  `mst.core/leading-zeros-on-hash` (see namespace docstring)."
  ^long [^String key]
  (long (mstcore/leading-zeros-on-hash key)))

(defn count-prefix-len
  "Length of the common prefix of `a` and `b`. Delegates to
  `mst.core/common-prefix-len` (see namespace docstring)."
  ^long [^String a ^String b]
  (long (mstcore/common-prefix-len a b)))

(def valid-chars-regex #"^[a-zA-Z0-9_~\-:.]*$")

(defn valid-chars? [^String s] (boolean (re-matches valid-chars-regex s)))

(defn valid-mst-key?
  "collection/rkey shape, <=1024 chars, both halves non-empty + valid chars.
  `str/split` needs the `-1` limit to keep trailing empty segments (matching
  JS `String.split`'s default of NOT dropping trailing empties, unlike
  Clojure's default which does)."
  [^String s]
  (let [parts (str/split s #"/" -1)]
    (and (<= (count s) 1024)
         (= 2 (count parts))
         (pos? (count (first parts)))
         (pos? (count (second parts)))
         (valid-chars? (first parts))
         (valid-chars? (second parts)))))

(defn ensure-valid-mst-key! [^String s]
  (when-not (valid-mst-key? s)
    (throw (ex-info (str "Not a valid MST key: " s) {:key s}))))

;; ---------------------------------------------------------------------------
;; Serialization + node CID
;; ---------------------------------------------------------------------------

(defn- ascii-bytes [s]
  #?(:clj (.getBytes ^String s "US-ASCII")
     ;; MST keys are already constrained to the AT-key charset
     ;; (valid-chars-regex, below), which is ASCII -- a plain UTF-8 encode is
     ;; therefore byte-identical to US-ASCII for every string this ever sees.
     :cljs (.encode (js/TextEncoder.) s)))

(declare get-pointer)

(defn serialize-node-data
  "entries -> {:l CidLink-or-nil :e [{:p n :k bytes :v CidLink :t
  CidLink-or-nil} ...]} -- the exact MST node dag-cbor schema (`nodeData` in
  mst.ts). Field order in the final bytes is decided by dagcbor's canonical
  key sort, NOT by map construction order here (matches the real
  implementation, which also relies on canonical CBOR key sorting rather
  than JS object property order)."
  [entries]
  (let [n (count entries)
        first-is-tree? (and (pos? n) (tree? (nth entries 0)))
        start (if first-is-tree? 1 0)
        l (when first-is-tree? (cbor/cid-link (get-pointer (nth entries 0))))]
    (loop [i start last-key "" e []]
      (if (>= i n)
        {:l l :e e}
        (let [leaf (nth entries i)]
          (when-not (leaf? leaf)
            (throw (ex-info "Not a valid node: two subtrees next to each other" {:index i})))
          (let [nxt (when (< (inc i) n) (nth entries (inc i)))
                next-tree? (and nxt (tree? nxt))
                subtree-cid (when next-tree? (cbor/cid-link (get-pointer nxt)))
                next-i (if next-tree? (+ i 2) (inc i))
                prefix-len (count-prefix-len last-key (:key leaf))
                entry {:p prefix-len
                       :k (ascii-bytes (subs (:key leaf) prefix-len))
                       :v (cbor/cid-link (:value leaf))
                       :t subtree-cid}]
            (recur next-i (:key leaf) (conj e entry))))))))

(defn get-pointer
  "A node's CID -- always freshly `cid-for-entries`'d (see namespace
  docstring on why there's no mutable-pointer cache here)."
  ^String [node]
  (cbor/cid-for-value (serialize-node-data (:entries node))))

;; ---------------------------------------------------------------------------
;; Entry-list helpers (array.slice / splice / replace-in-place)
;; ---------------------------------------------------------------------------

(defn- at-index [entries i]
  (when (and (>= i 0) (< i (count entries))) (nth entries i)))

(defn- mst-slice
  ([entries start] (mst-slice entries start (count entries)))
  ([entries start end]
   (let [v (vec entries) n (count v)
         s (max 0 (min start n))
         e (max s (min end n))]
     (subvec v s e))))

(defn- splice-in [entries entry index]
  (vec (concat (mst-slice entries 0 index) [entry] (mst-slice entries index))))

(defn- update-entry [entries index entry]
  (vec (concat (mst-slice entries 0 index) [entry] (mst-slice entries (inc index)))))

(defn- remove-entry [entries index]
  (vec (concat (mst-slice entries 0 index) (mst-slice entries (inc index)))))

(defn- append-entry [entries entry] (conj (vec entries) entry))
(defn- prepend-entry [entries entry] (vec (cons entry entries)))

(defn- replace-with-split [entries index left leaf right]
  (vec (concat (mst-slice entries 0 index)
               (when left [left])
               [leaf]
               (when right [right])
               (mst-slice entries (inc index)))))

(defn- find-gt-or-equal-leaf-index
  "Index of the first leaf whose key is >= `key`; entries length if none."
  ^long [entries ^String key]
  (or (first (keep-indexed (fn [i e] (when (and (leaf? e) (>= (compare (:key e) key) 0)) i)) entries))
      (count entries)))

;; ---------------------------------------------------------------------------
;; Relatives
;; ---------------------------------------------------------------------------

(defn- create-child [node] (mst-create [] (dec (get-layer node))))
(defn- create-parent [node] (mst-create [node] (inc (get-layer node))))

;; ---------------------------------------------------------------------------
;; splitAround
;; ---------------------------------------------------------------------------

(defn split-around
  "Recursively split `node` around `key` -> [left-or-nil right-or-nil]."
  [node ^String key]
  (let [entries (:entries node)
        layer (get-layer node)
        index (find-gt-or-equal-leaf-index entries key)
        left-data (mst-slice entries 0 index)
        right-data (mst-slice entries index)
        right0 (mst-create right-data layer)
        last-in-left (when (pos? (count left-data)) (peek left-data))]
    (if (and last-in-left (tree? last-in-left))
      (let [left-data' (remove-entry left-data (dec (count left-data)))
            [split-l split-r] (split-around last-in-left key)
            left-entries (if split-l (append-entry left-data' split-l) left-data')
            right-entries (if split-r (prepend-entry right-data split-r) right-data)
            left (mst-create left-entries layer)
            right (mst-create right-entries layer)]
        [(when (pos? (count (:entries left))) left)
         (when (pos? (count (:entries right))) right)])
      (let [left (mst-create left-data layer)]
        [(when (pos? (count left-data)) left)
         (when (pos? (count (:entries right0))) right0)]))))

;; ---------------------------------------------------------------------------
;; add
;; ---------------------------------------------------------------------------

(defn mst-add
  "Add `key` -> `value` (a CID string) to `node`. Throws if `key` already
  present. Direct port of `MST.add` (see mst.ts) -- layer promotion,
  subtree descent, and splitAround/replaceWithSplit are all exercised, not
  just the trivial 'insert into a fresh empty tree' path (that path IS
  exercised too, since it's what checkpointer.ts's #commitMst always does,
  but the general algorithm is what's implemented)."
  ([node key value] (mst-add node key value nil))
  ([node ^String key value known-zeros]
   (ensure-valid-mst-key! key)
   (let [key-zeros (long (or known-zeros (leading-zeros-on-hash key)))
         layer (get-layer node)
         new-leaf (->Leaf key value)]
     (cond
       (= key-zeros layer)
       (let [entries (:entries node)
             index (find-gt-or-equal-leaf-index entries key)
             found (at-index entries index)]
         (when (and found (leaf? found) (= (:key found) key))
           (throw (ex-info (str "There is already a value at key: " key) {:key key})))
         (let [prev-node (at-index entries (dec index))]
           (if (or (nil? prev-node) (leaf? prev-node))
             (mst-create (splice-in entries new-leaf index) layer)
             (let [[l r] (split-around prev-node key)]
               (mst-create (replace-with-split entries (dec index) l new-leaf r) layer)))))

       (< key-zeros layer)
       (let [entries (:entries node)
             index (find-gt-or-equal-leaf-index entries key)
             prev-node (at-index entries (dec index))]
         (if (and prev-node (tree? prev-node))
           (let [new-subtree (mst-add prev-node key value key-zeros)]
             (mst-create (update-entry entries (dec index) new-subtree) layer))
           (let [child (create-child node)
                 new-subtree (mst-add child key value key-zeros)]
             (mst-create (splice-in entries new-subtree index) layer))))

       :else ; key-zeros > layer: push the rest of the tree down
       (let [[left0 right0] (split-around node key)
             extra-layers (- key-zeros layer)
             wrap (fn [t] (reduce (fn [acc _] (when acc (create-parent acc))) t (range 1 extra-layers)))
             left (wrap left0)
             right (wrap right0)
             updated (cond-> []
                       left (conj left)
                       true (conj new-leaf)
                       right (conj right))]
         (mst-create updated key-zeros))))))

;; ---------------------------------------------------------------------------
;; getUnstoredBlocks
;; ---------------------------------------------------------------------------

(defn get-unstored-blocks
  "`storage-cids` is the set of CID strings ALREADY persisted before MST
  construction (the payload/ref blocks `commit-mst` adds up front). Returns
  {:root cid-str :blocks BlockMap} -- the MST node block(s) not already
  covered by `storage-cids`, exactly mirroring `MST.getUnstoredBlocks`."
  [node storage-cids]
  (let [pointer (get-pointer node)]
    (if (contains? storage-cids pointer)
      {:root pointer :blocks (bm/empty-block-map)}
      (let [data (serialize-node-data (:entries node))
            bytes (cbor/encode data)
            blocks (bm/bm-set (bm/empty-block-map) pointer bytes)
            blocks (reduce
                    (fn [acc entry]
                      (if (tree? entry)
                        (bm/bm-add-map acc (:blocks (get-unstored-blocks entry storage-cids)))
                        acc))
                    blocks
                    (:entries node))]
        {:root pointer :blocks blocks}))))
