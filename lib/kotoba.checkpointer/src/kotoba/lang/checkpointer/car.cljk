(ns kotoba.lang.checkpointer.car
  "CAR v1 file writer -- varint-length-prefixed dag-cbor header + a stream of
  varint-length-prefixed (CID-bytes ++ content-bytes) blocks, ported from
  @atproto/repo's `src/car.ts` (`writeCarStream`/`blocksToCarFile`). The
  length-prefix varint is the standard unsigned LEB128 the `varint` npm
  package (and `multiformats.core/varint`) both implement -- reused as-is,
  no CAR-specific quirks.

  Portability: `.cljc`, whole-file `#?(:clj (do ...))`-wrapped with a
  throwing `:cljs` stub, matching `kotoba.lang.checkpointer.dagcbor` (same
  file, same rationale): `blocks->car-bytes` calls `cbor/encode` and
  `multiformats.core/varint`/`cid->bytes`, which are themselves `:clj`-only
  (content-addressing bytes, per that namespace's own documented decision),
  so a genuine cljs CAR writer is blocked upstream regardless of this
  namespace's own (JVM `ByteArrayOutputStream`-based) implementation."
  #?(:clj (:require [kotoba.lang.checkpointer.dagcbor :as cbor]
                    [kotoba.lang.checkpointer.blockmap :as bm]
                    [multiformats.core :as mf]))
  #?(:clj (:import (java.io ByteArrayOutputStream))))

#?(:clj
(do

(defn- car-header-bytes ^bytes [root-cid]
  (cbor/encode {:version 1 :roots (if root-cid [(cbor/cid-link root-cid)] [])}))

(defn blocks->car-bytes
  "root-cid: a CID string, or nil for a rootless CAR. blockmap: a
  kotoba.lang.checkpointer.blockmap/BlockMap, written in its insertion
  order (matches `blocksToCarFile`'s block ordering exactly)."
  ^bytes [root-cid blockmap]
  (let [o (ByteArrayOutputStream.)
        ^bytes header (car-header-bytes root-cid)]
    (.write o ^bytes (mf/varint (alength header)))
    (.write o header)
    (doseq [[cid content] (bm/bm-entries blockmap)]
      (let [^bytes cid-bytes (mf/cid->bytes cid)
            ^bytes content-bytes content
            len (+ (alength cid-bytes) (alength content-bytes))]
        (.write o ^bytes (mf/varint len))
        (.write o cid-bytes)
        (.write o content-bytes)))
    (.toByteArray o)))

)) ;; end #?(:clj (do …))

#?(:cljs
(defn blocks->car-bytes [& _]
  (throw (ex-info (str "kotoba.lang.checkpointer.car/blocks->car-bytes is :clj-only "
                       "(CAR writer, downstream of :clj-only dagcbor/multiformats content addressing)")
                  {}))))
