(ns kotobase.lake.sniff
  "Bounded magic-byte classification of an object's leading bytes.

  Three properties make this safe to put on a lake's write path, and all
  three are structural rather than tested:

  1. **It reads a bounded prefix.** `prefix-bytes` bytes, never more. The
     bound is not a convention the caller is asked to honour -- `classify`
     takes the prefix, so there is no argument through which a caller could
     hand it a gigabyte.
  2. **It never parses.** Every rule is a byte comparison at a fixed offset.
     Nothing here can throw on malformed input, because nothing here reads
     structure.
  3. **`nil` is the normal answer.** An unrecognised object is not an error,
     not a rejection, and not a guess. Most of what a lake receives is
     unrecognisable and that must cost nothing.

  ## What the bound excludes, concretely

  `prefix-bytes` is 512 rather than 64 so that `tar` (`ustar` at offset 257)
  is reachable. ISO 9660 puts `CD001` at offset 32769 and is therefore
  **undetectable here by construction** -- stated rather than discovered,
  because a bound whose cost is unknown is a bound nobody can evaluate.

  ## What has no magic bytes at all

  CSV, TSV, JSON, NDJSON, EDN, YAML, plain text and every log format are
  undetectable by any prefix rule, at any bound. This is not a gap to be
  closed later. It is the reason `:object/media-type` must survive as a
  *claim* on the ingest record instead of being replaced by what the lake
  observed: for a large share of real data, observation has nothing to say."
  (:require [kotoba.lang.text :as str]))

(def prefix-bytes
  "How many leading bytes `prefix` retains. See the namespace docstring for
  what this bound excludes."
  512)

;; ── byte coercion ──────────────────────────────────────────────────────────

(defn- unsigned [b]
  (bit-and (long b) 0xff))

(defn prefix
  "The leading `prefix-bytes` of `data`, as a vector of unsigned ints.

  Accepts a JVM `byte[]`, a JS `Uint8Array`, or any sequential collection of
  numbers. Returns `[]` for nil or empty input -- an empty object is a
  perfectly ordinary thing to land in a lake."
  [data]
  (cond
    (nil? data) []

    #?@(:clj [(bytes? data)
              (into [] (comp (take prefix-bytes) (map unsigned)) data)]
        :cljs [(instance? js/Uint8Array data)
               (into [] (comp (take prefix-bytes) (map unsigned)) (array-seq data))])

    (sequential? data)
    (into [] (comp (take prefix-bytes) (map unsigned)) data)

    :else
    (throw (ex-info "not byte-like" {:kotobase.lake/error :not-byte-like
                                     :type (str (type data))}))))

