(ns zip.write
  "ZIP writing (PKWARE APPNOTE.TXT): local headers, the central directory, the
   end-of-central-directory record, and the ZIP64 structures when the archive
   needs them.

   Every member is compressed in memory, so sizes and CRC-32s are known before
   the local header is written and no data descriptors are needed — the shape
   that every reader, including the oldest, understands.

   Archives are **reproducible**: timestamps default to the MS-DOS epoch
   (1980-01-01), the version-made-by and external-attribute fields are constants,
   and nothing else varies. The same entries produce the same bytes, which is
   what makes a content-addressed `.docx`/`.epub`/`.sketch` possible.

   Deliberately absent: encryption (a ZIP feature nobody should still be using),
   split archives, and per-entry compression methods other than stored, deflate
   and bzip2."
  (:require [bzip2.core :as bzip2]
            [kotoba.lang.text :as str]
            [deflate.core :as deflate]
            [zip.bytes :as b]))

(def ^:private max-u16 65535)
(def ^:private max-u32 4294967295)

(def ^:private version-needed-base 20)                     ; 2.0 — deflate
(def ^:private version-needed-zip64 45)                    ; 4.5 — ZIP64
(def ^:private flag-utf8 0x0800)

;; High byte 3 = Unix, so the external attributes below are read as a mode.
(defn- version-made-by [zip64?]
  (+ 768 (if zip64? version-needed-zip64 version-needed-base)))

(defn- p8  [out x] (conj! out (bit-and x 0xff)))
(defn- p16 [out x] (-> out (p8 x) (p8 (unsigned-bit-shift-right x 8))))
(defn- p32 [out x] (-> out (p16 (bit-and x 0xffff)) (p16 (quot x 65536))))
(defn- p64 [out x] (-> out (p32 (mod x 4294967296)) (p32 (quot x 4294967296))))
(defn- pbytes [out bs] (reduce (fn [o x] (p8 o x)) out bs))

