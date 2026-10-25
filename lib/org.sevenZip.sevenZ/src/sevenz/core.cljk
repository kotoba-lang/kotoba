(ns sevenz.core
  "The .7z container (Igor Pavlov's `7zFormat.txt`, as shipped with the LZMA SDK)
   — reading, plus a Copy-coder writer. Portable `.cljc`.

   .7z is the most structurally involved of the common archive formats, for two
   reasons:

   1. **The header is usually itself compressed.** A `kEncodedHeader` at the end
      of the file describes a packed stream which, once decoded, *is* the real
      header. So a reader has to run the codec machinery before it can find out
      what is in the archive.
   2. **Folders are coder graphs, not files.** Members ('substreams') are cut out
      of a folder's decoded output, and a folder may chain several coders through
      bind pairs (a filter feeding a compressor). Sizes and CRCs live in three
      different places — pack info, unpack info, substreams info — and the
      reader has to agree with all of them.

   Namespaces are `sevenz.*` rather than `7z.*` because a Clojure symbol cannot
   start with a digit; the repo keeps the reverse-domain name `org-7-zip-7z`.

   Coders implemented: Copy, LZMA1, LZMA2, Delta and Deflate. Everything else —
   BCJ/BCJ2 branch conversion, AES-256, PPMd, BZip2, ARM64/RISC-V filters — is
   recognised and refused **by name**, because returning undecoded bytes as a
   member's content is the failure mode this repo exists to avoid."
  (:require [bzip2.core :as bzip2]
            [deflate.core :as deflate]
            [xz.lzma :as lzma]))

(def signature [0x37 0x7a 0xbc 0xaf 0x27 0x1c])

;; Property IDs (7zFormat.txt)
(def ^:private k-end 0x00)
(def ^:private k-header 0x01)
(def ^:private k-archive-properties 0x02)
(def ^:private k-additional-streams 0x03)
(def ^:private k-main-streams 0x04)
(def ^:private k-files-info 0x05)
(def ^:private k-pack-info 0x06)
(def ^:private k-unpack-info 0x07)
(def ^:private k-substreams-info 0x08)
(def ^:private k-size 0x09)
(def ^:private k-crc 0x0a)
(def ^:private k-folder 0x0b)
(def ^:private k-coders-unpack-size 0x0c)
(def ^:private k-num-unpack-stream 0x0d)
(def ^:private k-empty-stream 0x0e)
(def ^:private k-empty-file 0x0f)
(def ^:private k-anti 0x10)
(def ^:private k-name 0x11)
(def ^:private k-ctime 0x12)
(def ^:private k-atime 0x13)
(def ^:private k-mtime 0x14)
(def ^:private k-attributes 0x15)
(def ^:private k-encoded-header 0x17)
;; kDummy (0x19) is padding a writer may insert; the FilesInfo loop skips any
;; unknown property by its declared size, so it needs no special case.

(def coder-names
  "Coder IDs as they appear in a folder. Copy, LZMA1/2, Delta, Deflate and BZip2
   are decoded; the rest are refused by name."
  {[0x00]           :copy
   [0x21]           :lzma2
   [0x03 0x01 0x01] :lzma1
   [0x03]           :delta
   [0x04 0x01 0x08] :deflate
   [0x04 0x02 0x02] :bzip2
   [0x03 0x04 0x01] :ppmd
   [0x03 0x03 0x01 0x03] :bcj-x86
   [0x03 0x03 0x01 0x1b] :bcj2
   [0x04 0x01 0x09] :deflate64
   [0x06 0xf1 0x07 0x01] :aes-256-sha-256
   [0x0a]           :arm64
   [0x0b]           :riscv})

;; ---------------------------------------------------------------------------
;; Cursor over the header bytes
;; ---------------------------------------------------------------------------

(defn- index-of [coll x]
  (first (keep-indexed (fn [i v] (when (= v x) i)) coll)))

(defn- cursor [v pos] {:v v :pos (volatile! pos)})

(defn- rd8 [c]
  (let [p @(:pos c)]
    (when (>= p (count (:v c)))
      (throw (ex-info "7z: header ends unexpectedly" {:reason :truncated :pos p})))
    (vreset! (:pos c) (inc p))
    (nth (:v c) p)))

