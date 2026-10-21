(ns kotoba.fs
  "Assembled from one repo per definition.

  This namespace holds no implementation. It re-exports the definitions
  that each live in their own repo, so a call site can require one name
  and a library can require only the definitions it actually uses.

  AN IMPLEMENTATION BUILT AGAINST kotoba.lang.fs IS NOT ACCEPTED HERE.
  kotoba.lang.fs still declares IAsyncFilesystem, IFilesystem, and a protocol split into its own
  repo is a DIFFERENT protocol from the one the source namespace declares
  (ADR-2609091900). Measured 2026-09-09 on kotoba.lang.fs: a filesystem
  reified against the source protocol answers through the source namespace
  and fails through this one -- No implementation of method: :exists?.
  Build the implementation against the repo that declares the protocol here,
  or call through kotoba.lang.fs.

  NOT re-exported here, on purpose: IAsyncFilesystem, IFilesystem. A protocol's identity is what extend-type and reify dispatch on,
  and a copy would make an implementation silently extend nothing, so the
  protocol name stays in the one repo that declares it. Requiring that repo
  is a compile error away; a copy would not be.

  Value vars are not re-exported either: sep. `(def x other/x)` copies, which is harmless for a function and makes
  with-redefs through this namespace a SILENT no-op for a value -- measured
  on kotoba.lang.edn, where three assertions passed against nothing at all.
  Require the repo that defines the value.
"
  (:refer-clojure :exclude [list read write])
  (:require [kotoba.fs.async-filesystem :as iasync-filesystem-ns]
            [kotoba.fs.filesystem :as ifilesystem-ns]
            [kotoba.fs.absolute :as absolute-ns]
            [kotoba.fs.basename :as basename-ns]
            [kotoba.fs.copy :as copy-ns]
            [kotoba.fs.dirname :as dirname-ns]
            [kotoba.fs.eventual-error-type :as eventual-error-type-ns]
            [kotoba.fs.ext :as ext-ns]
            [kotoba.fs.join :as join-ns]
            [kotoba.fs.mem-filesystem :as mem-filesystem-ns]
            [kotoba.fs.normalize :as normalize-ns]
            [kotoba.fs.relative :as relative-ns]
            [kotoba.fs.split :as split-ns]
            [kotoba.fs.utf8-bytes :as utf8-bytes-ns]
            [kotoba.fs.utf8-text :as utf8-text-ns]))

(def absolute? "See kotoba.fs.absolute/absolute?." absolute-ns/absolute?)
(def basename "See kotoba.fs.basename/basename." basename-ns/basename)
(def copy "See kotoba.fs.copy/copy." copy-ns/copy)
(def delete "See kotoba.fs.filesystem/delete." ifilesystem-ns/delete)
(def delete-async "See kotoba.fs.async-filesystem/delete-async." iasync-filesystem-ns/delete-async)
(def dirname "See kotoba.fs.dirname/dirname." dirname-ns/dirname)
(def eventual-error-type "See kotoba.fs.eventual-error-type/eventual-error-type." eventual-error-type-ns/eventual-error-type)
(def exists-async? "See kotoba.fs.async-filesystem/exists-async?." iasync-filesystem-ns/exists-async?)
(def exists? "See kotoba.fs.filesystem/exists?." ifilesystem-ns/exists?)
(def ext "See kotoba.fs.ext/ext." ext-ns/ext)
(def join "See kotoba.fs.join/join." join-ns/join)
(def list "See kotoba.fs.filesystem/list." ifilesystem-ns/list)
(def list-async "See kotoba.fs.async-filesystem/list-async." iasync-filesystem-ns/list-async)
(def mem-filesystem "See kotoba.fs.mem-filesystem/mem-filesystem." mem-filesystem-ns/mem-filesystem)
(def normalize "See kotoba.fs.normalize/normalize." normalize-ns/normalize)
(def read "See kotoba.fs.filesystem/read." ifilesystem-ns/read)
(def read-async "See kotoba.fs.async-filesystem/read-async." iasync-filesystem-ns/read-async)
(def read-bytes "See kotoba.fs.filesystem/read-bytes." ifilesystem-ns/read-bytes)
(def relative? "See kotoba.fs.relative/relative?." relative-ns/relative?)
(def split "See kotoba.fs.split/split." split-ns/split)
(def utf8-bytes "See kotoba.fs.utf8-bytes/utf8-bytes." utf8-bytes-ns/utf8-bytes)
(def utf8-text "See kotoba.fs.utf8-text/utf8-text." utf8-text-ns/utf8-text)
(def write "See kotoba.fs.filesystem/write." ifilesystem-ns/write)
(def write-async "See kotoba.fs.async-filesystem/write-async." iasync-filesystem-ns/write-async)
(def write-bytes "See kotoba.fs.filesystem/write-bytes." ifilesystem-ns/write-bytes)
