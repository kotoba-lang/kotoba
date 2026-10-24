(ns kotoba.logistics.readback
  "Read back what `kotoba.logistics.export` writes: an RFC 4180 CSV reader and
  an RFC 8259 JSON reader, for use as test oracles.

  ## Why these are written from the specs rather than from the exporter

  Every export test in this repo used to be a `re-find` over the emitted text.
  A substring match cannot see a field count that drifted away from its header,
  cannot see a quote that was opened and never closed, and cannot see a control
  character that makes the whole document unreadable. It only reports that some
  bytes it already knew about are somewhere in the output.

  The fix is to decode. But a decoder derived from the encoder agrees with the
  encoder by construction, so it proves nothing -- that is the defect ADR-0073
  recorded as \"a test written from the docstring\", and which four different
  repositories reproduced on 2026-08-22. So these two readers are written from
  the grammars (RFC 4180 section 2, RFC 8259 sections 6 and 7) and then pinned
  against an outside implementation: every fixture in `readback-test` carries
  the answer Python's `csv` and `json` modules give for the same bytes, so a
  reader quietly bent to agree with a broken writer fails its own tests first.

  They refuse malformed input instead of guessing. A lenient oracle turns a
  corrupt document into a plausible one and the round trip goes green.

  Portable (.cljc): no host interop, so the same oracle judges the JVM run and
  the ClojureScript run of the suite."
  (:require [kotoba.lang.text :as str]))

(defn- fail [why detail]
  (throw (ex-info (str "malformed document: " (name why))
                  {:readback/why why :readback/detail detail})))

(defn why
  "The `:readback/why` of a refusal, so a test can name which refusal it wanted
  rather than accepting any thrown thing. A test that only asserts \"it threw\"
  counts an unrelated crash as the rejection it was looking for."
  [e]
  (:readback/why (ex-data e)))

;; ---------------------------------------------------------------------------
;; RFC 4180
;; ---------------------------------------------------------------------------

(def ^:private cr \return)
(def ^:private lf \newline)

(defn- terminator? [c] (or (= c cr) (= c lf)))

