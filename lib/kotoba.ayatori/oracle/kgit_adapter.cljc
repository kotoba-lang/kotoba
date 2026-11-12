(ns oracle.kgit-adapter
  "kgit oracle: kotobase/awai-fs-shaped git over a content-addressed
  datom/block plane (one-shot measurement only).

  Blob/tree/commit semantics, in-process, zero spawn, digest-pinned
  verified reads (awai-fs discipline: every read recomputes the digest
  and fails closed on mismatch).

  Reuse decision (code first): the discovery seam is
  bonsai.git-object/frame+oid, bonsai.git-codec/encode-tree+encode-commit,
  arrangement/commit! (commit-DAG), prolly-tree/build-tree (index substrate).
  None fits directly: all are `.cljk` namespaces requiring kotoba.bytes,
  arrangement, multiformats (JVM/cljk loader chain), while this oracle must
  stay a dependency-free `.cljc` runnable under bb (clj) and nbb (cljs).
  So this file ports the minimal byte-exact framing (type SP size NUL body,
  SHA-1 OID) with platform SHA-1 primitives and documents the seam above.
  No silent fallback: hash primitive missing -> throw, never substitute.

  Oracle rules: lives under project-top `oracle/`, one-shot measurement.
  Never wire into CI, gates, builds, packaging, or execution paths.
  Scope is the bench harness + oracle only: never touches real VCS."
  (:require [clojure.string :as str]))

;; ---- platform sha1 + utf8 (fail closed when unavailable) ----

(defn- utf8-bytes
  [s]
  #?(:clj (.getBytes ^String (str s) "UTF-8")
     :cljs (.encode (js/TextEncoder.) (str s))
     :default (throw (ex-info "kgit: no utf8 primitive on this platform" {}))))

(defn- sha1-hex-of-bytes
  [bs]
  #?(:clj (let [md (java.security.MessageDigest/getInstance "SHA-1")]
            (.update md ^bytes bs)
            (let [sb (StringBuilder.)]
              (doseq [b (.digest md)]
                (.append sb (format "%02x" (bit-and (int b) 0xff))))
              (str sb)))
     :cljs (let [crypto (js/require "node:crypto")
                 h (.createHash crypto "sha1")]
             (.update h bs)
             (.digest h "hex"))
     :default (throw (ex-info "kgit: no sha1 primitive on this platform" {}))))

(defn- concat-bytes [a b]
  #?(:clj (let [out (byte-array (+ (alength ^bytes a) (alength ^bytes b)))]
            (System/arraycopy a 0 out 0 (alength ^bytes a))
            (System/arraycopy b 0 out (alength ^bytes a) (alength ^bytes b))
            out)
     :cljs (let [out (js/Uint8Array. (+ (.-length a) (.-length b)))]
              (.set out a 0)
              (.set out b (.-length a))
              out)
     :default (throw (ex-info "kgit: no bytes primitive on this platform" {}))))

(defn- bytes-length [bs]
  #?(:clj (alength ^bytes bs)
     :cljs (.-length bs)
     :default (throw (ex-info "kgit: no bytes primitive on this platform" {}))))

(def object-types #{"blob" "tree" "commit"})

(defn frame
  "Byte-exact git framing: `type SP decimal-size NUL body`."
  [type body-bytes]
  (when-not (contains? object-types type)
    (throw (ex-info "kgit: unsupported object type"
                    {:reason :invalid-type :type type})))
  (concat-bytes (utf8-bytes (str type " " (bytes-length body-bytes) "\u0000"))
                body-bytes))

(defn oid-of-framed
  "Lowercase 40-hex git SHA-1 OID of already-framed bytes."
  [framed]
  (sha1-hex-of-bytes framed))

(defn blob-oid
  "Git blob OID for string CONTENT (utf8)."
  [content]
  (oid-of-framed (frame "blob" (utf8-bytes (str content)))))

;; ---- tree / commit codecs (byte-exact, minimal) ----

(def tree-modes #{"100644" "100755" "120000" "160000" "40000"})

(defn- hex->bytes
  [hex]
  #?(:clj (let [n (/ (count hex) 2)
                out (byte-array n)]
            (dotimes [i n]
              (aset out i (unchecked-byte
                            (Integer/parseInt (subs hex (* 2 i) (+ 2 (* 2 i))) 16))))
            out)
     :cljs (let [n (/ (count hex) 2)
                 out (js/Uint8Array. n)]
              (dotimes [i n]
                (aset out i (js/parseInt (subs hex (* 2 i) (+ 2 (* 2 i))) 16)))
              out)
     :default (throw (ex-info "kgit: no bytes primitive on this platform" {}))))

