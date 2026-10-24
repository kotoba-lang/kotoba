(ns tar.core
  "tar archives (POSIX.1 ustar, IEEE Std 1003.1) — read and write, portable
   `.cljc`, zero dependencies.

   tar is an *archiver*, not a codec: it concatenates 512-byte header blocks and
   padded file data, and compression is somebody else's job. `.tar.gz` is this
   repo composed with `org-ietf-deflate`'s gzip, `.tar.xz` with
   `org-tukaani-xz` — see the README.

   Three header dialects exist in the wild and all three are read here:

   - **ustar** (POSIX.1-1988): the 512-byte header with `magic = \"ustar\\0\"`,
     names split across a 155-byte prefix and a 100-byte name.
   - **PAX** (POSIX.1-2001): an `x` (per-file) or `g` (global) entry whose *data*
     is a set of `\"<len> <key>=<value>\\n\"` records that override the next
     entry's header. This is how long names, sub-second times, large sizes and
     non-ASCII metadata are carried, and it is what macOS `tar` writes by
     default.
   - **GNU** long name/link (`L`/`K` type flags) plus base-256 numeric fields.

   Writing produces ustar, escalating to a PAX header only for what ustar cannot
   express (a name that will not split, a link target over 100 bytes, a size
   above 8 GiB). Output is reproducible: mtime, uid and gid default to 0 and
   nothing reads the clock or the environment."
  (:require [kotoba.lang.text :as str]
            [tar.bytes :as b]))

(def block-size 512)

(def ^:private default-record-size
  "GNU tar's default blocking factor (20 × 512). Some readers insist the archive
   is a whole number of records, so writing pads to it."
  10240)

(def type-flag->type
  {0x00 :file, 0x30 :file, 0x37 :file                      ; NUL, '0', '7' (contiguous)
   0x31 :hard-link, 0x32 :symlink
   0x33 :char-device, 0x34 :block-device
   0x35 :directory, 0x36 :fifo})

(def ^:private type->type-flag
  {:file 0x30 :hard-link 0x31 :symlink 0x32 :char-device 0x33
   :block-device 0x34 :directory 0x35 :fifo 0x36})

(def ^:private pax-next 0x78)                              ; 'x'
(def ^:private pax-global 0x67)                            ; 'g'
(def ^:private gnu-long-name 0x4c)                         ; 'L'
(def ^:private gnu-long-link 0x4b)                         ; 'K'

;; ---------------------------------------------------------------------------
;; Header checksum
;; ---------------------------------------------------------------------------

(defn- checksum
  "Sum of the 512 header bytes with the checksum field itself read as spaces.
   Historic tars disagreed on whether the bytes are signed, so both sums are
   offered and a reader accepts either."
  [bv off]
  (loop [i 0 unsigned 0 signed 0]
    (if (= i block-size)
      [unsigned signed]
      (let [raw (nth bv (+ off i))
            v   (if (and (>= i 148) (< i 156)) 0x20 raw)]
        (recur (inc i)
               (+ unsigned v)
               (+ signed (if (> v 127) (- v 256) v)))))))

(defn- zero-block? [bv off]
  (every? zero? (subvec bv off (+ off block-size))))

;; ---------------------------------------------------------------------------
;; PAX records
;; ---------------------------------------------------------------------------

