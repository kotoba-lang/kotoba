(ns zip.core
  "ZIP container read and write (PKWARE APPNOTE.TXT). Sketch (.sketch), OOXML
   (.docx/.xlsx/.pptx), ODF and EPUB are all ZIPs — this lists, extracts and
   builds them in pure `.cljc`, with `org-ietf-deflate` as its only dependency.

   Reading is driven by the central directory (never by scanning for local
   headers), which is what makes it agree with `unzip` on archives that have
   prepended data, and it understands the ZIP64 structures a >4 GiB or
   >65535-entry archive uses.

   Three things this reader is deliberately strict about, because the previous
   version was not and each is a silent-corruption path:

   - **Unsupported compression methods raise.** Methods 0 (stored), 8 (deflate)
     and 12 (bzip2) are implemented; LZMA, zstd, xz, PPMd and the AE-x encryption
     wrapper are not. Returning the *compressed* bytes as though they were the
     member's content — the old behaviour — hands a caller silent garbage.
   - **CRC-32 is verified** per member, along with the uncompressed size.
   - **Encrypted members raise** instead of yielding ciphertext.

   Extraction is separated from listing: `entries` reads the directory only, and
   `read-entry` decompresses one member. `parse` keeps the original eager
   behaviour (every member decompressed at once) for existing callers."
  (:require [bzip2.core :as bzip2]
            [kotoba.lang.text :as str]
            [deflate.core :as deflate]
            [zip.bytes :as b]
            [zip.write :as write]))

(def ^:private local-sig    0x04034b50)
(def ^:private central-sig  0x02014b50)
(def ^:private eocd-sig     0x06054b50)
(def ^:private eocd64-sig   0x06064b50)
(def ^:private locator-sig  0x07064b50)

(def ^:private max-u16 65535)
(def ^:private max-u32 4294967295)

(def method-names
  "APPNOTE 4.4.5. Only 0 and 8 are implemented; the rest exist so that an error
   can name what it found."
  {0 "stored" 1 "shrunk" 2 "reduced-1" 3 "reduced-2" 4 "reduced-3" 5 "reduced-4"
   6 "imploded" 8 "deflate" 9 "deflate64" 10 "pkware-implode" 12 "bzip2"
   14 "lzma" 16 "cmpsc" 18 "terse" 19 "lz77" 20 "zstd-deprecated" 93 "zstd"
   94 "mp3" 95 "xz" 96 "jpeg" 97 "wavpack" 98 "ppmd" 99 "ae-x-encryption"})

;; ---------------------------------------------------------------------------
;; End of central directory
;; ---------------------------------------------------------------------------

(defn- find-eocd
  "Scan backward for the end-of-central-directory signature. The archive comment
   can be up to 64 KiB, so the search is bounded by that rather than the whole
   file — a shorter scan than the old unbounded one, and it cannot mistake
   member data for a directory."
  [bv]
  (let [n (count bv)]
    (when (< n 22)
      (throw (ex-info "zip: shorter than an empty archive" {:reason :not-a-zip :length n})))
    (loop [i (- n 22)]
      (cond
        (or (neg? i) (< i (- n 22 max-u16)))
        (throw (ex-info "zip: no end-of-central-directory record (not a zip?)"
                        {:reason :not-a-zip}))

        (= (b/u32 bv i) eocd-sig) i
        :else (recur (dec i))))))

(defn- read-eocd [bv at]
  {:disk       (b/u16 bv (+ at 4))
   :cd-disk    (b/u16 bv (+ at 6))
   :count-disk (b/u16 bv (+ at 8))
   :count      (b/u16 bv (+ at 10))
   :cd-size    (b/u32 bv (+ at 12))
   :cd-offset  (b/u32 bv (+ at 16))
   :comment    (let [len (b/u16 bv (+ at 20))]
                 (when (pos? len)
                   (b/utf8->str (subvec bv (+ at 22) (min (count bv) (+ at 22 len))))))})

