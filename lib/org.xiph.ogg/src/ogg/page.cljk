(ns ogg.page
  "Ogg pages (RFC 3533 §6), read and written.

   A page is a fixed 27-byte header, a segment table of 1-255 lacing values, and
   the segments themselves. Packets are carried across pages by **lacing**: each
   segment is 0-255 bytes, a value below 255 terminates a packet, and a packet
   whose length is a multiple of 255 must therefore be followed by a zero-length
   segment to say so. Getting that wrong loses the last packet of a stream or
   silently concatenates two.

   Fields are little-endian, unlike almost every other container: `granule`
   position is 64-bit LE and is read as two 32-bit halves recombined by
   multiplication, because a 64-bit shift does not exist on ClojureScript.
   The reserved value 0xFFFFFFFFFFFFFFFF (`-1`) means *no packet ends on this
   page* and is returned as `:none` rather than as a number."
  (:require [ogg.crc :as crc]))

(def ^:private capture-pattern [0x4f 0x67 0x67 0x53])       ; "OggS"
(def header-size 27)

(def continued-flag 0x01)
(def bos-flag 0x02)
(def eos-flag 0x04)

(defn- u8 [v i] (nth v i))
(defn- u32le [v i]
  (+ (nth v i) (* 256 (nth v (+ i 1))) (* 65536 (nth v (+ i 2)))
     (* 16777216 (nth v (+ i 3)))))
(defn- u64le
  "64-bit little-endian as an exact integer, or `:none` for the reserved -1."
  [v i]
  (let [lo (u32le v i)
        hi (u32le v (+ i 4))]
    (if (and (= lo 4294967295) (= hi 4294967295))
      :none
      (+ lo (* 4294967296 hi)))))

(defn- put-u32le [n]
  [(bit-and n 0xff)
   (bit-and (quot n 256) 0xff)
   (bit-and (quot n 65536) 0xff)
   (bit-and (quot n 16777216) 0xff)])

(defn- put-u64le [n]
  (if (= n :none)
    (vec (repeat 8 0xff))
    (into (put-u32le (mod n 4294967296)) (put-u32le (quot n 4294967296)))))

(defn page-at
  "Parse the page starting at `offset` →

       {:continued? :bos? :eos? :granule :serial :sequence :crc :segments
        :size :body :packets :tail}

   `:segments` is the lacing table, `:packets` the complete packets ending on
   this page, `:tail` the bytes of a packet that continues onto the next one, and
   `:size` the total page length so a caller can walk to the next page. The
   stored CRC is verified unless `:verify-crc false`."
  ([data offset] (page-at data offset {}))
  ([data offset {:keys [verify-crc] :or {verify-crc true}}]
   (let [v (vec data)
         n (count v)]
     (when (> (+ offset header-size) n)
       (throw (ex-info "ogg: truncated page header"
                       {:reason :truncated :offset offset})))
     (when-not (= capture-pattern (subvec v offset (+ offset 4)))
       (throw (ex-info "ogg: no OggS capture pattern"
                       {:reason :not-ogg :offset offset})))
     (let [version (u8 v (+ offset 4))]
       (when-not (zero? version)
         (throw (ex-info "ogg: unknown page version"
                         {:reason :bad-version :version version})))
       (let [flags (u8 v (+ offset 5))
             granule (u64le v (+ offset 6))
             serial (u32le v (+ offset 14))
             sequence (u32le v (+ offset 18))
             stored-crc (u32le v (+ offset 22))
             n-segments (u8 v (+ offset 26))
             seg-start (+ offset header-size)
             _ (when (> (+ seg-start n-segments) n)
                 (throw (ex-info "ogg: truncated segment table"
                                 {:reason :truncated :offset offset})))
             segments (subvec v seg-start (+ seg-start n-segments))
             body-len (reduce + 0 segments)
             body-start (+ seg-start n-segments)
             _ (when (> (+ body-start body-len) n)
                 (throw (ex-info "ogg: page body runs past the end of the input"
                                 {:reason :truncated :offset offset
                                  :want body-len :have (- n body-start)})))
             size (+ header-size n-segments body-len)
             body (subvec v body-start (+ body-start body-len))
             [packets tail]
             (loop [ss (seq segments) start 0 len 0 out []]
               (if-not ss
                 [out (subvec body start (+ start len))]
                 (let [l (first ss)]
                   (if (= l 255)
                     (recur (next ss) start (+ len 255) out)
                     (let [end (+ start len l)]
                       (recur (next ss) end 0 (conj out (subvec body start end))))))))]
         (when verify-crc
           (let [zeroed (into (into (subvec v offset (+ offset 22)) [0 0 0 0])
                              (subvec v (+ offset 26) (+ offset size)))
                 computed (crc/crc32 zeroed)]
             (when-not (= computed stored-crc)
               (throw (ex-info "ogg: page CRC mismatch"
                               {:reason :bad-crc :offset offset
                                :expected stored-crc :actual computed})))))
         {:continued? (pos? (bit-and flags continued-flag))
          :bos? (pos? (bit-and flags bos-flag))
          :eos? (pos? (bit-and flags eos-flag))
          :granule granule
          :serial serial
          :sequence sequence
          :crc stored-crc
          :segments segments
          :size size
          :body body
          ;; A segment of 255 continues a packet; anything less ends one. A
          ;; trailing run of 255s means the packet continues on the *next* page,
          ;; so those bytes are reported separately as `:tail` and are not a
          ;; packet here. Treating a tail as a complete packet is how a decoder
          ;; ends up handing a truncated frame to a codec.
          :packets packets
          :tail tail})))))