(defn- rd-bytes [c n]
  (let [p @(:pos c)]
    (when (> (+ p n) (count (:v c)))
      (throw (ex-info "7z: header ends unexpectedly" {:reason :truncated :pos p})))
    (vreset! (:pos c) (+ p n))
    (subvec (:v c) p (+ p n))))

(defn- rd-number
  "7z's variable-length number: the leading byte's high bits say how many extra
   little-endian bytes follow, and its remaining low bits are the high part."
  [c]
  (let [first-byte (rd8 c)]
    ;; Integer arithmetic with a running multiplier, not `Math/pow`: a double
    ;; result would make every size a float and `=` against an integer false.
    (loop [i 0 mask 0x80 value 0 mult 1]
      (cond
        (= i 8) value
        (zero? (bit-and first-byte mask))
        (+ value (* (bit-and first-byte (dec mask)) mult))
        :else
        (let [b (rd8 c)]
          (recur (inc i) (unsigned-bit-shift-right mask 1)
                 (+ value (* b mult)) (* mult 256)))))))

(defn- rd-num
  "`rd-number`, refusing values a JavaScript runtime cannot represent exactly."
  [c]
  (let [n (rd-number c)]
    (when (> n 9007199254740991)
      (throw (ex-info "7z: number beyond exact integer range" {:reason :too-large})))
    n))

(defn- rd-u32 [c]
  (let [b (rd-bytes c 4)]
    (+ (nth b 0) (* 256 (nth b 1)) (* 65536 (nth b 2)) (* 16777216 (nth b 3)))))

(defn- rd-u64 [c]
  (let [lo (rd-u32 c) hi (rd-u32 c)]
    (when (> hi 2097151)
      (throw (ex-info "7z: 64-bit value beyond exact integer range" {:reason :too-large})))
    (+ lo (* hi 4294967296))))

(defn- rd-filetime
  "A Windows FILETIME (100-nanosecond ticks since 1601) → Unix seconds.

   Read as a double deliberately: the raw value is ~1.3e17, past the exact
   integer range, and refusing it (as `rd-u64` does for structural fields) would
   make every 7-Zip archive unreadable because 7-Zip always records mtime. A
   microsecond of rounding in a timestamp is not a correctness problem; a
   silently wrong *offset* would be, which is why only this one is lossy."
  [c]
  (let [lo (rd-u32 c)
        hi (rd-u32 c)
        ft (+ lo (* hi 4294967296.0))]
    ;; `long` does not exist in ClojureScript, and the value is already integral.
    #?(:clj (long (Math/floor (/ (- ft 116444736000000000) 10000000)))
       :cljs (Math/floor (/ (- ft 116444736000000000) 10000000)))))

(defn- rd-bit-vector
  "`n` bits, most significant bit of each byte first."
  [c n]
  (loop [i 0 b 0 mask 0 out []]
    (if (= i n)
      out
      (let [[b mask] (if (zero? mask) [(rd8 c) 0x80] [b mask])]
        (recur (inc i) b (unsigned-bit-shift-right mask 1)
               (conj out (pos? (bit-and b mask))))))))

(defn- rd-bool-vector
  "A bit vector preceded by an 'all defined' byte."
  [c n]
  (if (pos? (rd8 c))
    (vec (repeat n true))
    (rd-bit-vector c n)))

;; ---------------------------------------------------------------------------
;; StreamsInfo
;; ---------------------------------------------------------------------------

(defn- read-folder [c]
  (let [num-coders (rd-num c)
        coders (vec (for [_ (range num-coders)]
                      (let [flags    (rd8 c)
                            id-size  (bit-and flags 0x0f)
                            id       (vec (rd-bytes c id-size))
                            complex? (pos? (bit-and flags 0x10))
                            attrs?   (pos? (bit-and flags 0x20))
                            [nin nout] (if complex? [(rd-num c) (rd-num c)] [1 1])
                            props    (when attrs? (vec (rd-bytes c (rd-num c))))]
                        (when (pos? (bit-and flags 0x80))
                          (throw (ex-info "7z: alternative-methods flag is not supported"
                                          {:reason :unsupported-coder :flags flags})))
                        {:id id :coder (get coder-names id :unknown)
                         :num-in nin :num-out nout :props props})))
        total-in  (reduce + (map :num-in coders))
        total-out (reduce + (map :num-out coders))
        bind-pairs (vec (for [_ (range (dec total-out))]
                          {:in (rd-num c) :out (rd-num c)}))
        num-packed (- total-in (count bind-pairs))
        packed-indices (if (= 1 num-packed)
                         ;; the single unbound input stream
                         [(first (remove (set (map :in bind-pairs)) (range total-in)))]
                         (vec (for [_ (range num-packed)] (rd-num c))))]
    {:coders coders :bind-pairs bind-pairs
     :total-in total-in :total-out total-out
     :packed-indices packed-indices}))

