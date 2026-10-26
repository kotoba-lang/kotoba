(ns kuro.fs
  "Browser-resident filesystem model: a POSIX-flavoured path API whose storage
  substrate is a content-addressed IPLD DAG (ADR-2609041240).

  ## Why this namespace is pure

  Like `kuro.terminal`, this file has no I/O, no clock, no crypto, no globals.
  The host (OPFS-backed cache, kotobase gateway, browser Worker) supplies:

    - `put-block`  : bytes -> cid          (host computes sha256 + CID)
    - `get-block`  : cid -> bytes | nil    (cache -> gateway order)
    - `now-ms`     : optional receipt timestamps

  This namespace only maps **paths to DAGs** and records **receipts**. That
  split is what lets the same model run against an in-memory block store in
  tests, OPFS in a Worker, and kotobase.net in production — the substrate is
  the host's choice, the semantics are here.

  ## The mapping (the one decision in this namespace)

    - a **directory** is an IPLD map block: entries are name -> child CID,
      values are bytes, so a directory with no children is still one
      deterministic block.
    - a **file** is a unixfs file DAG (`tech-ipfs-specs-unixfs`): one chunk is
      a bare raw block, more is a dag-pb tree. We do not re-implement the
      chunker — the host wires `unixfs.file/build` and `read-file`.
    - **every write produces a new root CID.** There is no in-place mutation;
      `write` is `(fs/write store path bytes)` -> new store value. Undo is
      therefore just remembering a previous root.
    - **receipts, not exceptions, for denied work.** A path that escapes the
      mount root, a write without `fs/write` capability, a read of a
      non-existent path — each returns a `:kuro.fs/denied` receipt. An empty
      receipt list must not mean both refused and never asked (the same
      rule `kobo.workbench` records for denials).

  ## Receipts are fixed-shape, namespaced

  Mirroring `kuro.terminal/receipt`: host- or caller-supplied extras are
  dropped, everything lands in `:kuro.fs/*`."
  (:require [kotoba.lang.text :as str]))

(defn- byte-count
  "Length of a byte container on either runtime. JVM byte-arrays use alength;
  JS typed arrays use .length."
  [b]
  #?(:clj (alength b)
     :cljs (.-length b)))

(defn- byte-seq?
  "True for a byte container on either runtime. JVM: byte[]; cljs: typed
  array. Named byte-seq? (not bytes?) because clojure.core/bytes? exists on
  the JVM and a local def would shadow it."
  [b]
  #?(:clj (instance? (Class/forName "[B") b)
     :cljs (instance? js/Uint8Array b)))

(def format-version 1)

;; ---------------------------------------------------------------------------
;; capabilities
;; ---------------------------------------------------------------------------