(defn- tree-sort-key [{:keys [name mode]}]
  (str name (when (= mode "40000") "/")))

(defn encode-tree
  "Encode [{:mode :name :oid}] to the exact git tree body (bytes).
  OIDs are 40-hex SHA-1. Entries are canonical git-name sorted."
  [entries]
  (let [parts (for [{:keys [mode name oid]} (sort-by tree-sort-key entries)]
                (do
                  (when-not (contains? tree-modes mode)
                    (throw (ex-info "kgit: invalid tree mode"
                                    {:reason :invalid-mode :mode mode})))
                  (when-not (and (string? name) (not (str/blank? name))
                                 (not (str/includes? name "\u0000"))
                                 (not (str/includes? name "/")))
                    (throw (ex-info "kgit: invalid tree entry name"
                                    {:reason :invalid-name :name name})))
                  (when-not (and (string? oid) (re-matches #"[0-9a-f]{40}" oid))
                    (throw (ex-info "kgit: invalid tree entry OID"
                                    {:reason :invalid-oid :oid oid})))
                  (concat-bytes (utf8-bytes (str mode " " name "\u0000"))
                                (hex->bytes oid))))]
    (reduce concat-bytes #?(:clj (byte-array 0) :cljs (js/Uint8Array. 0)) parts)))

(defn encode-commit
  "Encode a typed git commit body (bytes). author/committer are exact git
  identity strings (`Name <mail> epoch tz`). parents is an OID vector
  (0/1/N, so merges are representable; no merge algorithm here)."
  [{:keys [tree parents author committer message]
    :or {parents [] message ""}}]
  (doseq [[label value] [["tree" tree] ["author" author] ["committer" committer]]]
    (when-not (and (string? value) (not (str/blank? value)))
      (throw (ex-info "kgit: missing commit field"
                      {:reason :missing-field :field label}))))
  (doseq [oid (cons tree parents)]
    (when-not (re-matches #"[0-9a-f]{40}" oid)
      (throw (ex-info "kgit: invalid commit OID"
                      {:reason :invalid-oid :oid oid}))))
  (utf8-bytes (str "tree " tree "\n"
                   (apply str (map #(str "parent " % "\n") parents))
                   "author " author "\n"
                   "committer " committer "\n"
                   "\n" message)))

;; ---- store: content-addressed block plane + path index ----

(defn make-store
  "Empty kgit store. Stats count 1 round trip per op; :spawns is always 0."
  ([] (make-store {}))
  ([_opts]
   (atom {:objects {}   ;; oid -> {:type :body-str :framed}
          :index {}     ;; path -> oid (the :fs/path index)
          :refs {}      ;; ref -> oid (mutable pointer over immutable DAG)
          :stats {:reads 0 :writes 0 :round-trips 0 :bytes 0 :spawns 0}})))

(defn- bump! [store k n-bytes]
  (swap! store update :stats
         (fn [st]
           (-> st
               (update :reads + (if (= k :reads) 1 0))
               (update :writes + (if (= k :writes) 1 0))
               (update :round-trips inc)
               (update :bytes + (or n-bytes 0))))))

(defn- store-object!
  "Store framed object, idempotent. Returns oid."
  [store type body-str framed]
  (let [oid (oid-of-framed framed)]
    (swap! store assoc-in [:objects oid]
           {:type type :body-str body-str :framed framed})
    oid))

(defn write-blob!
  "Write blob CONTENT (string), return its git OID. Idempotent."
  [store content]
  (let [text (str content)
        framed (frame "blob" (utf8-bytes text))
        oid (store-object! store "blob" text framed)]
    (bump! store :writes (count text))
    oid))

(defn read-blob
  "Read blob OID with digest-pinned verification. Fails closed on corruption."
  [store oid]
  (let [entry (get (:objects @store) oid)]
    (bump! store :reads 0)
    (when entry
      (let [recomputed (oid-of-framed (:framed entry))]
        (when-not (= recomputed oid)
          (throw (ex-info "kgit: OID verification failed"
                          {:reason :oid-mismatch :expected oid :actual recomputed})))
        (:body-str entry)))))

(defn write-tree!
  "Write a tree object from [{:mode :name :oid}], return its OID."
  [store entries]
  (let [body (encode-tree entries)
        framed (frame "tree" body)
        oid (store-object! store "tree" nil framed)]
    (bump! store :writes (bytes-length body))
    oid))

(defn write-commit!
  "Write a commit object, return its OID. parents vector 0/1/N."
  [store opts]
  (let [body (encode-commit opts)
        framed (frame "commit" body)
        oid (store-object! store "commit" nil framed)]
    (bump! store :writes (bytes-length body))
    oid))

(defn set-ref!
  "Move REF to OID (no ff check here; policy lives in bonsai.ref-policy)."
  [store ref oid]
  (swap! store assoc-in [:refs ref] oid)
  (bump! store :writes 0)
  nil)

(defn get-ref [store ref]
  (bump! store :reads 0)
  (get (:refs @store) ref))

;; ---- fs shape over the block plane (bench parity) ----

(defn- norm-path [p]
  (let [s (str p)]
    (when (str/includes? s "..")
      (throw (ex-info "kgit: path escapes root"
                      {:type :fs/escape :path s})))
    (when (str/blank? s)
      (throw (ex-info "kgit: empty path"
                      {:type :fs/empty-path :path s})))
    (str/replace s #"^/+" "")))

(defn fs-write!
  "Write CONTENT at PATH as a blob + path-index entry. Returns nil."
  [store path content]
  (let [p (norm-path path)
        text (str content)
        framed (frame "blob" (utf8-bytes text))
        oid (oid-of-framed framed)]
    (swap! store (fn [s]
                   (-> s
                       (assoc-in [:objects oid]
                                 {:type "blob" :body-str text :framed framed})
                       (assoc-in [:index p] oid))))
    (bump! store :writes (count text))
    nil))

(defn fs-read
  "Read PATH with digest-pinned verification, or nil when absent."
  [store path]
  (let [p (norm-path path)
        oid (get (:index @store) p)]
    (if (nil? oid)
      (do (bump! store :reads 0) nil)
      (let [entry (get (:objects @store) oid)]
        (when (nil? entry)
          (throw (ex-info "kgit: index points at missing object"
                          {:reason :missing-object :path p :oid oid})))
        (let [recomputed (oid-of-framed (:framed entry))]
          (when-not (= recomputed oid)
            (throw (ex-info "kgit: OID verification failed on read"
                            {:reason :oid-mismatch :path p
                             :expected oid :actual recomputed})))
          (bump! store :reads (count (:body-str entry)))
          (:body-str entry))))))

(defn fs-exists?
  [store path]
  (let [hit (contains? (:index @store) (norm-path path))]
    (bump! store :reads 0)
    hit))

(defn fs-list
  [store dir]
  (let [d (if (or (nil? dir) (str/blank? (str dir))) "" (norm-path (str dir)))
        prefix (if (= d "") "" (str d "/"))
        names (->> (keys (:index @store))
                   (filter #(str/starts-with? % prefix))
                   (map #(subs % (count prefix)))
                   (remove #(str/includes? % "/"))
                   (remove str/blank?)
                   (sort)
                   (vec))]
    (bump! store :reads 0)
    names))

(defn fs-delete!
  [store path]
  (swap! store update :index dissoc (norm-path path))
  (bump! store :writes 0)
  nil)

(defn blob-oid-for-path
  "Git blob OID currently indexed at PATH, or nil."
  [store path]
  (get (:index @store) (norm-path path)))

(defn stats [store]
  (assoc (:stats @store) :spawns 0))

(defn snapshot [store]
  (->> (:index @store)
       (map (fn [[p oid]] [p (get-in @store [:objects oid :body-str])]))
       (sort-by first)
       (vec)))