(defn pages
  "Lazily walk every page in `data`. Returns a vector of page maps."
  ([data] (pages data {}))
  ([data opts]
   (let [v (vec data) n (count v)]
     (loop [off 0 out []]
       (if (>= off n)
         out
         (let [p (page-at v off opts)]
           (recur (+ off (:size p)) (conj out p))))))))

(defn lacing
  "The segment table for packets of the given `lengths`.

   A packet whose length is a multiple of 255 gets a terminating zero segment —
   the rule that decides whether a decoder sees one packet or two."
  [lengths]
  (vec (mapcat (fn [len]
                 (concat (repeat (quot len 255) 255) [(rem len 255)]))
               lengths)))

(defn build-raw
  "Serialise one page from an explicit segment table → a vector of unsigned bytes.

   `ogg.stream/build` needs this to *split* a packet across pages: the segment
   table then no longer follows from the packet lengths, because a page that
   continues a packet must end on a 255 segment with no terminator."
  [{:keys [segments body serial sequence granule bos? eos? continued?]
    :or {granule 0 sequence 0}}]
  (when (> (count segments) 255)
    (throw (ex-info "ogg: more lacing values than a page can hold"
                    {:reason :page-overflow :segments (count segments)})))
  (when-not (= (reduce + 0 segments) (count body))
    (throw (ex-info "ogg: segment table does not describe the body"
                    {:reason :bad-segments :lacing-total (reduce + 0 segments)
                     :body (count body)})))
  (let [flags (+ (if continued? continued-flag 0)
                 (if bos? bos-flag 0)
                 (if eos? eos-flag 0))
        head (vec (concat capture-pattern
                          [0 flags]
                          (put-u64le granule)
                          (put-u32le serial)
                          (put-u32le sequence)
                          [0 0 0 0]                         ; CRC placeholder
                          [(count segments)]))
        page (into (into head (vec segments)) (vec body))
        c (crc/crc32 page)]
    ;; the checksum covers the page including its own zeroed field, so it is
    ;; patched in afterwards rather than computed over a prefix
    (reduce (fn [v [i b]] (assoc v i b))
            page
            (map vector (range 22 26) (put-u32le c)))))

(defn build
  "Serialise one page of complete packets → a vector of unsigned bytes.

       {:packets [[bytes] ...] :serial n :sequence n
        :granule n-or-:none :bos? :eos? :continued?}

   At most 255 lacing values fit in a page, so `:packets` must be small enough to
   lace within that; `ogg.stream/build` does the splitting. The CRC is computed
   over the finished page with its own field zeroed."
  [{:keys [packets] :as opts}]
  (build-raw (assoc opts
                    :segments (lacing (map count packets))
                    :body (vec (apply concat packets)))))