(defn- read-zip64
  "Follow the ZIP64 locator that sits immediately before the EOCD record and
   return the widened counts/offsets. Only consulted when a 32-bit field is
   saturated."
  [bv eocd-at eocd]
  (let [loc (- eocd-at 20)]
    (if (or (neg? loc) (not= (b/u32 bv loc) locator-sig))
      eocd
      (let [at (b/u64 bv (+ loc 8))]
        (when (or (neg? at) (> (+ at 56) (count bv)) (not= (b/u32 bv at) eocd64-sig))
          (throw (ex-info "zip: ZIP64 locator points at no ZIP64 directory record"
                          {:reason :bad-zip64 :offset at})))
        (assoc eocd
               :zip64?    true
               :count     (b/u64 bv (+ at 32))
               :cd-size   (b/u64 bv (+ at 40))
               :cd-offset (b/u64 bv (+ at 48)))))))

;; ---------------------------------------------------------------------------
;; Extra fields
;; ---------------------------------------------------------------------------

(defn- parse-extra
  "Split an extra-field block into `{id bytes}`. A malformed tail is ignored
   rather than fatal — writers do append junk."
  [bs]
  (let [n (count bs)]
    (loop [i 0 out {}]
      (if (> (+ i 4) n)
        out
        (let [id   (b/u16 bs i)
              size (b/u16 bs (+ i 2))
              end  (+ i 4 size)]
          (if (> end n)
            out
            (recur end (assoc out id (subvec bs (+ i 4) end)))))))))

(defn- apply-zip64-extra
  "Field 0x0001 carries whichever of size / compressed-size / local-offset had a
   saturated 32-bit slot, in that order."
  [extra size csize offset]
  (if-let [z (get extra 0x0001)]
    (loop [i 0
           [k & ks] [:size :csize :offset]
           acc {:size size :csize csize :offset offset}]
      (if (or (nil? k) (> (+ i 8) (count z)))
        acc
        (let [saturated? (= max-u32 (get acc k))]
          (if saturated?
            (recur (+ i 8) ks (assoc acc k (b/u64 z i)))
            (recur i ks acc)))))
    {:size size :csize csize :offset offset}))

;; ---------------------------------------------------------------------------
;; Listing
;; ---------------------------------------------------------------------------

(defn entries
  "Central-directory entries, metadata only — nothing is decompressed.

   Each entry: `:name :comment :method :method-name :size :compressed-size
   :crc32 :flags :encrypted? :dir? :mtime :offset` (local header offset)."
  [data]
  (let [bv       (vec data)
        eocd-at  (find-eocd bv)
        eocd     (read-eocd bv eocd-at)
        eocd     (if (or (= max-u16 (:count eocd))
                         (= max-u32 (:cd-offset eocd))
                         (= max-u32 (:cd-size eocd)))
                   (read-zip64 bv eocd-at eocd)
                   eocd)]
    (when (pos? (:disk eocd))
      (throw (ex-info "zip: split archives are not supported"
                      {:reason :split-archive :disk (:disk eocd)})))
    (loop [i 0 off (:cd-offset eocd) out []]
      (if (>= i (:count eocd))
        out
        (do
          (when (> (+ off 46) (count bv))
            (throw (ex-info "zip: central directory runs past the end of the archive"
                            {:reason :truncated :offset off})))
          (when-not (= (b/u32 bv off) central-sig)
            (throw (ex-info "zip: bad central directory signature"
                            {:reason :bad-central-header :offset off :index i})))
          (let [flags   (b/u16 bv (+ off 8))
                method  (b/u16 bv (+ off 10))
                nlen    (b/u16 bv (+ off 28))
                elen    (b/u16 bv (+ off 30))
                clen    (b/u16 bv (+ off 32))
                name-bs (subvec bv (+ off 46) (+ off 46 nlen))
                extra   (parse-extra (subvec bv (+ off 46 nlen) (+ off 46 nlen elen)))
                utf8?   (pos? (bit-and flags 0x0800))
                nm      (if utf8? (b/utf8->str name-bs) (b/bytes->ascii name-bs))
                widened (apply-zip64-extra extra
                                           (b/u32 bv (+ off 24))
                                           (b/u32 bv (+ off 20))
                                           (b/u32 bv (+ off 42)))]
            (recur (inc i)
                   (+ off 46 nlen elen clen)
                   (conj out {:name            nm
                              :comment         (when (pos? clen)
                                                 (b/utf8->str (subvec bv (+ off 46 nlen elen)
                                                                      (+ off 46 nlen elen clen))))
                              :method          method
                              :method-name     (get method-names method "unknown")
                              :size            (:size widened)
                              :compressed-size (:csize widened)
                              :crc32           (b/u32 bv (+ off 16))
                              :flags           flags
                              :encrypted?      (pos? (bit-and flags 0x0001))
                              :dir?            (str/ends-with? nm "/")
                              :mtime           (b/dos->map (b/u16 bv (+ off 14))
                                                           (b/u16 bv (+ off 12)))
                              :offset          (:offset widened)
                              :zip64?          (boolean (get extra 0x0001))}))))))))

