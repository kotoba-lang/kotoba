(ns csv.core
  "CSV per RFC 4180, in portable `.cljc`. Zero dependencies.

  CSV looks like `split(\",\")` and is not. Everything hard about it is in the
  quoting rules, and every one of them is a case where the naive parser
  produces *plausible wrong rows* rather than an error:

  - **A quoted field may contain commas.** `a,\"b,c\",d` is three fields.
  - **A quoted field may contain newlines.** So a CSV record is not a line,
    and any parser built on `split-lines` is wrong before it starts — it is
    also the reason this cannot be a scanning reader: you cannot seek to
    record N without having read everything before it.
  - **A quote inside a quoted field is doubled.** `\"say \"\"hi\"\"\"` is
    `say \"hi\"`.
  - **Line endings are CRLF in the spec and LF everywhere in practice**, and
    a file with CRLF parsed as LF leaves a trailing `\\r` on the last field of
    every row — which compares unequal to the same string, silently, forever.

  ## What this does not decide

  **Types.** Every field comes back a string. `\"1\"` might be an integer, a
  zip code that must keep its leading zero, or a version number; RFC 4180 has
  no type system and inventing one here would make the parser's guess
  unrecoverable. A caller that knows the schema converts.

  **Whether row one is a header.** `read-csv` returns rows; `read-maps` treats
  the first as a header because a caller said so. A parser that sniffs for a
  header gets it wrong on exactly the files where every value looks like a
  name."
  (:require [kotoba.lang.text :as str]))

(def ^:private quote-ch \")

(defn read-csv
  "Parse `text` into a vector of vectors of strings.

  `:separator` defaults to `\\,` — `\\tab` parses TSV, which is the same
  grammar with a different delimiter rather than a different format.

  A final record without a trailing newline is returned; a trailing newline
  does **not** produce an empty final record. Those two are the same character
  sequence apart from one byte, and treating them alike is how a row count
  ends up one off."
  ([text] (read-csv text {}))
  ([text {:keys [separator] :or {separator \,}}]
   (let [n (count text)]
     ;; A vector of chars, not StringBuilder: that class is JVM-only, and
     ;; `(str acc c)` in a loop is quadratic in the field length. This is
     ;; portable and amortised; `apply str` at the field boundary is the only
     ;; place a string is built.
     (loop [i 0, field [], row [], rows [], quoted? false, any? false]
       (if (= i n)
         ;; End of input. A field is emitted unless nothing at all was seen
         ;; since the last record boundary — which is what distinguishes
         ;; "file ends with a newline" from "file ends with an empty field".
         (let [f (apply str field)]
           (if (or any? (seq f))
             (conj rows (conj row f))
             rows))
         (let [c (nth text i)]
           (cond
             quoted?
             (cond
               (not= c quote-ch) (recur (inc i) (conj field c) row rows true true)
               ;; A doubled quote inside quotes is one literal quote.
               (and (< (inc i) n) (= quote-ch (nth text (inc i))))
               (recur (+ i 2) (conj field quote-ch) row rows true true)
               :else (recur (inc i) field row rows false true))

             (= c quote-ch) (recur (inc i) field row rows true true)

             (= c separator)
             (recur (inc i) [] (conj row (apply str field)) rows false true)

             (= c \newline)
             (recur (inc i) [] [] (conj rows (conj row (apply str field))) false false)

             ;; CRLF: consume the CR only when it precedes LF. A lone CR is
             ;; data — old Mac line endings are not RFC 4180, and dropping the
             ;; character would corrupt a field that legitimately holds one.
             (and (= c \return) (< (inc i) n) (= \newline (nth text (inc i))))
             (recur (+ i 2) [] [] (conj rows (conj row (apply str field))) false false)

             :else (recur (inc i) (conj field c) row rows false true))))))))

(defn read-maps
  "Parse `text` treating the first record as a header. -> vector of maps.

  A row shorter than the header omits the missing keys rather than filling
  them with `nil` or `\"\"`: absent and empty are different in CSV — `a,,b`
  has an empty middle field, and `a,b` has no third one at all — and a parser
  that flattens them takes that distinction away from every caller.

  A row longer than the header keeps the extra fields under their index, so
  they are visible rather than dropped."
  ([text] (read-maps text {}))
  ([text opts]
   (let [[header & rows] (read-csv text opts)]
     (if-not header
       []
       (mapv (fn [row]
               (into {} (map-indexed (fn [i v] [(nth header i (str i)) v])) row))
             rows)))))

(defn write-csv
  "Rows -> RFC 4180 text. Quotes a field when, and only when, leaving it bare
  would change what it parses back as."
  ([rows] (write-csv rows {}))
  ([rows {:keys [separator newline] :or {separator \, newline "\r\n"}}]
   (let [needs? (fn [s] (or (str/includes? s (str separator))
                            (str/includes? s "\"")
                            (str/includes? s "\n")
                            (str/includes? s "\r")))
         cell (fn [v] (let [s (str v)]
                        (if (needs? s)
                          (str quote-ch (str/replace s "\"" "\"\"") quote-ch)
                          s)))]
     (str/join newline (map (fn [row] (str/join (str separator) (map cell row))) rows)))))