(defn parse-pax
  "`\"<len> <key>=<value>\\n\"` records → `{key value}` (both strings).
   A record whose length does not parse ends the block rather than throwing:
   the payload is metadata, and a malformed tail should not lose the archive."
  [bs]
  (let [v (vec bs) n (count v)]
    (loop [i 0 out {}]
      (if (>= i n)
        out
        (let [sp (loop [j i] (cond (>= j n) nil
                                   (= 0x20 (nth v j)) j
                                   :else (recur (inc j))))
              len (when sp
                    (try (#?(:clj Integer/parseInt :cljs js/parseInt)
                          (b/utf8->str (subvec v i sp)))
                         (catch #?(:clj Exception :cljs :default) _ nil)))]
          (if (or (nil? len) (<= len 0) (> (+ i len) n))
            out
            (let [record (subvec v (inc sp) (+ i len))     ; drops the trailing \n below
                  record (if (and (seq record) (= 0x0a (peek record)))
                           (subvec record 0 (dec (count record)))
                           record)
                  eq     (loop [j 0] (cond (>= j (count record)) nil
                                           (= 0x3d (nth record j)) j
                                           :else (recur (inc j))))]
              (recur (+ i len)
                     (if eq
                       (assoc out (b/utf8->str (subvec record 0 eq))
                              (b/utf8->str (subvec record (inc eq))))
                       out)))))))))

(defn- pax-record [k v]
  (let [body (into (b/str->utf8 (str k "=")) (conj (b/str->utf8 v) 0x0a))]
    ;; The length prefix counts itself, so it has to converge.
    (loop [guess 1]
      (let [len (+ guess 1 (count body))
            s   (str len)]
        (if (= (count s) guess)
          (into (b/str->utf8 (str s " ")) body)
          (recur (count s)))))))

(defn- pax-block [records]
  (reduce (fn [acc [k v]] (into acc (pax-record k v))) [] records))

;; ---------------------------------------------------------------------------
;; Reading
;; ---------------------------------------------------------------------------

(defn- parse-header [bv off]
  (let [[unsigned signed] (checksum bv off)
        stored (b/read-numeric bv (+ off 148) 8)]
    (when-not (or (= stored unsigned) (= stored signed))
      (throw (ex-info "tar: header checksum mismatch"
                      {:reason :bad-checksum :offset off
                       :stored stored :computed unsigned})))
    (let [name   (b/read-str bv off 100)
          flag   (nth bv (+ off 156))
          magic  (b/read-str bv (+ off 257) 6)
          ustar? (= "ustar" (str/trim magic))
          prefix (when ustar? (b/read-str bv (+ off 345) 155))]
      {:name      (if (seq prefix) (str prefix "/" name) name)
       :mode      (b/read-numeric bv (+ off 100) 8)
       :uid       (b/read-numeric bv (+ off 108) 8)
       :gid       (b/read-numeric bv (+ off 116) 8)
       :size      (b/read-numeric bv (+ off 124) 12)
       :mtime     (b/read-numeric bv (+ off 136) 12)
       :type-flag flag
       :type      (get type-flag->type flag :unknown)
       :linkname  (b/read-str bv (+ off 157) 100)
       :magic     magic
       :uname     (when ustar? (b/read-str bv (+ off 265) 32))
       :gname     (when ustar? (b/read-str bv (+ off 297) 32))
       :dev-major (when ustar? (b/read-numeric bv (+ off 329) 8))
       :dev-minor (when ustar? (b/read-numeric bv (+ off 337) 8))})))

(defn- apply-overrides
  "PAX records and GNU long-name entries override the header they precede."
  [entry pax]
  (cond-> entry
    (get pax "path")     (assoc :name (get pax "path"))
    (get pax "linkpath") (assoc :linkname (get pax "linkpath"))
    (get pax "size")     (assoc :size (#?(:clj Long/parseLong :cljs js/parseInt)
                                       (get pax "size")))
    (get pax "uid")      (assoc :uid (#?(:clj Long/parseLong :cljs js/parseInt) (get pax "uid")))
    (get pax "gid")      (assoc :gid (#?(:clj Long/parseLong :cljs js/parseInt) (get pax "gid")))
    (get pax "uname")    (assoc :uname (get pax "uname"))
    (get pax "gname")    (assoc :gname (get pax "gname"))
    (get pax "mtime")    (assoc :mtime (#?(:clj Double/parseDouble :cljs js/parseFloat)
                                        (get pax "mtime")))
    (seq pax)            (assoc :pax pax)))

(defn- blocks-for [size] (* block-size (quot (+ size block-size -1) block-size)))

(defn entries
  "Every entry's metadata, in archive order. Nothing is copied out of the
   archive: `:offset` is where the entry's data starts and `:size` how long it
   is, so `read-entry` can slice it later.

   PAX and GNU extension entries are consumed rather than reported — their whole
   purpose is to modify the next real entry — but the records they carried stay
   visible on that entry's `:pax`."
  [data]
  (let [bv (vec data)
        n  (count bv)]
    (loop [off 0 pending {} global {} out []]
      (if (> (+ off block-size) n)
        out
        (if (zero-block? bv off)
          ;; A pair of zero blocks ends the archive; a single one at EOF is
          ;; sloppy but common, so it also ends it.
          out
          (let [h        (parse-header bv off)
                data-off (+ off block-size)
                size     (:size h)
                next-off (+ data-off (blocks-for size))
                flag     (:type-flag h)]
            (when (> next-off n)
              (throw (ex-info "tar: entry data runs past the end of the archive"
                              {:reason :truncated :name (:name h) :offset data-off})))
            (cond
              (= flag pax-global)
              (recur next-off pending
                     (merge global (parse-pax (subvec bv data-off (+ data-off size))))
                     out)

              (= flag pax-next)
              (recur next-off
                     (merge pending (parse-pax (subvec bv data-off (+ data-off size))))
                     global out)

              (= flag gnu-long-name)
              (recur next-off
                     (assoc pending "path" (b/utf8->str
                                            (take-while pos? (subvec bv data-off (+ data-off size)))))
                     global out)

              (= flag gnu-long-link)
              (recur next-off
                     (assoc pending "linkpath" (b/utf8->str
                                                (take-while pos? (subvec bv data-off (+ data-off size)))))
                     global out)

              :else
              (let [e (-> h
                          (apply-overrides (merge global pending))
                          (assoc :offset data-off))]
                (recur next-off {} global (conj out e))))))))))

(defn read-entry
  "One entry's contents → the entry with `:bytes` (empty for anything that has
   no data: directories, links, devices)."
  [data e]
  (let [bv (vec data)]
    (assoc e :bytes (if (= :file (:type e))
                      (subvec bv (:offset e) (+ (:offset e) (:size e)))
                      []))))

(defn parse
  "Every entry with its contents."
  [data]
  (let [bv (vec data)]
    (mapv #(read-entry bv %) (entries bv))))

(defn names [entries] (mapv :name entries))
(defn entry [entries name] (first (filter #(= name (:name %)) entries)))

;; ---------------------------------------------------------------------------
;; Writing
;; ---------------------------------------------------------------------------

(def ^:private max-octal-size 8589934591)                  ; 0o77777777777

(defn- split-name
  "ustar carries a path as prefix + '/' + name (155 + 100 bytes). Returns
   `[name prefix]`, or nil when no split works and PAX is needed."
  [name-bs]
  (if (<= (count name-bs) 100)
    [name-bs []]
    (let [n (count name-bs)]
      ;; longest prefix ending at a '/' that leaves ≤100 bytes for the name
      (loop [i (min 154 (- n 2))]
        (cond
          (< i 0) nil
          (and (= 0x2f (nth name-bs i)) (<= (- n i 1) 100))
          [(subvec name-bs (inc i)) (subvec name-bs 0 i)]
          :else (recur (dec i)))))))

(defn- header-block
  [{:keys [name-bs prefix-bs type-flag mode uid gid size mtime linkname-bs uname gname]}]
  (let [blk (transient (vec (repeat block-size 0)))
        put (fn [t off bs] (reduce (fn [acc [i v]] (assoc! acc (+ off i) v))
                                   t (map-indexed vector bs)))
        blk (-> blk
                (put 0 name-bs)
                (put 100 (b/octal-field mode 8))
                (put 108 (b/octal-field uid 8))
                (put 116 (b/octal-field gid 8))
                (put 124 (b/octal-field size 12))
                (put 136 (b/octal-field mtime 12))
                (put 148 [0x20 0x20 0x20 0x20 0x20 0x20 0x20 0x20])  ; checksum placeholder
                (put 156 [type-flag])
                (put 157 linkname-bs)
                (put 257 (b/ascii->bytes "ustar"))          ; magic + NUL at 262
                (put 263 (b/ascii->bytes "00"))             ; version
                (put 265 (b/str->utf8 (or uname "")))
                (put 297 (b/str->utf8 (or gname "")))
                (put 329 (b/octal-field 0 8))
                (put 337 (b/octal-field 0 8))
                (put 345 prefix-bs))
        filled (persistent! blk)
        [unsigned _] (checksum filled 0)]
    ;; The classic checksum encoding is six octal digits, NUL, space.
    (into (subvec filled 0 148)
          (into (subvec (b/octal-field unsigned 7) 0 7)
                (into [0x20] (subvec filled 156))))))

(defn- pad-to-block [bs]
  (let [r (mod (count bs) block-size)]
    (if (zero? r) bs (into bs (repeat (- block-size r) 0)))))

(defn build
  "Assemble a tar archive → vector of unsigned bytes.

   Each entry is `{:name \"path\" :bytes <unsigned bytes>}` plus optional
   `:type` (`:file` default, `:directory`, `:symlink`, `:hard-link`, `:fifo`,
   `:char-device`, `:block-device`), `:linkname`, `:mode`, `:mtime`, `:uid`,
   `:gid`, `:uname`, `:gname`.

   Options: `:record-size` (default 10240; 0 writes only the two terminating
   zero blocks).

   ustar is used wherever it suffices; a PAX header is emitted only for a name
   that will not split, a link target over 100 bytes, or a size above 8 GiB."
  ([entries] (build entries nil))
  ([entries {:keys [record-size] :or {record-size default-record-size}}]
   (let [out
         (reduce
          (fn [acc e]
            (let [dir?     (or (= :directory (:type e)) (str/ends-with? (:name e) "/"))
                  type     (or (:type e) (if dir? :directory :file))
                  data     (if (= :file type) (vec (:bytes e)) [])
                  name     (:name e)
                  name     (if (and (= :directory type) (not (str/ends-with? name "/")))
                             (str name "/") name)
                  name-bs  (b/str->utf8 name)
                  link-bs  (b/str->utf8 (or (:linkname e) ""))
                  size     (count data)
                  split    (split-name name-bs)
                  pax      (cond-> {}
                             (nil? split)            (assoc "path" name)
                             (> (count link-bs) 100) (assoc "linkpath" (or (:linkname e) ""))
                             (> size max-octal-size) (assoc "size" (str size)))
                  base     {:type-flag   (get type->type-flag type 0x30)
                            :mode        (or (:mode e) (if (= :directory type) 493 420))
                            :uid         (or (:uid e) 0)
                            :gid         (or (:gid e) 0)
                            :size        (if (contains? pax "size") 0 size)
                            :mtime       (or (:mtime e) 0)
                            :uname       (:uname e)
                            :gname       (:gname e)
                            :name-bs     (if split (first split) (subvec name-bs 0 100))
                            :prefix-bs   (if split (second split) [])
                            :linkname-bs (if (> (count link-bs) 100) [] link-bs)}
                  acc      (if (seq pax)
                             ;; The PAX entry's own name is conventional; readers
                             ;; key off the type flag, not the name.
                             (let [records (pax-block pax)
                                   pname   (b/str->utf8 (str "PaxHeaders/" (last (str/split name #"/"))))
                                   pname   (subvec pname 0 (min 100 (count pname)))]
                               (-> acc
                                   (into (header-block {:name-bs pname :prefix-bs []
                                                        :type-flag pax-next :mode 420
                                                        :uid 0 :gid 0 :size (count records)
                                                        :mtime 0 :linkname-bs []}))
                                   (into (pad-to-block records))))
                             acc)]
              (-> acc
                  (into (header-block base))
                  (into (pad-to-block data)))))
          []
          entries)
         out (into out (repeat (* 2 block-size) 0))]
     (if (pos? record-size)
       (let [r (mod (count out) record-size)]
         (if (zero? r) out (into out (repeat (- record-size r) 0))))
       out))))
