(ns xz.core
  "The .xz container (Tukaani's `xz-file-format.txt`) and the legacy .lzma
   \"alone\" format, over the LZMA/LZMA2 codec in `xz.lzma`.

   An .xz file is a sequence of streams; each stream is a header, some blocks,
   an index and a footer, and every structural field is CRC-32'd separately from
   the data, which itself carries a CRC-32, CRC-64 (the default) or SHA-256
   check. Verifying those is the point of the format, so it happens by default —
   including SHA-256, which comes from `org-nist-sha2`. A compression library
   still should not *contain* a hash implementation, which is why this one is a
   dependency and why `:sha256` remains an injection point for a caller with its
   own. `:verify-check false` is available for salvage.

   Reading: full LZMA2 support, the Delta filter, multi-stream files and stream
   padding. The BCJ branch-conversion filters (x86, ARM, …) are recognised and
   refused by name rather than silently mis-decoded.

   Writing: valid .xz whose LZMA2 chunks are *uncompressed*. That is a real,
   conformant .xz file — `xz -d` and `xz -t` accept it, which the suite asserts —
   but it does not compress. An LZMA encoder worth using needs the optimal-parse
   price model, and shipping a bad one would be worse than shipping none: callers
   who want size should reach for `org-ietf-deflate`'s gzip, and callers who need
   *the .xz container* (a 7z folder, a signed artefact, a tool that only accepts
   .xz) get correct bytes today."
  (:require [deflate.core :as deflate]
            [sha2.core :as sha2]
            [xz.crc64 :as crc64]
            [xz.lzma :as lzma]))

(def ^:private stream-magic [0xfd 0x37 0x7a 0x58 0x5a 0x00])
(def ^:private footer-magic [0x59 0x5a])

(def check-types
  {0 :none 1 :crc32 4 :crc64 10 :sha256})

(def ^:private check-sizes
  {:none 0 :crc32 4 :crc64 8 :sha256 32})

(def filter-ids
  "Filter IDs from the .xz spec. Only LZMA2 and Delta are implemented; the rest
   exist so a refusal can name what it found."
  {0x21 :lzma2 0x03 :delta
   0x04 :bcj-x86 0x05 :bcj-powerpc 0x06 :bcj-ia64 0x07 :bcj-arm
   0x08 :bcj-armthumb 0x09 :bcj-sparc 0x0a :bcj-arm64 0x0b :bcj-riscv})

;; ---------------------------------------------------------------------------
;; Primitives
;; ---------------------------------------------------------------------------

(defn- u32le [v o]
  (+ (nth v o) (* 256 (nth v (+ o 1))) (* 65536 (nth v (+ o 2))) (* 16777216 (nth v (+ o 3)))))

(defn- read-vli
  "A variable-length integer: 7 bits per byte, little-endian, high bit = more."
  [v pos]
  (loop [p pos acc 0 mult 1 i 0]
    (when (>= p (count v))
      (throw (ex-info "xz: truncated variable-length integer" {:reason :truncated :pos pos})))
    (when (> i 8)
      (throw (ex-info "xz: variable-length integer longer than 9 bytes"
                      {:reason :bad-vli :pos pos})))
    (let [b   (nth v p)
          acc (+ acc (* (bit-and b 0x7f) mult))]
      (when (> acc 9007199254740991)
        (throw (ex-info "xz: value beyond exact integer range" {:reason :too-large})))
      (if (zero? (bit-and b 0x80))
        [acc (inc p)]
        (recur (inc p) acc (* mult 128) (inc i))))))

(defn- vli
  "Encode a variable-length integer."
  [n]
  (loop [n n out []]
    (if (< n 128)
      (conj out n)
      (recur (quot n 128) (conj out (bit-or 0x80 (bit-and n 0x7f)))))))

(defn- u32le-bytes [n]
  [(bit-and n 0xff)
   (bit-and (unsigned-bit-shift-right n 8) 0xff)
   (bit-and (unsigned-bit-shift-right n 16) 0xff)
   (bit-and (unsigned-bit-shift-right n 24) 0xff)])