(defn- read-streams-info [c]
  (loop [info {}]
    (let [id (rd8 c)]
      (cond
        (= id k-end) info

        (= id k-pack-info)
        (let [pack-pos (rd-num c)
              n        (rd-num c)]
          (recur (loop [info (assoc info :pack-pos pack-pos :num-pack-streams n)]
                   (let [id (rd8 c)]
                     (cond
                       (= id k-end) info
                       (= id k-size) (recur (assoc info :pack-sizes
                                                   (vec (for [_ (range n)] (rd-num c)))))
                       (= id k-crc) (do (rd-bool-vector c n)
                                        (dotimes [_ n] (rd-u32 c))
                                        (recur info))
                       :else (throw (ex-info "7z: unexpected id in PackInfo"
                                             {:reason :bad-header :id id})))))))

        (= id k-unpack-info)
        (let [info
              (loop [info info]
                (let [id (rd8 c)]
                  (cond
                    (= id k-end) info

                    (= id k-folder)
                    (let [n (rd-num c)
                          external (rd8 c)]
                      (when (pos? external)
                        (throw (ex-info "7z: folders stored in an external stream are not supported"
                                        {:reason :unsupported-header})))
                      (recur (assoc info :folders (vec (for [_ (range n)] (read-folder c))))))

                    (= id k-coders-unpack-size)
                    (recur (assoc info :unpack-sizes
                                  (mapv (fn [f] (vec (for [_ (range (:total-out f))] (rd-num c))))
                                        (:folders info))))

                    (= id k-crc)
                    (let [n (count (:folders info))
                          defined (rd-bool-vector c n)]
                      (recur (assoc info :folder-crcs
                                    (mapv (fn [d] (when d (rd-u32 c))) defined))))

                    :else (throw (ex-info "7z: unexpected id in UnPackInfo"
                                          {:reason :bad-header :id id})))))]
          (recur info))

        (= id k-substreams-info)
        (let [folders (:folders info)
              info
              (loop [info info]
                (let [id (rd8 c)]
                  (cond
                    (= id k-end) info

                    (= id k-num-unpack-stream)
                    (recur (assoc info :nums-unpack (vec (for [_ folders] (rd-num c)))))

                    (= id k-size)
                    ;; Sizes are stored for every substream except the last of
                    ;; each folder, which is whatever is left over.
                    (let [nums (or (:nums-unpack info) (vec (repeat (count folders) 1)))
                          totals (map-indexed (fn [i _] (first (nth (:unpack-sizes info) i)))
                                              folders)]
                      (recur (assoc info :substream-sizes
                                    (vec (map-indexed
                                          (fn [i n]
                                            (if (= n 1)
                                              [(nth (vec totals) i)]
                                              (let [firsts (vec (for [_ (range (dec n))] (rd-num c)))]
                                                (conj firsts (- (nth (vec totals) i)
                                                                (reduce + firsts))))))
                                          nums)))))

                    (= id k-crc)
                    (let [nums (or (:nums-unpack info) (vec (repeat (count folders) 1)))
                          ;; A folder with exactly one substream whose CRC is
                          ;; already known from UnPackInfo is skipped here.
                          unknown (reduce + (map-indexed
                                             (fn [i n]
                                               (if (and (= n 1)
                                                        (get (:folder-crcs info) i))
                                                 0 n))
                                             nums))
                          defined (rd-bool-vector c unknown)
                          digests (mapv (fn [d] (when d (rd-u32 c))) defined)]
                      (recur (assoc info :substream-crcs digests
                                    :substream-crc-count unknown)))

                    :else (throw (ex-info "7z: unexpected id in SubStreamsInfo"
                                          {:reason :bad-header :id id})))))]
          (recur info))

        :else (throw (ex-info "7z: unexpected id in StreamsInfo"
                              {:reason :bad-header :id id}))))))

