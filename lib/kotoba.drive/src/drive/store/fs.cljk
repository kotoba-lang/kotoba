(ns drive.store.fs
  "An `IObjectStore` on a filesystem.

  JVM only, on purpose. `cloud-itonami-app` needs Java 21 anyway, so a Node
  branch here would be a second implementation nothing runs and no test
  covers — worse than its absence, because it would read as supported.

  ## References are not paths

  A reference arrives from a caller and is used as a filename, so it is
  refused unless it looks like one: no separators, no `..`, no leading dot,
  and nothing outside a small alphabet. A store that concatenated an arbitrary
  reference onto a directory would let whoever chose the reference name any
  file on the disk — including one outside the workspace, and including one it
  could then be asked to delete."
  (:require [kotoba.lang.text :as str]
            #?(:clj [drive.object :as object]))
  #?(:clj (:import (java.io File)
                   (java.nio.file Files Path)
                   (java.nio.file.attribute FileAttribute))))

(def safe-reference
  "What a reference may look like when it is about to become a filename.

  Deliberately narrower than a filesystem allows: hashes, uuids and base32
  names all fit, and nothing that fits can escape a directory."
  #"[A-Za-z0-9][A-Za-z0-9._-]{0,254}")

(defn safe-reference?
  [ref]
  (boolean (and (string? ref)
                (re-matches safe-reference ref)
                (not (str/includes? ref "..")))))

#?(:clj
   (defn- resolve-ref ^Path [^String dir ref]
     (when-not (safe-reference? ref)
       (throw (ex-info "drive.store.fs: unsafe object reference" {:object-ref ref})))
     (.toPath (File. (File. dir) ^String ref))))

#?(:clj
   (defn store
     "A store rooted at `dir`, which is created if it does not exist."
     [^String dir]
     (Files/createDirectories (.toPath (File. dir))
                              (into-array FileAttribute []))
     (reify object/IObjectStore
       (-get-object [_ ref]
         (let [p (resolve-ref dir ref)]
           (when (Files/exists p (into-array java.nio.file.LinkOption []))
             (mapv #(bit-and (int %) 0xff) (Files/readAllBytes p)))))
       (-put-object [_ ref bytes]
         (Files/write (resolve-ref dir ref)
                      (byte-array (map unchecked-byte bytes))
                      (into-array java.nio.file.OpenOption []))
         nil)
       (-delete-object [_ ref]
         (Files/deleteIfExists (resolve-ref dir ref))
         nil)
       (-object-exists? [_ ref]
         (Files/exists (resolve-ref dir ref)
                       (into-array java.nio.file.LinkOption []))))))