(defn- pad4
  "Zero padding up to a multiple of four — the alignment .xz keeps everywhere."
  [n]
  (mod (- 4 (mod n 4)) 4))

(defn- dict-size-from-props
  "LZMA2 filter properties: a 6-bit code for the dictionary size."
  [p]
  (let [v (bit-and p 0x3f)]
    (when (> v 40)
      (throw (ex-info "xz: invalid LZMA2 dictionary size code"
                      {:reason :bad-filter-props :code v})))
    (if (= v 40)
      4294967295
      (* (bit-or 2 (bit-and v 1)) (bit-shift-left 1 (+ (quot v 2) 11))))))

(defn- props-from-dict-size
  "The smallest properties code whose dictionary is at least `n`."
  [n]
  (loop [v 0]
    (cond (> v 40) 40
          (>= (dict-size-from-props v) n) v
          :else (recur (inc v)))))

;; ---------------------------------------------------------------------------
;; Filters
;; ---------------------------------------------------------------------------

(defn- delta-decode
  "The Delta filter, decode direction: each byte is a difference from the byte
   `distance` back in the *decoded* output."
  [bytes distance]
  (let [v (vec bytes)]
    (persistent!
     (loop [i 0 out (transient [])]
       (if (>= i (count v))
         out
         (let [prev (if (>= (- i distance) 0) (nth out (- i distance)) 0)]
           (recur (inc i) (conj! out (bit-and (+ (nth v i) prev) 0xff)))))))))