;; ---------------------------------------------------------------------------
;; FilesInfo
;; ---------------------------------------------------------------------------

(defn- utf16le->str [bs]
  (let [v (vec bs)]
    (loop [i 0 out ""]
      (if (>= i (count v))
        out
        (let [u (+ (nth v i) (* 256 (nth v (inc i))))]
          (recur (+ i 2) (str out (char u))))))))

(defn- read-names [c size]
  (let [external (rd8 c)]
    (when (pos? external)
      (throw (ex-info "7z: names stored in an external stream are not supported"
                      {:reason :unsupported-header})))
    (let [bs (rd-bytes c (dec size))]
      (loop [i 0 start 0 out []]
        (if (>= i (count bs))
          out
          (if (and (zero? (nth bs i)) (zero? (nth bs (inc i))))
            (recur (+ i 2) (+ i 2) (conj out (utf16le->str (subvec bs start i))))
            (recur (+ i 2) start out)))))))

(defn- read-files-info [c]
  (let [num-files (rd-num c)]
    (loop [info {:num-files num-files}]
      (let [id (rd8 c)]
        (if (= id k-end)
          info
          (let [size  (rd-num c)
                start @(:pos c)
                info  (cond
                        (= id k-empty-stream)
                        (assoc info :empty-stream (rd-bit-vector c num-files))

                        (= id k-empty-file)
                        (assoc info :empty-file
                               (rd-bit-vector c (count (filter true? (:empty-stream info)))))

                        (= id k-anti)
                        (assoc info :anti
                               (rd-bit-vector c (count (filter true? (:empty-stream info)))))

                        (= id k-name)
                        (assoc info :names (read-names c size))

                        (= id k-attributes)
                        (let [defined (rd-bool-vector c num-files)
                              _       (rd8 c)]           ; external
                          (assoc info :attributes
                                 (mapv (fn [d] (when d (rd-u32 c))) defined)))

                        (contains? #{k-mtime k-ctime k-atime} id)
                        (let [defined (rd-bool-vector c num-files)
                              _       (rd8 c)
                              times   (mapv (fn [d] (when d (rd-filetime c))) defined)]
                          (assoc info (case id
                                        0x14 :mtime 0x12 :ctime 0x13 :atime)
                                 times))

                        :else info)]
            ;; Every property carries its size, so an unknown or partially-read
            ;; one is skipped exactly rather than guessed at.
            (vreset! (:pos c) (+ start size))
            (recur info)))))))

;; ---------------------------------------------------------------------------
;; Folder decoding
;; ---------------------------------------------------------------------------

(defn- delta-decode [bytes distance]
  (let [v (vec bytes)]
    (persistent!
     (loop [i 0 out (transient [])]
       (if (>= i (count v))
         out
         (let [prev (if (>= (- i distance) 0) (nth out (- i distance)) 0)]
           (recur (inc i) (conj! out (bit-and (+ (nth v i) prev) 0xff)))))))))

(defn- run-coder [{:keys [coder props]} input out-size opts]
  (case coder
    :copy input

    :lzma1
    (let [dict (+ (nth props 1) (* 256 (nth props 2))
                  (* 65536 (nth props 3)) (* 16777216 (nth props 4)))]
      (:bytes (lzma/decompress-lzma1 input 0 {:props (nth props 0)
                                              :unpacked-size out-size
                                              :dict-size (max dict 4096)})))

    :lzma2
    (:bytes (lzma/decompress-lzma2 input 0 {:dict-size 0x4000000
                                            :max-output (:max-output opts)}))

    :delta (delta-decode input (inc (first props)))

    :deflate (deflate/inflate-raw input (select-keys opts [:max-output]))

    ;; a bare bzip2 stream, BZh header and all — 7z reaches for this on text
    :bzip2 (bzip2/decompress input (select-keys opts [:max-output]))

    (throw (ex-info (str "7z: unsupported coder: " (name coder))
                    {:reason :unsupported-coder :coder coder}))))

(defn- decode-folder
  "Decode one folder's output by walking its coder graph backwards from the
   output stream nothing is bound to."
  [folder packed-streams unpack-sizes opts]
  (let [{:keys [coders bind-pairs packed-indices]} folder
        ;; global in/out stream index ranges per coder
        in-starts  (reductions + 0 (map :num-in coders))
        out-starts (reductions + 0 (map :num-out coders))
        coder-of-out (fn [oi] (first (keep-indexed
                                      (fn [i s] (when (and (<= s oi)
                                                           (< oi (+ s (:num-out (nth coders i)))))
                                                  i))
                                      (vec (butlast out-starts)))))
        bound-out (into {} (map (juxt :in :out) bind-pairs))
        final-out (first (remove (set (map :out bind-pairs))
                                 (range (:total-out folder))))
        decode-out
        (fn decode-out [oi seen]
          (when (contains? seen oi)
            (throw (ex-info "7z: coder graph has a cycle" {:reason :bad-header})))
          (let [ci     (coder-of-out oi)
                coder  (nth coders ci)
                in-lo  (nth (vec in-starts) ci)
                inputs (vec (for [k (range (:num-in coder))]
                              (let [gi (+ in-lo k)]
                                (if-let [src (get bound-out gi)]
                                  (decode-out src (conj seen oi))
                                  (let [pi (index-of (vec packed-indices) gi)]
                                    (when (nil? pi)
                                      (throw (ex-info "7z: input stream is neither bound nor packed"
                                                      {:reason :bad-header :stream gi})))
                                    (nth packed-streams pi))))))]
            (when (> (count inputs) 1)
              (throw (ex-info (str "7z: multi-input coder is not supported: " (name (:coder coder)))
                              {:reason :unsupported-coder :coder (:coder coder)})))
            (run-coder coder (first inputs) (nth unpack-sizes oi) opts)))]
    (decode-out final-out #{})))

;; ---------------------------------------------------------------------------
;; Archive reading
;; ---------------------------------------------------------------------------

(defn- read-header-block
  "Parse a header that starts at the cursor. `kEncodedHeader` means the real
   header is itself a packed stream, so it is decoded and re-parsed."
  [c v base opts]
  (let [id (rd8 c)]
    (cond
      (= id k-header)
      (loop [header {}]
        (let [id (rd8 c)]
          (cond
            (= id k-end) header
            (= id k-main-streams) (recur (assoc header :streams (read-streams-info c)))
            (= id k-files-info) (recur (assoc header :files (read-files-info c)))
            (= id k-archive-properties)
            (do (loop [] (let [t (rd8 c)]
                           (when-not (= t k-end)
                             (rd-bytes c (rd-num c))
                             (recur))))
                (recur header))
            (= id k-additional-streams)
            (throw (ex-info "7z: additional streams are not supported"
                            {:reason :unsupported-header}))
            :else (throw (ex-info "7z: unexpected id in Header"
                                  {:reason :bad-header :id id})))))

      (= id k-encoded-header)
      (let [si       (read-streams-info c)
            folder   (first (:folders si))
            offset   (+ base (:pack-pos si))
            packed   (loop [i 0 pos offset out []]
                       (if (>= i (count (:pack-sizes si)))
                         out
                         (let [size (nth (:pack-sizes si) i)]
                           (recur (inc i) (+ pos size)
                                  (conj out (subvec v pos (+ pos size)))))))
            decoded  (decode-folder folder packed (first (:unpack-sizes si)) opts)]
        (when-let [want (first (:folder-crcs si))]
          (let [got (deflate/crc32 decoded)]
            (when-not (= want got)
              (throw (ex-info "7z: encoded header CRC-32 mismatch"
                              {:reason :checksum-mismatch :expected want :actual got})))))
        (read-header-block (cursor (vec decoded) 0) v base opts))

      :else (throw (ex-info "7z: unexpected top-level header id"
                            {:reason :bad-header :id id})))))

(defn- assemble-entries
  "Zip the FilesInfo names/flags together with the substream sizes and CRCs."
  [header]
  (let [{:keys [streams files]} header
        num-files (or (:num-files files) 0)
        empty-stream (or (:empty-stream files) (vec (repeat num-files false)))
        empty-file   (or (:empty-file files) [])
        names        (or (:names files) [])
        attrs        (or (:attributes files) [])
        mtimes       (or (:mtime files) [])
        ;; substream sizes/CRCs, flattened in folder order
        sizes  (vec (apply concat (or (:substream-sizes streams)
                                      (map (fn [u] [(first u)]) (:unpack-sizes streams)))))
        crcs   (let [nums (or (:nums-unpack streams)
                              (vec (repeat (count (:folders streams)) 1)))
                     sub  (or (:substream-crcs streams) [])
                     fold (or (:folder-crcs streams) [])]
                 ;; A single-substream folder may carry its CRC in UnPackInfo.
                 (vec (loop [i 0 si 0 out []]
                        (if (>= i (count nums))
                          out
                          (let [n (nth nums i)]
                            (if (and (= n 1) (get fold i))
                              (recur (inc i) si (conj out (get fold i)))
                              (recur (inc i) (+ si n)
                                     (into out (subvec (vec sub) si (min (count sub) (+ si n)))))))))))
        nums   (or (:nums-unpack streams)
                   (vec (repeat (count (:folders streams)) 1)))
        folder-of (vec (mapcat (fn [i n] (repeat n i)) (range) nums))
        ;; Byte offset of each substream inside its own folder, so reading one
        ;; member is a slice rather than an index calculation at every call site.
        offsets (vec (:offsets
                      (reduce (fn [{:keys [offsets prev-folder acc]} si]
                                (let [f (nth folder-of si)
                                      acc (if (= f prev-folder) acc 0)]
                                  {:offsets (conj offsets acc)
                                   :prev-folder f
                                   :acc (+ acc (get sizes si))}))
                              {:offsets [] :prev-folder nil :acc 0}
                              (range (count sizes)))))]
    (loop [i 0 si 0 ei 0 out []]
      (if (>= i num-files)
        out
        (let [empty? (nth empty-stream i)
              name   (get names i)]
          (if empty?
            (let [is-file? (get (vec empty-file) ei false)]
              (recur (inc i) si (inc ei)
                     (conj out {:name name
                                :size 0
                                :dir? (not is-file?)
                                :empty? true
                                :attributes (get (vec attrs) i)
                                :mtime (get (vec mtimes) i)})))
            (recur (inc i) (inc si) ei
                   (conj out {:name name
                              :size (get sizes si)
                              :crc32 (get crcs si)
                              :dir? false
                              :empty? false
                              :folder (get folder-of si)
                              :substream si
                              :folder-offset (get offsets si)
                              :attributes (get (vec attrs) i)
                              :mtime (get (vec mtimes) i)}))))))))

(defn- read-archive [data opts]
  (let [v (vec data)]
    (when (< (count v) 32)
      (throw (ex-info "7z: shorter than a signature header" {:reason :not-7z})))
    (when-not (= signature (vec (subvec v 0 6)))
      (throw (ex-info "7z: bad signature" {:reason :not-7z})))
    (let [c        (cursor v 8)
          start-crc (rd-u32 c)
          _        (let [got (deflate/crc32 (subvec v 12 32))]
                     (when-not (= start-crc got)
                       (throw (ex-info "7z: start header CRC-32 mismatch"
                                       {:reason :checksum-mismatch
                                        :expected start-crc :actual got}))))
          next-off (rd-u64 c)
          next-size (rd-u64 c)
          next-crc (rd-u32 c)
          hdr-start (+ 32 next-off)]
      (when (> (+ hdr-start next-size) (count v))
        (throw (ex-info "7z: header runs past the end of the file"
                        {:reason :truncated})))
      (let [hdr-bytes (subvec v hdr-start (+ hdr-start next-size))
            got       (deflate/crc32 hdr-bytes)]
        (when-not (= next-crc got)
          (throw (ex-info "7z: header CRC-32 mismatch"
                          {:reason :checksum-mismatch :expected next-crc :actual got})))
        (if (zero? next-size)
          {:header {} :entries []}                         ; a legitimately empty archive
          (let [header (read-header-block (cursor hdr-bytes 0) v 32 opts)]
            {:header header :entries (assemble-entries header)}))))))

(defn entries
  "Every member's metadata: `:name :size :crc32 :dir? :empty? :folder :substream
   :attributes :mtime`. Nothing is decompressed."
  ([data] (entries data nil))
  ([data opts] (:entries (read-archive data opts))))

(defn- folder-packed-streams [v streams folder-index]
  (let [sizes  (:pack-sizes streams)
        ;; Each folder consumes as many packed streams as it has packed inputs.
        counts (mapv #(count (:packed-indices %)) (:folders streams))
        skip   (reduce + (take folder-index counts))
        base   (+ 32 (:pack-pos streams))
        offset (+ base (reduce + (take skip sizes)))]
    (loop [i 0 pos offset out []]
      (if (>= i (nth counts folder-index))
        out
        (let [size (nth sizes (+ skip i))]
          (recur (inc i) (+ pos size) (conj out (subvec v pos (+ pos size)))))))))

(defn parse
  "Every member with its contents. Each folder is decoded once and its members
   sliced out of the result — that is how .7z stores them (solid compression), so
   there is no cheaper way to read one member from the middle of a folder.

   Options: `:verify-crc` (default true), `:max-output`."
  ([data] (parse data nil))
  ([data {:keys [verify-crc] :or {verify-crc true} :as opts}]
   (let [v       (vec data)
         {:keys [header entries]} (read-archive v opts)
         streams (:streams header)
         cache   (volatile! {})
         folder-bytes
         (fn [fi]
           (or (get @cache fi)
               (let [f       (nth (:folders streams) fi)
                     packed  (folder-packed-streams v streams fi)
                     decoded (decode-folder f packed (nth (:unpack-sizes streams) fi) opts)]
                 (vswap! cache assoc fi decoded)
                 decoded)))]
     (mapv
      (fn [e]
        (if (:empty? e)
          (assoc e :bytes [])
          (let [fb    (vec (folder-bytes (:folder e)))
                start (:folder-offset e)
                bs    (subvec fb start (+ start (:size e)))]
            (when (and verify-crc (:crc32 e))
              (let [got (deflate/crc32 bs)]
                (when-not (= (:crc32 e) got)
                  (throw (ex-info "7z: member CRC-32 mismatch"
                                  {:reason :checksum-mismatch :name (:name e)
                                   :expected (:crc32 e) :actual got})))))
            (assoc e :bytes bs))))
      entries))))

(defn names [entries] (mapv :name entries))
(defn entry [entries name] (first (filter #(= name (:name %)) entries)))

;; ---------------------------------------------------------------------------
;; Writing (Copy coder)
;; ---------------------------------------------------------------------------

(def ^:private number-limits
  ;; 2^(7*(i+1)) — the point at which the leading byte needs another high bit.
  [128 16384 2097152 268435456 34359738368 4398046511104 562949953421312 72057594037927936])

(defn- wr-number
  "Inverse of `rd-number`: high bits of the leading byte count the extra
   little-endian bytes that follow."
  [n]
  (loop [i 0 fb 0 mask 0x80 div 1]
    (if (or (= i 8) (< n (nth number-limits i)))
      (into [(bit-or fb (bit-and (quot n div) 0xff))]
            (loop [j 0 d 1 out []]
              (if (>= j i)
                out
                (recur (inc j) (* d 256) (conj out (bit-and (quot n d) 0xff))))))
      (recur (inc i) (bit-or fb mask) (unsigned-bit-shift-right mask 1) (* div 256)))))

(defn- wr-u32 [n]
  [(bit-and n 0xff)
   (bit-and (unsigned-bit-shift-right n 8) 0xff)
   (bit-and (unsigned-bit-shift-right n 16) 0xff)
   (bit-and (unsigned-bit-shift-right n 24) 0xff)])

(defn- wr-u64 [n]
  (into (wr-u32 (mod n 4294967296)) (wr-u32 (quot n 4294967296))))

(defn- char-code [c]
  #?(:clj (int c) :cljs (.charCodeAt c 0)))

(defn- str->utf16le
  "7z stores names as UTF-16LE. Clojure strings are already UTF-16 code units, so
   surrogate pairs pass through unchanged."
  [s]
  (vec (mapcat (fn [ch]
                 (let [u (char-code ch)]
                   [(bit-and u 0xff) (bit-and (unsigned-bit-shift-right u 8) 0xff)]))
               (seq s))))

(defn- bit-vector-bytes
  "Pack booleans most-significant-bit first."
  [bools]
  (loop [bs (vec bools) out []]
    (if (empty? bs)
      out
      (let [chunk (take 8 bs)
            byte  (reduce (fn [acc [i b]] (if b (bit-or acc (bit-shift-left 1 (- 7 i))) acc))
                          0 (map-indexed vector chunk))]
        (recur (vec (drop 8 bs)) (conj out byte))))))

(defn build
  "Assemble a .7z archive whose members are stored with the Copy coder → vector
   of unsigned bytes.

   Each entry is `{:name \"path\" :bytes <unsigned bytes>}`, or `{:name \"dir/\"
   :dir? true}`. One folder per member, so members stay individually
   addressable — the opposite of 7-Zip's solid default, and the right trade-off
   for an archive nothing compressed anyway.

   There is deliberately no LZMA encoder here (see `org-tukaani-xz`): this writes
   the *container*, which is what `7z l`/`7z t`/`7z x` and every other tool
   need."
  ([entries] (build entries nil))
  ([entries _opts]
   (let [entries  (mapv (fn [e]
                          (let [dir? (boolean (or (:dir? e) (re-find #"/$" (str (:name e)))))]
                            (assoc e :dir? dir?
                                   :bytes (if dir? [] (vec (:bytes e))))))
                        entries)
         streamed (filterv #(and (not (:dir? %)) (pos? (count (:bytes %)))) entries)
         packed   (vec (mapcat :bytes streamed))
         n        (count streamed)
         ;; Folders: one Copy coder each. Flags 0x01 = 1-byte id, simple, no props.
         folder   [0x01 0x01 0x00]
         empty?   (mapv #(or (:dir? %) (zero? (count (:bytes %)))) entries)
         any-empty? (boolean (some true? empty?))
         empty-files (mapv #(and (not (:dir? %)) (zero? (count (:bytes %))))
                           (filterv #(or (:dir? %) (zero? (count (:bytes %)))) entries))
         names-bs (vec (mapcat (fn [e] (into (str->utf16le (:name e)) [0 0])) entries))
         streams  (when (pos? n)
                    (-> [k-main-streams]
                        (into [k-pack-info])
                        (into (wr-number 0))                ; pack position
                        (into (wr-number n))
                        (into [k-size])
                        (into (mapcat #(wr-number (count (:bytes %))) streamed))
                        (into [k-end])
                        (into [k-unpack-info k-folder])
                        (into (wr-number n))
                        (into [0x00])                       ; not external
                        (into (mapcat (fn [_] folder) streamed))
                        (into [k-coders-unpack-size])
                        (into (mapcat #(wr-number (count (:bytes %))) streamed))
                        (into [k-crc 0x01])                 ; all CRCs defined
                        (into (mapcat #(wr-u32 (deflate/crc32 (:bytes %))) streamed))
                        (into [k-end k-end])))
         files    (-> [k-files-info]
                      (into (wr-number (count entries)))
                      (into (if any-empty?
                              (let [bs (bit-vector-bytes empty?)]
                                (-> [k-empty-stream]
                                    (into (wr-number (count bs)))
                                    (into bs)))
                              []))
                      (into (if (some true? empty-files)
                              (let [bs (bit-vector-bytes empty-files)]
                                (-> [k-empty-file]
                                    (into (wr-number (count bs)))
                                    (into bs)))
                              []))
                      (into [k-name])
                      (into (wr-number (inc (count names-bs))))
                      (into [0x00])                         ; not external
                      (into names-bs)
                      (into [k-end]))
         header   (-> [k-header]
                      (into (or streams []))
                      (into files)
                      (into [k-end]))
         start    (-> (wr-u64 (count packed))
                      (into (wr-u64 (count header)))
                      (into (wr-u32 (deflate/crc32 header))))]
     (-> (vec signature)
         (into [0x00 0x04])                                 ; format version 0.4
         (into (wr-u32 (deflate/crc32 start)))
         (into start)
         (into packed)
         (into header)))))