(defn read-csv
  "Parse `s` as an RFC 4180 document. Returns a vector of records, each a vector
  of field strings.

  RFC 4180 section 2.1 specifies CRLF between records; a lone CR and a lone LF
  also end a record here, because that is what the oracle these fixtures are
  pinned against (Python's `csv` module, `strict=True`, `newline=''`) does, and
  because the point of the exporter quoting a bare CR is precisely that an
  unquoted one would be read as a record boundary.

  Refuses: an unterminated quoted field, a bare quote inside an unquoted field,
  and text after a closing quote."
  [s]
  (let [n (count s)]
    (loop [i 0, state :record-start, cur "", row [], rows []]
      (if (>= i n)
        (case state
          :record-start rows
          :quoted       (fail :unterminated-quoted-field {:at i})
          ;; :field-start :plain :closed -- a record was in progress and the
          ;; document ended without a terminator, which is legal.
          (conj rows (conj row cur)))
        (let [c (nth s i)
              ;; CRLF is one terminator, not two.
              after-term (if (and (= c cr) (< (inc i) n) (= lf (nth s (inc i))))
                           (+ i 2)
                           (inc i))]
          (case state
            :record-start
            (cond
              (= c \")        (recur (inc i) :quoted "" row rows)
              (= c \,)        (recur (inc i) :field-start "" (conj row "") rows)
              (terminator? c) (recur after-term :record-start "" [] (conj rows []))
              :else           (recur (inc i) :plain (str c) row rows))

            :field-start
            (cond
              (= c \")        (recur (inc i) :quoted "" row rows)
              (= c \,)        (recur (inc i) :field-start "" (conj row "") rows)
              (terminator? c) (recur after-term :record-start "" [] (conj rows (conj row "")))
              :else           (recur (inc i) :plain (str c) row rows))

            :plain
            (cond
              (= c \")        (fail :bare-quote-in-unquoted-field {:at i})
              (= c \,)        (recur (inc i) :field-start "" (conj row cur) rows)
              (terminator? c) (recur after-term :record-start "" [] (conj rows (conj row cur)))
              :else           (recur (inc i) :plain (str cur c) row rows))

            :quoted
            (cond
              (not= c \")     (recur (inc i) :quoted (str cur c) row rows)
              ;; "" inside a quoted field is one literal quote (section 2.7).
              (and (< (inc i) n) (= \" (nth s (inc i))))
                              (recur (+ i 2) :quoted (str cur \") row rows)
              :else           (recur (inc i) :closed cur row rows))

            :closed
            (cond
              (= c \,)        (recur (inc i) :field-start "" (conj row cur) rows)
              (terminator? c) (recur after-term :record-start "" [] (conj rows (conj row cur)))
              :else           (fail :text-after-closing-quote {:at i}))))))))

(defn csv-records
  "`read-csv` split into `{:header <vector> :rows <vector of vectors>}`.
  Refuses an empty document -- every exporter here writes a header even when it
  has nothing to report, so no header at all means the export did not run."
  [s]
  (let [rs (read-csv s)]
    (if (empty? rs)
      (fail :no-header {:document s})
      {:header (first rs) :rows (vec (rest rs))})))

(defn csv-column
  "The value of `col` in `row`, addressed by header name rather than position,
  so a test says which column it means and keeps saying it after a column is
  inserted somewhere to its left."
  [{:keys [header]} row col]
  (let [i (first (keep-indexed #(when (= %2 col) %1) header))]
    (cond
      (nil? i)            (fail :no-such-column {:column col :header header})
      (>= i (count row))  (fail :row-shorter-than-header {:column col :row row})
      :else               (nth row i))))

;; ---------------------------------------------------------------------------
;; RFC 8259
;; ---------------------------------------------------------------------------

(def ^:private c0-controls
  "RFC 8259 section 7: U+0000 through U+001F must appear escaped inside a string.
  A reader that accepts them raw cannot tell a correct exporter from one that
  stopped escaping, so this one refuses them exactly as Python's `json` module
  does (\"Invalid control character at ...\")."
  (into #{} (map char) (range 0x20)))

(def ^:private hex-value
  (into {} (concat (map vector "0123456789" (range))
                   (map vector "abcdef" (range 10 16))
                   (map vector "ABCDEF" (range 10 16)))))

(def ^:private ws #{\space \tab \newline \return})

(defn- skip-ws [s i]
  (let [n (count s)]
    (loop [i i] (if (and (< i n) (contains? ws (nth s i))) (recur (inc i)) i))))

(defn- read-str [s i]
  (let [n (count s)]
    (loop [i (inc i), acc ""]
      (if (>= i n)
        (fail :unterminated-string {:at i})
        (let [c (nth s i)]
          (cond
            (= c \")                  [acc (inc i)]
            (contains? c0-controls c) (fail :raw-control-character-in-string {:at i})
            (= c \\)
            (if (>= (inc i) n)
              (fail :truncated-escape {:at i})
              (let [e (nth s (inc i))]
                (case e
                  \" (recur (+ i 2) (str acc \"))
                  \\ (recur (+ i 2) (str acc \\))
                  \/ (recur (+ i 2) (str acc \/))
                  \b (recur (+ i 2) (str acc (char 8)))
                  \f (recur (+ i 2) (str acc (char 12)))
                  \n (recur (+ i 2) (str acc (char 10)))
                  \r (recur (+ i 2) (str acc (char 13)))
                  \t (recur (+ i 2) (str acc (char 9)))
                  \u (let [ds (when (<= (+ i 6) n)
                                (mapv #(hex-value (nth s %)) (range (+ i 2) (+ i 6))))]
                       (if (or (nil? ds) (some nil? ds))
                         (fail :bad-unicode-escape {:at i})
                         (recur (+ i 6)
                                (str acc (char (reduce (fn [a d] (+ (* 16 a) d)) 0 ds))))))
                  (fail :unknown-escape {:at i :escape (str e)}))))
            :else (recur (inc i) (str acc c))))))))

(declare read-value)

(defn- read-array [s i]
  (let [n (count s)]
    (loop [i (skip-ws s (inc i)), acc [], after-comma? false]
      (cond
        (>= i n)         (fail :unterminated-array {:at i})
        (= (nth s i) \]) (if after-comma? (fail :trailing-comma {:at i}) [acc (inc i)])
        :else
        (let [[v j] (read-value s i)
              j (skip-ws s j)]
          (cond
            (>= j n)         (fail :unterminated-array {:at j})
            (= (nth s j) \,) (recur (skip-ws s (inc j)) (conj acc v) true)
            (= (nth s j) \]) [(conj acc v) (inc j)]
            :else            (fail :expected-comma-or-close {:at j})))))))

(defn- read-object [s i]
  (let [n (count s)]
    (loop [i (skip-ws s (inc i)), acc {}, order [], after-comma? false]
      (cond
        (>= i n)            (fail :unterminated-object {:at i})
        (= (nth s i) \})    (if after-comma?
                              (fail :trailing-comma {:at i})
                              [(with-meta acc {:readback/member-order order}) (inc i)])
        (not= (nth s i) \") (fail :expected-member-name {:at i})
        :else
        (let [[k j] (read-str s i)
              j (skip-ws s j)]
          (cond
            (contains? acc k)              (fail :duplicate-member {:at i :member k})
            (or (>= j n) (not= (nth s j) \:)) (fail :expected-colon {:at j})
            :else
            (let [[v j2] (read-value s (inc j))
                  j2 (skip-ws s j2)]
              (cond
                (>= j2 n)         (fail :unterminated-object {:at j2})
                (= (nth s j2) \,) (recur (skip-ws s (inc j2)) (assoc acc k v) (conj order k) true)
                (= (nth s j2) \}) [(with-meta (assoc acc k v)
                                     {:readback/member-order (conj order k)})
                                   (inc j2)]
                :else             (fail :expected-comma-or-close {:at j2})))))))))

(defn- literal-at? [s i lit]
  (and (<= (+ i (count lit)) (count s)) (= lit (subs s i (+ i (count lit))))))

(defn- read-value [s i]
  (let [n (count s)
        i (skip-ws s i)]
    (if (>= i n)
      (fail :unexpected-end-of-document {:at i})
      (let [c (nth s i)]
        (cond
          (= c \")                  (read-str s i)
          (= c \[)                  (read-array s i)
          (= c \{)                  (read-object s i)
          (literal-at? s i "true")  [true (+ i 4)]
          (literal-at? s i "false") [false (+ i 5)]
          :else
          (fail :unsupported-value
                ;; Deliberately narrow. This oracle covers the value grammar
                ;; `kotoba.logistics.export` can emit -- object, array, string,
                ;; true, false -- and refuses numbers and null because no
                ;; document this repo writes contains either. An untested branch
                ;; inside a test oracle is worse than a refusal: it is a place
                ;; where the judge can be wrong without anyone noticing.
                {:at i :saw (subs s i (min n (+ i 8)))}))))))

(defn read-json
  "Parse `s` as an RFC 8259 document. Objects come back as maps carrying their
  member order in `:readback/member-order` metadata, so a test can assert the
  published key order of an export without re-reading the raw text."
  [s]
  (let [[v i] (read-value s 0)
        i (skip-ws s i)]
    (if (< i (count s))
      (fail :trailing-content {:at i})
      v)))

(defn member-order [m] (:readback/member-order (meta m)))

(defn describe
  "A short, printable form of a document, for assertion messages."
  [s]
  (str/join "" (map #(cond (= % \newline) "\\n" (= % \return) "\\r" :else (str %)) s)))