(defn- apply-filters
  "Run the decoded block data back through the filter chain, outermost last.
   The chain is stored in encode order, so decoding walks it in reverse."
  [data filters]
  (reduce (fn [d {:keys [id props]}]
            (case (get filter-ids id)
              :delta (delta-decode d (inc (first props)))
              :lzma2 d                                     ; already decoded
              (throw (ex-info (str "xz: unsupported filter: "
                                   (name (get filter-ids id :unknown)))
                              {:reason :unsupported-filter :filter-id id
                               :filter (get filter-ids id :unknown)}))))
          data
          (reverse (remove #(= :lzma2 (get filter-ids (:id %))) filters))))

;; ---------------------------------------------------------------------------
;; Reading
;; ---------------------------------------------------------------------------

(defn- read-block-header [v pos]
  (let [size-byte (nth v pos)
        total     (* 4 (inc size-byte))
        end       (+ pos total)]
    (when (> end (count v))
      (throw (ex-info "xz: block header runs past the end" {:reason :truncated :pos pos})))
    (let [stored-crc (u32le v (- end 4))
          actual     (deflate/crc32 (subvec v pos (- end 4)))]
      (when-not (= stored-crc actual)
        (throw (ex-info "xz: block header CRC-32 mismatch"
                        {:reason :checksum-mismatch :expected stored-crc :actual actual}))))
    (let [flags     (nth v (inc pos))
          nfilters  (inc (bit-and flags 0x03))
          _         (when (pos? (bit-and flags 0x3c))
                      (throw (ex-info "xz: reserved block flags are set"
                                      {:reason :bad-block-header :flags flags})))
          p         (+ pos 2)
          [csize p] (if (pos? (bit-and flags 0x40)) (read-vli v p) [nil p])
          [usize p] (if (pos? (bit-and flags 0x80)) (read-vli v p) [nil p])
          [filters p]
          (loop [i 0 p p acc []]
            (if (= i nfilters)
              [acc p]
              (let [[id p]   (read-vli v p)
                    [psz p]  (read-vli v p)
                    props    (subvec v p (+ p psz))]
                (recur (inc i) (+ p psz) (conj acc {:id id :props props})))))]
      (doseq [b (subvec v p (- end 4))]
        (when-not (zero? b)
          (throw (ex-info "xz: block header padding is not zero"
                          {:reason :bad-block-header}))))
      {:header-size total
       :flags flags
       :compressed-size csize
       :uncompressed-size usize
       :filters filters
       :data-start end})))

(defn- verify-check! [check data v pos {:keys [verify-check sha256]
                                        :or {verify-check true}}]
  (let [size (get check-sizes check)]
    (when (and verify-check (pos? size))
      (let [stored (subvec v pos (+ pos size))]
        (case check
          :crc32 (let [want (u32le v pos)
                       got  (deflate/crc32 data)]
                   (when-not (= want got)
                     (throw (ex-info "xz: block CRC-32 mismatch"
                                     {:reason :checksum-mismatch :expected want :actual got}))))
          :crc64 (let [got (crc64/->le-bytes (crc64/crc64 data))]
                   (when-not (= (vec stored) got)
                     (throw (ex-info "xz: block CRC-64 mismatch"
                                     {:reason :checksum-mismatch}))))
          ;; org-nist-sha2 by default; `:sha256` overrides it for a caller that
          ;; already has one (a native binding, say) and wants it used here too
          :sha256 (let [got (vec ((or sha256 sha2/sha256) data))]
                    (when-not (= (vec stored) got)
                      (throw (ex-info "xz: block SHA-256 mismatch"
                                      {:reason :checksum-mismatch}))))
          nil)))
    size))

(defn- read-stream
  "One .xz stream starting at `pos`. Returns the decoded bytes and where the
   stream ended."
  [v pos opts]
  (when (> (+ pos 12) (count v))
    (throw (ex-info "xz: shorter than a stream header" {:reason :truncated :pos pos})))
  (when-not (= stream-magic (vec (subvec v pos (+ pos 6))))
    (throw (ex-info "xz: bad stream magic" {:reason :not-xz :pos pos})))
  (let [flags (subvec v (+ pos 6) (+ pos 8))
        want  (u32le v (+ pos 8))
        got   (deflate/crc32 flags)]
    (when-not (= want got)
      (throw (ex-info "xz: stream flags CRC-32 mismatch"
                      {:reason :checksum-mismatch :expected want :actual got})))
    (when-not (zero? (nth flags 0))
      (throw (ex-info "xz: reserved stream flag byte is not zero"
                      {:reason :bad-stream-header})))
    (let [check-id (bit-and (nth flags 1) 0x0f)
          check    (get check-types check-id)]
      (when (or (nil? check) (pos? (bit-and (nth flags 1) 0xf0)))
        (throw (ex-info "xz: unknown check type"
                        {:reason :unsupported-check :check-id check-id})))
      (loop [p (+ pos 12) blocks [] out []]
        (if (zero? (nth v p))
          ;; Index, then footer.
          (let [index-start p
                [nrecords p2] (read-vli v (inc p))
                [records p3]
                (loop [i 0 p p2 acc []]
                  (if (= i nrecords)
                    [acc p]
                    (let [[unpadded p] (read-vli v p)
                          [usize p]    (read-vli v p)]
                      (recur (inc i) p (conj acc {:unpadded unpadded :uncompressed usize})))))
                p3        (loop [p p3] (if (zero? (mod (- p index-start) 4)) p (recur (inc p))))
                index-crc (u32le v p3)
                actual    (deflate/crc32 (subvec v index-start p3))
                _         (when-not (= index-crc actual)
                            (throw (ex-info "xz: index CRC-32 mismatch"
                                            {:reason :checksum-mismatch})))
                index-end (+ p3 4)
                footer    index-end]
            (when (> (+ footer 12) (count v))
              (throw (ex-info "xz: missing stream footer" {:reason :truncated})))
            (when-not (= footer-magic (vec (subvec v (+ footer 10) (+ footer 12))))
              (throw (ex-info "xz: bad footer magic" {:reason :bad-footer})))
            (let [fcrc  (u32le v footer)
                  facts (deflate/crc32 (subvec v (+ footer 4) (+ footer 10)))]
              (when-not (= fcrc facts)
                (throw (ex-info "xz: footer CRC-32 mismatch" {:reason :checksum-mismatch})))
              (let [backward (* 4 (inc (u32le v (+ footer 4))))]
                (when-not (= backward (- index-end index-start))
                  (throw (ex-info "xz: footer backward size does not match the index"
                                  {:reason :bad-footer :declared backward
                                   :actual (- index-end index-start)})))))
            (when-not (= (count records) (count blocks))
              (throw (ex-info "xz: index does not list every block"
                              {:reason :bad-index :records (count records)
                               :blocks (count blocks)})))
            (doseq [[r b] (map vector records blocks)]
              (when-not (= (:uncompressed r) (:uncompressed-size b))
                (throw (ex-info "xz: index disagrees with a block's uncompressed size"
                                {:reason :bad-index}))))
            {:bytes out :end (+ footer 12) :check check :blocks blocks :records records})

          ;; A block.
          (let [h        (read-block-header v p)
                dict     (some (fn [{:keys [id props]}]
                                 (when (= :lzma2 (get filter-ids id))
                                   (dict-size-from-props (first props))))
                               (:filters h))
                _        (when-not dict
                           (throw (ex-info "xz: block has no LZMA2 filter"
                                           {:reason :unsupported-filter
                                            :filters (mapv #(get filter-ids (:id %) (:id %))
                                                           (:filters h))})))
                res      (lzma/decompress-lzma2 v (:data-start h)
                                                {:dict-size dict
                                                 :max-output (:max-output opts)})
                data     (apply-filters (:bytes res) (:filters h))
                comp-len (- (:end res) (:data-start h))
                _        (when (and (:compressed-size h) (not= (:compressed-size h) comp-len))
                           (throw (ex-info "xz: block compressed size does not match the header"
                                           {:reason :size-mismatch
                                            :declared (:compressed-size h) :actual comp-len})))
                _        (when (and (:uncompressed-size h) (not= (:uncompressed-size h) (count data)))
                           (throw (ex-info "xz: block uncompressed size does not match the header"
                                           {:reason :size-mismatch})))
                after    (+ (:end res) (pad4 comp-len))
                csize    (verify-check! check data v after opts)]
            (recur (+ after csize)
                   (conj blocks {:uncompressed-size (count data)
                                 :compressed-size comp-len
                                 :unpadded (+ (:header-size h) comp-len csize)
                                 :filters (mapv #(get filter-ids (:id %) (:id %)) (:filters h))})
                   (into out data))))))))

(defn streams
  "Per-stream metadata for an .xz file: check type, blocks, index records."
  ([data] (streams data nil))
  ([data opts]
   (let [v (vec data)]
     (loop [pos 0 acc []]
       (if (>= pos (count v))
         acc
         ;; Streams may be separated by zero padding, always a multiple of four.
         (if (zero? (nth v pos))
           (recur (inc pos) acc)
           (let [s (read-stream v pos opts)]
             (recur (:end s) (conj acc (dissoc s :bytes))))))))))

(defn decompress
  "Decompress an .xz file (every stream, concatenated) → vector of unsigned bytes.

   Options: `:verify-check` (default true), `:max-output`, `:sha256` (a function
   from bytes to 32 bytes, overriding the bundled one)."
  ([data] (decompress data nil))
  ([data opts]
   (let [v (vec data)]
     (loop [pos 0 out []]
       (if (>= pos (count v))
         out
         (if (zero? (nth v pos))
           (recur (inc pos) out)
           (let [s (read-stream v pos opts)]
             (recur (:end s) (into out (:bytes s))))))))))

(defn decompress-alone
  "Decompress the legacy .lzma (\"alone\") format: a 13-byte header — properties,
   dictionary size, uncompressed size or 0xFFFFFFFFFFFFFFFF for unknown — then a
   raw LZMA1 stream."
  ([data] (decompress-alone data nil))
  ([data _opts]
   (let [v (vec data)]
     (when (< (count v) 13)
       (throw (ex-info "lzma: shorter than an alone header" {:reason :truncated})))
     (let [props (nth v 0)
           dict  (u32le v 1)
           lo    (u32le v 5)
           hi    (u32le v 9)
           size  (if (and (= lo 4294967295) (= hi 4294967295))
                   nil
                   (+ lo (* hi 4294967296)))]
       (:bytes (lzma/decompress-lzma1 v 13 {:props props
                                            :unpacked-size size
                                            :dict-size (max dict 4096)}))))))

;; ---------------------------------------------------------------------------
;; Writing
;; ---------------------------------------------------------------------------

(def ^:private max-uncompressed-chunk 65536)

(defn lzma2-uncompressed
  "A raw LZMA2 stream carrying `data` in uncompressed chunks. Valid LZMA2 that
   any decoder reads; it just does not compress. Also what `xz.core/compress` and
   `org-7-zip-7z`'s writer use."
  [data]
  (let [v (vec data)
        n (count v)]
    (loop [pos 0 out [] first? true]
      (if (>= pos n)
        (conj out 0x00)                                    ; end of LZMA2
        (let [size (min max-uncompressed-chunk (- n pos))]
          (recur (+ pos size)
                 (-> out
                     (conj (if first? 0x01 0x02))          ; 0x01 also resets the dictionary
                     (conj (bit-and (unsigned-bit-shift-right (dec size) 8) 0xff))
                     (conj (bit-and (dec size) 0xff))
                     (into (subvec v pos (+ pos size))))
                 false))))))

(defn compress
  "Write `data` as a single-block, single-stream .xz file.

   The LZMA2 chunks are uncompressed (see the namespace docstring), so the output
   is larger than the input by the framing — but it is a conformant .xz that
   `xz -d` and `xz -t` accept.

   Options: `:check` — `:crc64` (default, what xz itself uses), `:crc32`,
   `:none`."
  ([data] (compress data nil))
  ([data {:keys [check] :or {check :crc64}}]
   (let [v          (vec data)
         check-id   (or (some (fn [[k x]] (when (= x check) k)) check-types)
                        (throw (ex-info "xz: unknown check type" {:reason :bad-argument :check check})))
         flags      [0x00 check-id]
         payload    (lzma2-uncompressed v)
         dict-props (props-from-dict-size (max 4096 (min (count v) 4194304)))
         ;; Block header: size byte, flags, filter flags (LZMA2 + 1 prop byte),
         ;; padding to a multiple of four, CRC-32.
         ;; Block flags: bits 0-1 hold (number of filters - 1), so one filter is
         ;; 0x00 — not 0x01, and definitely not the filter count itself.
         hdr-body   (into [0x00]
                          (into (vli 0x21) (into (vli 1) [dict-props])))
         raw-len    (+ 1 (count hdr-body) 4)
         hdr-total  (* 4 (quot (+ raw-len 3) 4))
         padding    (- hdr-total raw-len)
         hdr-front  (into [(dec (quot hdr-total 4))] (into hdr-body (repeat padding 0)))
         block-hdr  (into hdr-front (u32le-bytes (deflate/crc32 hdr-front)))
         check-bs   (case check
                      :none []
                      :crc32 (u32le-bytes (deflate/crc32 v))
                      :crc64 (crc64/->le-bytes (crc64/crc64 v)))
         unpadded   (+ (count block-hdr) (count payload) (count check-bs))
         block      (-> block-hdr
                        (into payload)
                        (into (repeat (pad4 (count payload)) 0))
                        (into check-bs))
         index-body (into [0x00] (into (vli 1) (into (vli unpadded) (vli (count v)))))
         index-body (into index-body (repeat (pad4 (count index-body)) 0))
         index      (into index-body (u32le-bytes (deflate/crc32 index-body)))
         backward   (dec (quot (count index) 4))
         footer-mid (into (u32le-bytes backward) flags)
         footer     (into (into (u32le-bytes (deflate/crc32 footer-mid)) footer-mid) footer-magic)]
     (-> (vec stream-magic)
         (into flags)
         (into (u32le-bytes (deflate/crc32 flags)))
         (into block)
         (into index)
         (into footer)))))