(defn- prepare
  "Compress one entry and work out its header fields."
  [{:keys [name bytes method level dir? comment mtime]} default-level]
  (let [data     (vec bytes)
        dir?     (boolean (or dir? (str/ends-with? name "/")))
        data     (if dir? [] data)
        name-bs  (b/str->utf8 name)
        utf8?    (boolean (some #(> % 0x7f) name-bs))
        level    (or level default-level)
        method   (cond dir?                 :stored
                       (empty? data)        :stored
                       (= method :stored)   :stored
                       (= method :bzip2)    :bzip2
                       :else                :deflate)
        compressed (case method
                     :deflate (deflate/deflate-raw data {:level level})
                     ;; method 12 is a bare bzip2 stream. `:level` means blocks of
                     ;; 100 KB each there, not an effort setting, so it is passed
                     ;; through unchanged rather than remapped.
                     :bzip2 (bzip2/compress data {:level (or level 9)})
                     nil)
        ;; A member that compresses larger than it started is stored instead; the
        ;; format allows either and every reader handles stored.
        store?   (or (= method :stored) (>= (count compressed) (count data)))
        payload  (if store? data compressed)
        {:keys [date time]} (if mtime (b/map->dos mtime) b/dos-epoch)]
    {:name      name
     :name-bs   name-bs
     :comment   comment
     :dir?      dir?
     :method    (cond store? 0 (= method :bzip2) 12 :else 8)
     :flags     (if utf8? flag-utf8 0)
     :crc32     (deflate/crc32 data)
     :size      (count data)
     :csize     (count payload)
     :payload   payload
     :dos-date  date
     :dos-time  time}))

(defn- local-header [out {:keys [name-bs method flags crc32 size csize dos-date dos-time]}]
  (-> out
      (p32 0x04034b50)
      (p16 version-needed-base)
      (p16 flags)
      (p16 method)
      (p16 dos-time)
      (p16 dos-date)
      (p32 crc32)
      (p32 csize)
      (p32 size)
      (p16 (count name-bs))
      (p16 0)                                              ; extra length
      (pbytes name-bs)))

(defn- central-entry [out {:keys [name-bs comment dir? method flags crc32 size csize
                                 dos-date dos-time offset]} zip64?]
  (let [comment-bs (if comment (b/str->utf8 comment) [])
        extra      (when zip64?
                     ;; 0x0001: uncompressed size, compressed size, local header
                     ;; offset — in that order, each 8 bytes.
                     (persistent! (-> (transient [])
                                      (p16 0x0001) (p16 24)
                                      (p64 size) (p64 csize) (p64 offset))))]
    (-> out
        (p32 0x02014b50)
        (p16 (version-made-by zip64?))
        (p16 (if zip64? version-needed-zip64 version-needed-base))
        (p16 flags)
        (p16 method)
        (p16 dos-time)
        (p16 dos-date)
        (p32 crc32)
        (p32 (if zip64? max-u32 csize))
        (p32 (if zip64? max-u32 size))
        (p16 (count name-bs))
        (p16 (count extra))
        (p16 (count comment-bs))
        (p16 0)                                            ; disk number start
        (p16 0)                                            ; internal attributes
        ;; external attributes: directory bit + rw-r--r-- / rwxr-xr-x, so that
        ;; unzip recreates something sane on a POSIX filesystem.
        (p32 (if dir? 0x41ed0010 0x81a40000))
        (p32 (if zip64? max-u32 offset))
        (pbytes name-bs)
        (pbytes (or extra []))
        (pbytes comment-bs))))

(defn build
  "Assemble a ZIP archive → vector of unsigned bytes.

   Each entry is `{:name \"path/in/zip\" :bytes <unsigned bytes>}` plus optional
   `:method` (`:deflate` default, `:stored`, `:bzip2`), `:level`, `:dir?`, `:comment` and
   `:mtime` (`{:year :month :day :hour :minute :second}`).

   Options: `:level` (default for all entries), `:comment` (archive comment),
   `:zip64` — `:auto` (default) writes ZIP64 structures only when a count, size
   or offset no longer fits, `true` forces them, `false` refuses to."
  ([entries] (build entries nil))
  ([entries {:keys [level comment zip64] :or {level 6 zip64 :auto}}]
   (let [prepared (mapv #(prepare % level) entries)
         ;; local records first, so central-directory offsets are known
         [body placed]
         (reduce (fn [[out placed] e]
                   (let [offset (count out)]
                     [(-> out (local-header e) (pbytes (:payload e)))
                      (conj placed (assoc e :offset offset))]))
                 [(transient []) []]
                 prepared)
         cd-offset (count body)
         needs64?  (or (> (count placed) max-u16)
                       (>= cd-offset max-u32)
                       (some #(or (>= (:size %) max-u32) (>= (:csize %) max-u32)) placed))
         zip64?    (case zip64
                     :auto (boolean needs64?)
                     true  true
                     false (if needs64?
                             (throw (ex-info "zip: archive needs ZIP64 but it was disabled"
                                             {:reason :zip64-required
                                              :entries (count placed)
                                              :cd-offset cd-offset}))
                             false))
         with-cd   (reduce (fn [out e] (central-entry out e zip64?)) body placed)
         cd-size   (- (count with-cd) cd-offset)
         comment-bs (if comment (b/str->utf8 comment) [])
         eocd64-at (+ cd-offset cd-size)
         out       (cond-> with-cd
                     zip64?
                     (-> (p32 0x06064b50)
                         (p64 44)                          ; size of this record - 12
                         (p16 (version-made-by true))
                         (p16 version-needed-zip64)
                         (p32 0) (p32 0)                   ; this disk / CD start disk
                         (p64 (count placed))
                         (p64 (count placed))
                         (p64 cd-size)
                         (p64 cd-offset)
                         ;; ZIP64 end-of-central-directory locator
                         (p32 0x07064b50)
                         (p32 0)
                         (p64 eocd64-at)
                         (p32 1))

                     :always
                     (-> (p32 0x06054b50)
                         (p16 0) (p16 0)
                         (p16 (if zip64? max-u16 (count placed)))
                         (p16 (if zip64? max-u16 (count placed)))
                         (p32 (if zip64? max-u32 cd-size))
                         (p32 (if zip64? max-u32 cd-offset))
                         (p16 (count comment-bs))
                         (pbytes comment-bs)))]
     (persistent! out))))
