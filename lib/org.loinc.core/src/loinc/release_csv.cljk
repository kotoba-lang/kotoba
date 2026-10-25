(ns loinc.release-csv
  "A parser for the **column layout** of LOINC's published release
  files (`Loinc.csv` in the official release ZIP) — RFC 4180-shaped CSV,
  header-driven, so a licensee who has downloaded their own copy of the
  release from loinc.org can load it into data this library's other
  namespaces (`loinc.parts`, `loinc.code`) can work with.

  **This module ships no LOINC content whatsoever** — no header list,
  no column count, no code, no term. It is deliberately *header-driven*
  rather than hardcoded to a specific schema, for two reasons: (1) the
  exact column set has grown across LOINC release versions (new columns
  are added; nothing is guaranteed about which of dozens of columns a
  given release has), and this library has no way to verify a hardcoded
  list against a real release file without downloading licensed content,
  which it will not do; (2) a parser that reads *whatever header row is
  actually present* works correctly against any release version a
  licensee supplies, rather than silently mis-columning against a
  version this library's author never saw.

  Input is a plain string (the CSV file's own text, already read by the
  caller) — this namespace does no file/network IO of its own, per the
  library-wide no-IO rule."
  (:require [kotoba.lang.text :as str]))

;; --- RFC 4180 field-level parsing ----------------------------------------
;;
;; A hand-rolled state machine rather than `str/split`, because
;; `split` on `,` breaks the moment any field is quoted and contains a
;; literal comma or embedded newline — both of which are legal, and both
;; of which appear in real LOINC release files (LONG_COMMON_NAME and
;; several other free-text columns routinely contain commas).

;; `field` accumulates as a vector of chars, joined with `apply str` only
;; once the field is complete — not a `java.lang.StringBuilder` (JVM-only,
;; no ClojureScript equivalent) and not repeated `str` concatenation
;; (quadratic). `(nth s i)` / `count` on a string work identically on
;; both runtimes for reading.
(defn- parse-row
  "Parse one CSV record starting at `i` in `s` (a full multi-row CSV
  text). Returns `[fields next-i]`, where `next-i` is the index just
  past the record's terminating newline (or `(count s)` at EOF)."
  [s i]
  (let [n (count s)]
    (loop [i i field [] fields [] in-quotes? false]
      (if (>= i n)
        [(conj fields (apply str field)) i]
        (let [c (nth s i)]
          (cond
            in-quotes?
            (cond
              ;; `""` inside a quoted field is a literal `"`.
              (and (= c \") (< (inc i) n) (= (nth s (inc i)) \"))
              (recur (+ i 2) (conj field \") fields true)

              (= c \")
              (recur (inc i) field fields false)

              :else
              (recur (inc i) (conj field c) fields true))

            (= c \")
            (recur (inc i) field fields true)

            (= c \,)
            (recur (inc i) [] (conj fields (apply str field)) false)

            (= c \newline)
            [(conj fields (apply str field)) (inc i)]

            (and (= c \return) (< (inc i) n) (= (nth s (inc i)) \newline))
            [(conj fields (apply str field)) (+ i 2)]

            (= c \return) ; lone CR line ending
            [(conj fields (apply str field)) (inc i)]

            :else
            (recur (inc i) (conj field c) fields in-quotes?)))))))

(defn parse-rows
  "Parse `s` (full CSV text) into a vector of rows, each a vector of
  field strings. A trailing blank line at EOF is dropped (the common
  \"file ends with a newline\" case), not returned as a spurious
  single-empty-field row."
  [s]
  (let [n (count s)]
    (loop [i 0 rows []]
      (if (>= i n)
        rows
        (let [[fields next-i] (parse-row s i)]
          (recur next-i
                 (if (and (= next-i n) (= fields [""]))
                   rows
                   (conj rows fields))))))))

;; --- header-driven row -> map --------------------------------------------

(defn rows->maps
  "`rows` (as from `parse-rows`) -> a seq of `{keyword column-value}`
  maps, using `rows`'s first row as the header (column name -> keyword,
  verbatim — `\"LOINC_NUM\"` becomes `:LOINC_NUM`, not renamed or
  reordered, so field names in the caller's data always match the
  release file's own column names exactly). A row with a different
  field count than the header is reported per-row as `[:error
  :loinc/row-field-count-mismatch]` rather than silently
  zipped/truncated. Returns `[:error :loinc/empty-csv]` for `rows`
  with no header row at all."
  [rows]
  (if (empty? rows)
    [:error :loinc/empty-csv]
    (let [header (mapv keyword (first rows))
          n (count header)]
      [:ok (mapv (fn [row]
                    (if (= n (count row))
                      (zipmap header row)
                      [:error :loinc/row-field-count-mismatch]))
                  (rest rows))])))

(defn parse
  "Parse full LOINC release-CSV text `s` directly into `[:ok [row-maps...]]`,
  or `[:error reason]`. Convenience composition of `parse-rows` +
  `rows->maps`."
  [s]
  (rows->maps (parse-rows s)))
