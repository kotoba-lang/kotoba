(ns mail-archive.blob-store
  "Content-addressed blob storage: every raw artifact (the reconstructed source
  of an email, an attachment payload) is stored under its own sha256 hex digest
  (its `cid`), so the same bytes are stored once and referenced by content, never
  by a mutable path. This is the `:blob/*` half of the schema — `mail_archive.ingest`
  puts each raw message here and points `:email/blob` at the resulting cid.

  `BlobStore` is a portable protocol; the default `LocalDirBlobStore` (one file
  per blob, named by its cid, under a directory) is JVM-only, which is all the
  JVM-side ingest needs. sha256 hashing keeps the store immutable and idempotent:
  `put!`-ing identical bytes twice yields the same cid and writes the file once."
  #?(:clj (:require [clojure.java.io :as io]))
  #?(:clj (:import [java.security MessageDigest])))

(defprotocol BlobStore
  "Content-addressed byte storage. `cid` is the sha256 hex digest of the bytes."
  (put! [this bytes] "Store `bytes`, returning the cid (sha256 hex). Idempotent.")
  (get-bytes [this cid] "The stored bytes for `cid`, or nil if absent.")
  (exists? [this cid] "True when `cid` is already stored."))

#?(:clj
   (defn sha256-hex
     "Lowercase hex sha256 of a byte array — the content id (cid) for those bytes."
     ^String [^bytes bs]
     (let [digest (.digest (MessageDigest/getInstance "SHA-256") bs)
           sb (StringBuilder. (* 2 (alength digest)))]
       (doseq [b digest]
         (let [v (bit-and b 0xff)]
           (when (< v 16) (.append sb "0"))
           (.append sb (Integer/toString v 16))))
       (.toString sb))))

#?(:clj
   (defn- read-all-bytes ^bytes [^java.io.File f]
     (with-open [in (io/input-stream f)
                 out (java.io.ByteArrayOutputStream.)]
       (io/copy in out)
       (.toByteArray out))))

#?(:clj
   (defrecord LocalDirBlobStore [dir]
     BlobStore
     (put! [_ bytes]
       (let [cid (sha256-hex bytes)
             f (io/file dir cid)]
         (when-not (.exists f)
           (io/make-parents f)
           (with-open [out (io/output-stream f)]
             (.write out ^bytes bytes)))
         cid))
     (get-bytes [_ cid]
       (let [f (io/file dir cid)]
         (when (.exists f) (read-all-bytes f))))
     (exists? [_ cid]
       (.exists (io/file dir cid)))))

#?(:clj
   (defn local-dir-blob-store
     "A `BlobStore` writing one file per blob (named by cid) under `dir`."
     [dir]
     (->LocalDirBlobStore dir)))
