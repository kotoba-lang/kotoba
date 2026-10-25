(ns kotobase.sftp.fs
  "sftp.kotobase.net (or any self-hosted peer) — real filesystem semantics
  projected onto the kotobase IStore document space (ADR-2607172210, KRP
  §16.4: an SFTP path is a Location only — no Name/Record/Content mapping
  of its own).

  This namespace is the Phase 1 CORE this whole repo exists to ship
  regardless of the transport question (ADR-2607172210's own framing): a
  pure `.cljc` filesystem model, deliberately decoupled from every
  SSH-specific concept — no session, no channel, no request-id, no wire
  packet shape appears anywhere below. `kotobase.sftp.transport.*`
  (`.cljs`-only, experimental — see that namespace's docstring) is the
  ONLY thing that knows an SSH_FXP_* opcode exists; it is a consumer of
  this namespace, calling these functions directly and translating their
  `{:ok? ...}` result maps to SFTP protocol responses. This is the
  intended single swap-in point for any transport, including a future
  Phase-2 WASM-guest host-capability-based one (ADR-2607172210 Rejected
  section) — this namespace does not need to change for that to work.

  Mapping:
    share (a filesystem root)  → IStore collection [:kotobase.sftp/fs <share>]
    path                       → doc key, '/'-joined, no leading/trailing
                                  '/' once normalized (see normalize-path)
    file entry                 → {:type :file :bytes <string> :size :content-type :mtime}
    directory entry            → {:type :dir :mtime}
    the share root (path \"\")  → implicit; always exists as a directory,
                                  never has its own stored doc
    every mutation             → audit event on :kotobase.protocols/audit
                                  (same convention as kotobase.protocols.s3)

  DIRECTORY-CREATION MODEL (the write/mkdir choice this namespace's
  docstring is required to make explicit): `write` and `mkdir` both
  require the PARENT directory to already exist — either the implicit
  share root, or a directory previously created with `mkdir`. Neither
  auto-vivifies missing parent directories. This mirrors real POSIX
  `open(2, O_CREAT)`/`mkdir(2)` semantics (and SFTP's own
  SSH_FX_NO_SUCH_FILE error when a parent is missing) rather than S3's
  flat-key-space convention of treating '/' as purely cosmetic — SFTP is
  a real directory-tree protocol, and `readdir`/`rmdir` (empty-check)
  below depend on directories being real, explicitly-created entries, not
  inferred from key prefixes alone.

  Deliberately out of scope here (v0.1, same discipline as
  kotobase.protocols.s3's own carve-out docstring):
    - POSIX permission bits / uid / gid / mode / ACLs — no `chmod`,
      `chown`; every caller has full access to every path in a share.
      Access control is the deploy shell's job, exactly as SigV4 lives
      outside kotobase.protocols.s3.
    - Symlinks and hard links.
    - Extended attributes (SFTP v4+ ACLs/attrib-bits) beyond
      type/size/mtime.
    - Partial/byte-range `write` — `write` always replaces a file's
      entire contents in one call (matches the rest of this protocol
      family's 'string body, v0.1' convention). `read` DOES support an
      `:offset`/`:length` byte range (SFTP's own READ request always
      carries those), sliced out of the fully-materialized string body —
      there is no streaming/chunked write path.
    - Concurrent-writer conflict detection beyond IStore's own
      last-writer-wins `-put` semantics — no locking, no O_EXCL atomicity
      guarantee beyond what a single `-put` call already gives for free.
    - Cross-share rename/copy — `rename` only moves an entry within one
      share (mirrors SFTP's own single-filesystem RENAME semantics; SFTP
      has no protocol concept of a multi-share request in the first
      place)."
  (:require [kotoba.lang.text :as str]
            [kotobase.store :as st]))

;; ---------------------------------------------------------------------------
;; Collection / path helpers
;; ---------------------------------------------------------------------------

(defn fs-coll [share] [:kotobase.sftp/fs share])

(defn normalize-path
  "\"/a//b/\" -> \"a/b\"; \"\" or \"/\" -> \"\" (the share root). Returns nil
  (an invalid path, KRP §12 discipline: reject traversal) when any segment
  is exactly \".\" or \"..\" — callers MUST check for nil, never pass a
  \"..\"-containing string through to a doc key."
  [path]
  (let [segs (->> (str/split (or path "") #"/+")
                  (remove str/blank?))]
    (when-not (some #(or (= "." %) (= ".." %)) segs)
      (str/join "/" segs))))

(defn- parent-path
  "Parent of a normalized, non-root path `p`. Callers never invoke this
  with p = \"\" (the root has no parent)."
  [p]
  (let [segs (str/split p #"/+")]
    (if (<= (count segs) 1)
      ""
      (str/join "/" (butlast segs)))))

(defn- dir? [node] (= :dir (:type node)))

(defn- get-node
  "The stored doc at `p`, or a synthetic always-present directory node
  when `p` is the share root (\"\") — the root is never itself a stored
  doc, so `st/-get` would otherwise (correctly, but unhelpfully for every
  caller here) return nil for it."
  [store coll p]
  (if (= p "")
    {:type :dir :root? true}
    (st/-get store coll p)))

(defn- audit!
  [store op share path & [extra]]
  (st/-append store :kotobase.protocols/audit
              (merge {:surface :sftp :op op :share share :path path} extra)))

;; ---------------------------------------------------------------------------
;; readdir / stat
;; ---------------------------------------------------------------------------

(defn readdir
  "List direct children of `path` (which must already exist and be a
  directory). Entries are `{:name :type :size :mtime}`, sorted by name —
  `:name` is the child's basename, not its full path (SFTP's own READDIR
  response is basename-shaped; the transport layer joins it back onto
  `path` if it needs the full path)."
  [{:keys [store]} share path]
  (if-let [p (normalize-path path)]
    (let [coll (fs-coll share)
          node (get-node store coll p)]
      (cond
        (nil? node) {:ok? false :error :kotobase.sftp/no-such-file :path path}
        (not (dir? node)) {:ok? false :error :kotobase.sftp/not-a-directory :path path}
        :else
        (let [prefix (if (= p "") "" (str p "/"))
              entries (->> (st/-list store coll)
                           (keep (fn [k]
                                   (when (and (not= k p) (str/starts-with? k prefix))
                                     (let [rel (subs k (count prefix))]
                                       (when-not (str/includes? rel "/")
                                         (when-let [n (st/-get store coll k)]
                                           {:name rel :type (:type n)
                                            :size (:size n) :mtime (:mtime n)}))))))
                           (sort-by :name)
                           vec)]
          {:ok? true :path p :entries entries})))
    {:ok? false :error :kotobase.sftp/invalid-path :path path}))

(defn stat
  "Metadata for `path`: `{:ok? true :type :size :mtime}` (directories have
  a nil `:size`), or `{:ok? false :error :kotobase.sftp/no-such-file}`."
  [{:keys [store]} share path]
  (if-let [p (normalize-path path)]
    (let [node (get-node store (fs-coll share) p)]
      (if node
        {:ok? true :path p :type (:type node) :size (:size node) :mtime (:mtime node)}
        {:ok? false :error :kotobase.sftp/no-such-file :path path}))
    {:ok? false :error :kotobase.sftp/invalid-path :path path}))

;; ---------------------------------------------------------------------------
;; open / read (SSH_FXP_OPEN / SSH_FXP_READ)
;; ---------------------------------------------------------------------------

(defn open
  "Validate `path` exists and is a file; returns `{:ok? true :handle
  {:share :path}}` for `read-file` to use. There is no server-side open
  file-descriptor table here — a \"handle\" is just the (share, path)
  pair, since v0.1 has no partial-write/streaming state to hold open
  across calls. The transport layer is free to mint its own opaque
  SSH_FXP_HANDLE bytes and keep this map behind them; that bookkeeping is
  session state and deliberately does not belong in this namespace."
  [{:keys [store]} share path]
  (if-let [p (normalize-path path)]
    (let [node (get-node store (fs-coll share) p)]
      (cond
        (nil? node) {:ok? false :error :kotobase.sftp/no-such-file :path path}
        (dir? node) {:ok? false :error :kotobase.sftp/is-a-directory :path path}
        :else {:ok? true :handle {:share share :path p}}))
    {:ok? false :error :kotobase.sftp/invalid-path :path path}))

(defn read-file
  "Read up to `:length` bytes starting at `:offset` (default 0/whole
  file) from an already-`open`ed handle. `:eof?` true means this read
  reached (or started past) end-of-file — the transport layer maps that
  to SSH_FX_EOF once a read returns zero bytes at EOF, matching real SFTP
  READ semantics."
  [{:keys [store]} {:keys [share path]} & {:keys [offset length]}]
  (let [node (get-node store (fs-coll share) path)]
    (cond
      (nil? node) {:ok? false :error :kotobase.sftp/no-such-file :path path}
      (dir? node) {:ok? false :error :kotobase.sftp/is-a-directory :path path}
      :else
      (let [bytes (or (:bytes node) "")
            total (count bytes)
            off (max 0 (or offset 0))]
        (if (>= off total)
          {:ok? true :bytes "" :eof? true}
          (let [len (or length (- total off))
                end (min total (+ off len))]
            {:ok? true :bytes (subs bytes off end) :eof? (>= end total)}))))))

;; ---------------------------------------------------------------------------
;; write (SSH_FXP_WRITE, whole-file v0.1)
;; ---------------------------------------------------------------------------

(defn write
  "Store `bytes` (a string, same 'string body, v0.1' convention as the
  rest of this protocol family) as the full contents of `path`. `path`'s
  parent directory MUST already exist (see ns docstring); `write` never
  creates it. Overwrites an existing file; errors on an existing
  directory at `path`."
  [{:keys [store now]} share path bytes & [opts]]
  (if-let [p (normalize-path path)]
    (let [coll (fs-coll share)]
      (cond
        (= p "") {:ok? false :error :kotobase.sftp/is-a-directory :path path}
        (dir? (get-node store coll p)) {:ok? false :error :kotobase.sftp/is-a-directory :path path}
        :else
        (let [parent (get-node store coll (parent-path p))]
          (cond
            (nil? parent) {:ok? false :error :kotobase.sftp/no-such-file :path path}
            (not (dir? parent)) {:ok? false :error :kotobase.sftp/not-a-directory :path path}
            :else
            (let [bytes (or bytes "")
                  node {:type :file :bytes bytes :size (count bytes)
                        :content-type (or (:content-type opts) "application/octet-stream")
                        :mtime now}]
              (st/-put store coll p node)
              (audit! store :write share p)
              {:ok? true :path p :size (:size node)})))))
    {:ok? false :error :kotobase.sftp/invalid-path :path path}))

;; ---------------------------------------------------------------------------
;; mkdir / rmdir
;; ---------------------------------------------------------------------------

(defn mkdir
  [{:keys [store now]} share path]
  (if-let [p (normalize-path path)]
    (let [coll (fs-coll share)]
      (cond
        (= p "") {:ok? false :error :kotobase.sftp/file-already-exists :path path}
        (some? (get-node store coll p)) {:ok? false :error :kotobase.sftp/file-already-exists :path path}
        :else
        (let [parent (get-node store coll (parent-path p))]
          (cond
            (nil? parent) {:ok? false :error :kotobase.sftp/no-such-file :path path}
            (not (dir? parent)) {:ok? false :error :kotobase.sftp/not-a-directory :path path}
            :else
            (do (st/-put store coll p {:type :dir :mtime now})
                (audit! store :mkdir share p)
                {:ok? true :path p})))))
    {:ok? false :error :kotobase.sftp/invalid-path :path path}))

(defn rmdir
  "Removes an EMPTY directory (SSH_FX_FAILURE-shaped
  :kotobase.sftp/directory-not-empty when it isn't — SFTP has no
  recursive-delete request). The share root can never be removed."
  [{:keys [store]} share path]
  (if-let [p (normalize-path path)]
    (let [coll (fs-coll share)]
      (cond
        (= p "") {:ok? false :error :kotobase.sftp/permission-denied :path path}
        :else
        (let [node (get-node store coll p)]
          (cond
            (nil? node) {:ok? false :error :kotobase.sftp/no-such-file :path path}
            (not (dir? node)) {:ok? false :error :kotobase.sftp/not-a-directory :path path}
            (seq (:entries (readdir {:store store} share p)))
            {:ok? false :error :kotobase.sftp/directory-not-empty :path path}
            :else
            (do (st/-put store coll p nil)
                (audit! store :rmdir share p)
                {:ok? true :path p})))))
    {:ok? false :error :kotobase.sftp/invalid-path :path path}))

;; ---------------------------------------------------------------------------
;; remove-file (SSH_FXP_REMOVE — files only, use rmdir for directories)
;; ---------------------------------------------------------------------------

(defn remove-file
  [{:keys [store]} share path]
  (if-let [p (normalize-path path)]
    (let [coll (fs-coll share)
          node (get-node store coll p)]
      (cond
        (= p "") {:ok? false :error :kotobase.sftp/permission-denied :path path}
        (nil? node) {:ok? false :error :kotobase.sftp/no-such-file :path path}
        (dir? node) {:ok? false :error :kotobase.sftp/is-a-directory :path path}
        :else
        (do (st/-put store coll p nil)
            (audit! store :remove share p)
            {:ok? true :path p})))
    {:ok? false :error :kotobase.sftp/invalid-path :path path}))

;; ---------------------------------------------------------------------------
;; rename (SSH_FXP_RENAME — moves a file, or a directory subtree)
;; ---------------------------------------------------------------------------

(defn rename
  "Move `from` to `to` within one share. Errors if `to` already exists
  (v0.1 does not implement the POSIX-rename-overwrite extension some real
  SFTP servers offer) or if `to`'s parent doesn't exist. Renaming a
  directory moves every descendant entry (a real subtree move, not a
  shallow single-key rewrite) — SFTP itself has no notion of a 'shallow'
  directory rename."
  [{:keys [store]} share from to]
  (let [pf (normalize-path from)
        pt (normalize-path to)]
    (cond
      (or (nil? pf) (nil? pt))
      {:ok? false :error :kotobase.sftp/invalid-path :path (if (nil? pf) from to)}

      (= pf "")
      {:ok? false :error :kotobase.sftp/permission-denied :path from}

      :else
      (let [coll (fs-coll share)
            src (get-node store coll pf)]
        (cond
          (nil? src) {:ok? false :error :kotobase.sftp/no-such-file :path from}

          (and (dir? src) (or (= pt pf) (str/starts-with? pt (str pf "/"))))
          {:ok? false :error :kotobase.sftp/invalid-path :path to}

          (some? (get-node store coll pt))
          {:ok? false :error :kotobase.sftp/file-already-exists :path to}

          (not (dir? (get-node store coll (parent-path pt))))
          {:ok? false :error :kotobase.sftp/no-such-file :path to}

          :else
          (do
            (doseq [k (if (dir? src)
                        (->> (st/-list store coll)
                             (filter #(or (= % pf) (str/starts-with? % (str pf "/")))))
                        [pf])]
              (let [node (st/-get store coll k)
                    new-key (str pt (subs k (count pf)))]
                (st/-put store coll new-key node)
                (st/-put store coll k nil)))
            (audit! store :rename share pf {:to pt})
            {:ok? true :from pf :to pt}))))))