(defn ascii-bytes
  "An ASCII string as a vector of unsigned bytes.

  Public, and used by the rule table and by the tests, because the obvious
  one-liner is wrong on exactly one of the two runtimes: seq-ing a string
  yields `Character` on the JVM (where `int` is the code point) and
  single-character *strings* in ClojureScript (where `(int \"%\")` is **0**,
  silently). A private copy of this would be duplicated into every caller
  that needs byte literals, which is how that defect spreads -- it did, into
  this repo's own test helpers, and the JVM suite stayed green while every
  ASCII magic became all-zeros under cljs."
  [s]
  #?(:clj  (mapv #(bit-and (int ^char %) 0xff) s)
     :cljs (mapv #(bit-and (.charCodeAt s %) 0xff) (range (count s)))))

(def ^:private ascii ascii-bytes)

(defn- matches-at?
  "True when `pat` (a vector of unsigned ints) occurs in `pfx` at `offset`."
  [pfx offset pat]
  (let [n (count pat)]
    (and (<= (+ offset n) (count pfx))
         (loop [i 0]
           (cond
             (= i n) true
             (= (nth pfx (+ offset i)) (nth pat i)) (recur (inc i))
             :else false)))))

;; ── the rule table ─────────────────────────────────────────────────────────
;;
;; `:media-type` is the canonical name the claim is compared against. It is
;; deliberately the same vocabulary a producer would declare, so
;; `declared-vs-observed` compares like with like instead of comparing a
;; keyword to a MIME string.

(def rules
  "Ordered magic-byte rules. First match wins; order matters only where one
  signature is a prefix of another."
  [{:format :pdf      :media-type "application/pdf"                :offset 0 :magic (ascii "%PDF-")}
   {:format :png      :media-type "image/png"                      :offset 0 :magic [0x89 0x50 0x4E 0x47 0x0D 0x0A 0x1A 0x0A]}
   {:format :jpeg     :media-type "image/jpeg"                     :offset 0 :magic [0xFF 0xD8 0xFF]}
   {:format :gif      :media-type "image/gif"                      :offset 0 :magic (ascii "GIF8")}
   {:format :webp     :media-type "image/webp"                     :offset 8 :magic (ascii "WEBP")}
   {:format :riff     :media-type "application/x-riff"             :offset 0 :magic (ascii "RIFF")}
   {:format :matroska :media-type "video/x-matroska"               :offset 0 :magic [0x1A 0x45 0xDF 0xA3]}
   {:format :ogg      :media-type "application/ogg"                :offset 0 :magic (ascii "OggS")}
   {:format :iso-bmff :media-type "video/mp4"                      :offset 4 :magic (ascii "ftyp")}
   {:format :wasm     :media-type "application/wasm"               :offset 0 :magic [0x00 0x61 0x73 0x6D]}
   {:format :elf      :media-type "application/x-elf"              :offset 0 :magic [0x7F 0x45 0x4C 0x46]}
   {:format :sqlite   :media-type "application/vnd.sqlite3"        :offset 0 :magic (ascii "SQLite format 3")}
   {:format :parquet  :media-type "application/vnd.apache.parquet" :offset 0 :magic (ascii "PAR1")}
   {:format :arrow    :media-type "application/vnd.apache.arrow.file" :offset 0 :magic (ascii "ARROW1")}
   {:format :orc      :media-type "application/vnd.apache.orc"     :offset 0 :magic (ascii "ORC")}
   {:format :avro     :media-type "application/vnd.apache.avro"    :offset 0 :magic [0x4F 0x62 0x6A 0x01]}
   {:format :gzip     :media-type "application/gzip"               :offset 0 :magic [0x1F 0x8B]}
   {:format :zstd     :media-type "application/zstd"               :offset 0 :magic [0x28 0xB5 0x2F 0xFD]}
   {:format :bzip2    :media-type "application/x-bzip2"            :offset 0 :magic (ascii "BZh")}
   {:format :xz       :media-type "application/x-xz"               :offset 0 :magic [0xFD 0x37 0x7A 0x58 0x5A 0x00]}
   {:format :sevenzip :media-type "application/x-7z-compressed"    :offset 0 :magic [0x37 0x7A 0xBC 0xAF 0x27 0x1C]}
   {:format :zip      :media-type "application/zip"                :offset 0 :magic [0x50 0x4B]}
   ;; ustar sits at 257 -- the single rule that decides `prefix-bytes`.
   {:format :tar      :media-type "application/x-tar"              :offset 257 :magic (ascii "ustar")}])

(def sniffer-version
  "Bumped whenever `rules` changes.

  A classification is a function of the bytes AND the classifier, so it is
  recorded against this version rather than presented as a timeless property
  of the object -- see `kotobase.lake.catalog`."
  "kotobase.lake.sniff/1")

(defn classify
  "Classify a `prefix`. Returns `{:format kw :media-type s}` or **nil**.

  nil means *this classifier recognised nothing*, which is the expected
  outcome for text, columnar-adjacent formats without leading magic, encrypted
  bytes, and anything newer than `rules`. It is never an error."
  [pfx]
  (when (seq pfx)
    (some (fn [{:keys [offset magic] :as rule}]
            (when (matches-at? pfx offset magic)
              (select-keys rule [:format :media-type])))
          rules)))

(defn sniff
  "Convenience: `prefix` then `classify`. Safe on nil and on empty input."
  [data]
  (classify (prefix data)))

(defn normalize-media-type
  "Lower-cased type/subtype with parameters dropped, for comparison only.

  `text/csv; charset=utf-8` and `TEXT/CSV` compare equal. Returns nil for
  nil/blank -- absent is not the empty string."
  [mt]
  (when (and mt (not (str/blank? mt)))
    (-> mt (str/split #";") first str/trim str/lower)))