(def default-capabilities
  "The capability vocabulary `wc.fs` understands. A host session maps its own
  grant onto these; anything not granted produces a denial receipt."
  #{"fs/read" "fs/write" "fs/ls" "fs/rm" "fs/publish"})

(def op-capabilities
  "The capability each operation requires. `mkdir` creates nodes, so it is a
  write, not a listing; `publish` is a host-side op (the block store's), not
  a path op, so no path fn requires it."
  {:read   "fs/read"
   :write  "fs/write"
   :ls     "fs/ls"
   :mkdir  "fs/write"
   :rm     "fs/rm"})

(defn with-grant
  "Constrain the store to `caps` (a subset of `default-capabilities`). The
  grant is a value inside the store — same discipline as `kuro.terminal`'s
  session grant — so a store handed to untrusted code carries its own limits
  and every op records what it was refused for. Ops absent from the grant
  produce a `:kuro.fs/denied` receipt with `:kuro.fs/missing`, not an
  exception. Default (no `with-grant`) is the full vocabulary."
  [st caps]
  (assoc st :kuro.fs/grant (set caps)))

;; ---------------------------------------------------------------------------
;; paths
;; ---------------------------------------------------------------------------

(defn- clean-path
  "Normalize a POSIX-ish path to a vector of segments, refusing escapes.
  Returns nil (do not throw — callers convert to a denial receipt) when the
  path is not a string, is blank, or contains a `..` traversal. `.` segments
  are dropped, so `.` and `./` resolve to the root (empty vector, truthy)."
  [p]
  (when (and (string? p) (not (str/blank? p)))
    (let [segs (->> (str/split p #"/+")
                    (remove #(or (= "" %) (= "." %))))]
      (when (not (some #(= ".." %) segs))
        (vec segs)))))

(defn- join-path [segs]
  (str/join "/" segs))

;; ---------------------------------------------------------------------------
;; store value
;; ---------------------------------------------------------------------------

(defn- new-store [mount-root]
  {:kuro.fs/format-version format-version
   :kuro.fs/mount-root mount-root
   ;; node-id -> {:type :dir|:file :entries {...} | :cid cid :size n}
   ;; entries maps name -> node-id. The DAG itself (cid -> bytes) lives in the
   ;; host's block store; we keep CIDs here, never bytes.
   :kuro.fs/nodes {}
   :kuro.fs/root :root
   ;; Default grant is the whole vocabulary; `with-grant` narrows it.
   :kuro.fs/grant default-capabilities
   :kuro.fs/receipts []})

(defn- check-grant
  "Denial receipt when `op`'s capability is outside the store's grant, else
  nil. The docstring's claim — a write without `fs/write` is a denial, not an
  exception — is enforced here, once, for every path op."
  [st op path]
  (let [cap (get op-capabilities op)
        grant (or (:kuro.fs/grant st) default-capabilities)]
    (when (and cap (not (contains? grant cap)))
      {:reason :missing-capability
       :extra  {:kuro.fs/missing cap}})))

(defn store
  "A fresh filesystem mounted at `mount-root` (a repo-root CID string)."
  ([] (store nil))
  ([mount-root] (new-store mount-root)))

(defn- record!
  "Append a receipt to the store value. Takes and returns the store."
  [st receipt]
  (update st :kuro.fs/receipts conj receipt))

(defn- denied
  "Build (and record) a denial receipt, and return `[store' nil]` — the same
  shape the public API returns on success, so every caller destructures one
  way. `extra` must be a map of fixed keys."
  ([st op path reason] (denied st op path reason {}))
  ([st op path reason extra]
   (let [r (merge {:kuro.fs/type :kuro.fs/denied
                   :kuro.fs/op op
                   :kuro.fs/path (if (string? path) path (join-path path))
                   :kuro.fs/reason reason}
                  (select-keys extra [:kuro.fs/missing :kuro.fs/cid]))]
     [(record! st r) nil])))

(defn- ok-receipt [op path extra]
  (merge {:kuro.fs/type :kuro.fs/receipt
          :kuro.fs/op op
          :kuro.fs/path (if (string? path) path (join-path path))}
         (select-keys extra [:kuro.fs/cid :kuro.fs/size :kuro.fs/entries
                             :kuro.fs/at-ms :kuro.fs/root-cid])))

;; ---------------------------------------------------------------------------
;; node helpers (pure, over :kuro.fs/nodes)
;; ---------------------------------------------------------------------------

(defn- node-at
  "Resolve a path to a node (or nil). Read-only."
  [nodes segs]
  (loop [id :root
         [seg & rest] segs]
    (let [n (get nodes id)]
      (cond
        (nil? n) nil
        (nil? seg) n
        (not= :dir (:type n)) nil
        :else (recur (get (:entries n) seg) rest)))))

(defn- dir-with [entries]
  {:type :dir :entries entries})

(defn- put-node [nodes id node]
  (assoc nodes id node))

(defn- set-path
  "Set `node` at `segs`, creating intermediate directories. Returns
  [nodes' node-id] on success, or nil when a file blocks the path.

  Two-phase: assign the leaf node first, then link it from every ancestor up
  to :root. The single-segment case (`hello.txt`) must still link from :root,
  which is why the leaf assignment happens before the ancestor walk rather
  than being returned early. The ancestor walk's accumulated nodes map is the
  returned nodes' — the leaf-only map is never used on its own."
  [nodes segs node]
  (let [leaf-id (keyword (str "n" (count (keys nodes)) "-" (join-path segs)))
        link
        (fn link [acc child-id rev]
          (if (empty? rev)
            ;; all ancestors linked; child-id is the id of the root-level dir
            ;; or the leaf itself when segs had one segment.
            [acc child-id]
            (let [seg (first rev)
                  parent-segs (vec (reverse (rest rev)))]
              (if (empty? parent-segs)
                ;; the parent IS the root: link directly into :root
                (let [pn (get acc :root)
                      entries (or (:entries pn) {})]
                  (recur (put-node acc :root (dir-with (assoc entries seg child-id)))
                         :root
                         (rest rev)))
                (let [pn (node-at acc parent-segs)]
                  (cond
                    ;; parent doesn't exist yet: create it as a dir holding child
                    (nil? pn)
                    (let [pid (keyword (str "n" (count (keys acc)) "-" (join-path parent-segs)))]
                      (recur (put-node acc pid (dir-with {seg child-id}))
                             pid
                             (rest rev)))
                    ;; parent exists but is a file: the path is blocked
                    (not= :dir (:type pn)) nil
                    ;; parent is a dir: add/update the child entry
                    :else (let [pid (keyword (str "n" (count (keys acc)) "-" (join-path parent-segs)))]
                            (recur (put-node acc pid (dir-with (assoc (or (:entries pn) {}) seg child-id)))
                                   pid
                                   (rest rev)))))))))]
    (when-let [linked (link (put-node nodes leaf-id node) leaf-id (reverse segs))]
      linked)))

(defn- remove-path
  "Remove `segs` (a file or empty dir). Returns updated nodes, or nil when the
  path does not exist."
  [nodes segs]
  (let [parent-segs (butlast segs)
        name (last segs)
        pn (node-at nodes (or parent-segs []))]
    (when (and pn (= :dir (:type pn)) (contains? (:entries pn) name))
      (if (empty? parent-segs)
        (put-node nodes :root (dir-with (dissoc (:entries pn) name)))
        (let [id (get-in (node-at nodes (butlast parent-segs)) [:entries (last parent-segs)])]
          (put-node nodes id (dir-with (dissoc (:entries pn) name))))))))

;; ---------------------------------------------------------------------------
;; public API — every fn takes the store value and returns [store' result]
;; ---------------------------------------------------------------------------

(defn ls
  "List a directory. Returns [store' entries] where entries is
  [{:name :type :size} ...] sorted by name; a denial records a receipt and
  returns [store' nil]."
  [st path]
  (let [op :ls
        segs (clean-path path)]
    (cond
      (nil? segs) (denied st op path :bad-path)
      (check-grant st op path) (let [{:keys [reason extra]} (check-grant st op path)]
                                 (denied st op path reason extra))
      :else (let [n (node-at (:kuro.fs/nodes st) segs)]
              (cond
                (nil? n) (denied st op path :not-found)
                (not= :dir (:type n)) (denied st op path :not-a-directory)
                :else [(record! st (ok-receipt op path {:kuro.fs/entries (count (:entries n))}))
                       (->> (:entries n)
                            (map (fn [[name child-id]]
                                   (let [cn (get (:kuro.fs/nodes st) child-id)]
                                     {:name name
                                      :type (:type cn)
                                      :size (or (:size cn) 0)})))
                            (sort-by :name)
                            vec)])))))

(defn read-file
  "Read a file's bytes via the host's block store. `get-block` is injected:
  cid -> bytes | nil. Returns [store' bytes] — bytes nil on denial."
  [st path get-block]
  (let [op :read
        segs (clean-path path)]
    (cond
      (nil? segs) (denied st op path :bad-path)
      (check-grant st op path) (let [{:keys [reason extra]} (check-grant st op path)]
                                 (denied st op path reason extra))
      :else (let [n (node-at (:kuro.fs/nodes st) segs)]
              (cond
                (nil? n) (denied st op path :not-found)
                (not= :file (:type n)) (denied st op path :not-a-file)
                :else (let [bytes (get-block (:cid n))]
                        (if (nil? bytes)
                          (denied st op path :block-missing {:kuro.fs/cid (:cid n)})
                          [(record! st (ok-receipt op path {:kuro.fs/cid (:cid n) :kuro.fs/size (:size n)}))
                           bytes])))))))

(defn write
  "Write bytes to a path. `put-block` is injected: bytes -> cid (host computes
  the unixfs DAG and stores it). Returns [store' cid] — cid nil on denial.
  Writing over a directory is refused; over a file replaces it."
  [st path bytes put-block]
  (let [op :write
        segs (clean-path path)]
    (cond
      (nil? segs) (denied st op path :bad-path)
      (not (byte-seq? bytes)) (denied st op path :bytes-required)
      (check-grant st op path) (let [{:keys [reason extra]} (check-grant st op path)]
                                 (denied st op path reason extra))
      :else (let [n (node-at (:kuro.fs/nodes st) segs)]
              (cond
                (= :dir (:type n)) (denied st op path :is-a-directory)
                :else (let [cid (put-block bytes)
                            setp (set-path (:kuro.fs/nodes st) segs
                                           {:type :file :cid cid :size (byte-count bytes)})
                            nodes (first setp)]
                        (if (or (nil? setp) (nil? nodes))
                          (denied st op path :path-blocked)
                          [(-> st
                               (assoc :kuro.fs/nodes nodes)
                               (record! (ok-receipt op path {:kuro.fs/cid cid :kuro.fs/size (byte-count bytes)})))
                           cid])))))))

(defn mkdir
  "Create a directory (and missing parents). Returns [store' path] on success."
  [st path]
  (let [op :mkdir
        segs (clean-path path)]
    (cond
      (nil? segs) (denied st op path :bad-path)
      (check-grant st op path) (let [{:keys [reason extra]} (check-grant st op path)]
                                 (denied st op path reason extra))
      :else (let [setp (set-path (:kuro.fs/nodes st) segs (dir-with {}))
                  nodes (first setp)]
              (if (or (nil? setp) (nil? nodes))
                (denied st op path :path-blocked)
                [(-> st
                     (assoc :kuro.fs/nodes nodes)
                     (record! (ok-receipt op path {})))
                 path])))))

(defn rm
  "Remove a file or an empty directory. Non-empty directories are refused —
  a recursive remove is a separate, explicit decision."
  [st path]
  (let [op :rm
        segs (clean-path path)]
    (cond
      (nil? segs) (denied st op path :bad-path)
      (check-grant st op path) (let [{:keys [reason extra]} (check-grant st op path)]
                                 (denied st op path reason extra))
      :else (let [n (node-at (:kuro.fs/nodes st) segs)]
              (cond
                (nil? n) (denied st op path :not-found)
                (and (= :dir (:type n)) (seq (:entries n))) (denied st op path :directory-not-empty)
                :else (let [nodes (remove-path (:kuro.fs/nodes st) segs)]
                        (if (nil? nodes)
                          (denied st op path :not-found)
                          [(-> st
                               (assoc :kuro.fs/nodes nodes)
                               (record! (ok-receipt op path {})))
                           true])))))))

(defn receipts
  "All receipts so far — accepted AND denied. An audit reads both."
  [st]
  (:kuro.fs/receipts st))