(defn names [entries] (mapv :name entries))
(defn entry [entries name] (first (filter #(= (:name %) name) entries)))

;; ---------------------------------------------------------------------------
;; Extraction
;; ---------------------------------------------------------------------------

(defn read-entry
  "Decompress one entry (as returned by `entries`) → the entry with `:bytes`.

   Options: `:verify-crc` (default true), `:max-output` (passed to the
   inflater's compression-bomb ceiling)."
  ([data e] (read-entry data e nil))
  ([data e {:keys [verify-crc] :or {verify-crc true} :as opts}]
   (let [bv  (vec data)
         off (:offset e)]
     (when (:encrypted? e)
       (throw (ex-info "zip: encrypted members are not supported"
                       {:reason :encrypted :name (:name e)})))
     (when (> (+ off 30) (count bv))
       (throw (ex-info "zip: local header runs past the end of the archive"
                       {:reason :truncated :name (:name e) :offset off})))
     (when-not (= (b/u32 bv off) local-sig)
       (throw (ex-info "zip: bad local header signature"
                       {:reason :bad-local-header :name (:name e) :offset off})))
     (let [nlen    (b/u16 bv (+ off 26))
           elen    (b/u16 bv (+ off 28))
           data-at (+ off 30 nlen elen)
           csize   (:compressed-size e)]
       (when (> (+ data-at csize) (count bv))
         (throw (ex-info "zip: member data runs past the end of the archive"
                         {:reason :truncated :name (:name e)})))
       (let [raw (subvec bv data-at (+ data-at csize))
             out (case (int (:method e))
                   0 raw
                   8 (deflate/inflate-raw raw (select-keys opts [:max-output]))
                   ;; method 12: a bare bzip2 stream, BZh header and all
                   12 (bzip2/decompress raw (select-keys opts [:max-output]))
                   (throw (ex-info (str "zip: unsupported compression method: "
                                        (get method-names (:method e) "unknown"))
                                   {:reason :unsupported-method
                                    :method (:method e)
                                    :method-name (get method-names (:method e) "unknown")
                                    :name (:name e)})))]
         (when-not (= (count out) (:size e))
           (throw (ex-info "zip: member size does not match the directory"
                           {:reason :size-mismatch :name (:name e)
                            :expected (:size e) :actual (count out)})))
         (when verify-crc
           (let [actual (deflate/crc32 out)]
             (when-not (= actual (:crc32 e))
               (throw (ex-info "zip: member CRC-32 mismatch"
                               {:reason :checksum-mismatch :name (:name e)
                                :expected (:crc32 e) :actual actual})))))
         (assoc e :bytes out))))))

(defn parse
  "Every member with its decompressed bytes → `[{:name :method :size :bytes ...}]`.

   Directory entries yield an empty `:bytes`. This is the eager API the repo
   started with; prefer `entries` + `read-entry` for archives where you only need
   part of the content."
  ([data] (parse data nil))
  ([data opts]
   (let [bv (vec data)]
     (mapv (fn [e]
             (if (:dir? e)
               (assoc e :bytes [])
               (read-entry bv e opts)))
           (entries bv)))))

;; ---------------------------------------------------------------------------
;; Writing (see zip.write)
;; ---------------------------------------------------------------------------

(def build
  "Assemble a ZIP archive from `[{:name ... :bytes ...} ...]` — see `zip.write/build`."
  write/build)
