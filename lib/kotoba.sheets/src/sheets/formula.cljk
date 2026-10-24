(ns sheets.formula
  "What `=SUM(B2:B9)` comes to.

  A workbook here could hold a formula and never compute one. `sheets.xlsx`
  writes `<f>` with no cached value on purpose — Excel recalculates on open,
  which is correct — but inside this Drive a spreadsheet showed the text
  `=SUM(B2:B9)` for ever. Computing is the whole point of a spreadsheet.

  ## Nothing is stored

  `values` takes a tab and returns what each cell comes to *now*. A computed
  value written back into `:sheets/value` would be a second copy of something
  derived, stale the moment any input changed, and indistinguishable
  afterwards from a value somebody typed. The model holds formulas; this
  answers what they mean.

  ## Cells hold text, and that is not undone here

  `sheets.csv` reads every field as a string, and `sheets.xlsx` writes every
  cell as one, both for the same stated reason: guessing is how a part number
  becomes a float. So evaluation parses text to a number *where a number is
  required*, and says so when it cannot — it does not decide that `0042` was
  a number all along.

  Which follows Excel: `=A1+1` over text is `#VALUE!`, while `=SUM(A1:A9)`
  ignores the text in the range. The difference is that arithmetic asks for
  a number and an aggregate asks for the numbers there are.

  ## Errors are values

  `#DIV/0!`, `#VALUE!`, `#NAME?`, `#REF!`, `#CIRCULAR!` — a cell whose
  formula cannot be computed holds the reason, which is what a spreadsheet
  does and is more useful than an empty cell or a thrown exception. They
  propagate: a sum over a range containing `#DIV/0!` is `#DIV/0!`, because
  the alternative is a total that silently omits a number nobody can see is
  missing."
  (:require [kotoba.lang.text :as str]
            [sheets.model :as model]))

(def error-values
  "The strings a cell holds when its formula cannot be computed."
  #{"#DIV/0!" "#VALUE!" "#NAME?" "#REF!" "#CIRCULAR!" "#N/A"})

(defn error? [x] (contains? error-values (str x)))

;; ── reading a formula ───────────────────────────────────────────────────────

(defn- number-token [s i]
  (let [n (count s)]
    (loop [j i seen-dot? false]
      (cond
        (>= j n) [(subs s i j) j]
        (= \. (nth s j)) (if seen-dot? [(subs s i j) j] (recur (inc j) true))
        (contains? (set "0123456789") (nth s j)) (recur (inc j) seen-dot?)
        :else [(subs s i j) j]))))

(def ^:private stops
  "The characters a word ends at: whitespace, operators, punctuation, quote.

  Defined as what stops a word rather than as what a word contains, because
  a named range here is as likely to be 売上 as Sales. An allowlist of ASCII
  letters would make every non-English name unspellable, which is a strange
  thing for this Drive to decide."
  (set " \t\n+-*/^%(),:<>=&\"'!"))

(defn- word-token
  "A run of anything that is not a stop — a cell reference, a function name,
  or a named range, which cannot be told apart until something follows."
  [s i]
  (let [n (count s)]
    (loop [j i]
      (if (and (< j n) (not (contains? stops (nth s j))))
        (recur (inc j))
        [(subs s i j) j]))))

(defn- string-token
  "A double-quoted literal. `\"\"` inside one is a literal quote, which is how
  a spreadsheet spells it and not how most languages do."
  [s i]
  (let [n (count s)]
    (loop [j (inc i) out []]
      (cond
        (>= j n) [(apply str out) j]
        (= \" (nth s j)) (if (and (< (inc j) n) (= \" (nth s (inc j))))
                           (recur (+ j 2) (conj out \"))
                           [(apply str out) (inc j)])
        :else (recur (inc j) (conj out (nth s j)))))))

(defn tokens
  "A formula as tokens. Never throws — an unreadable one becomes tokens the
  parser refuses, which is a `#NAME?` in a cell rather than a 500."
  [s]
  (let [s (str s)
        n (count s)]
    (loop [i 0 out []]
      (if (>= i n)
        out
        (let [c (nth s i)]
          (cond
            (contains? (set " \t\n") c) (recur (inc i) out)
            (contains? (set "0123456789") c)
            (let [[t j] (number-token s i)] (recur j (conj out [:number t])))
            (= \" c) (let [[t j] (string-token s i)] (recur j (conj out [:string t])))
            ;; A single-quoted run is a *sheet name*, not a string literal —
            ;; a spreadsheet spells `'売上 表'!A1` that way, and there is no
            ;; single-quoted string in a formula for it to be confused with.
            (= \' c) (let [j (or (str/index-of s "'" (inc i)) (count s))]
                       (recur (inc j) (conj out [:word (subs s (inc i) j)])))
            (= \! c) (recur (inc i) (conj out [:bang "!"]))
            (contains? (set "+-*/^%(),:") c)
            (recur (inc i) (conj out [(get {\( :lparen \) :rparen \, :comma
                                            \: :colon}
                                           c :op)
                                      (str c)]))
            (and (= \< c) (< (inc i) n) (= \= (nth s (inc i))))
            (recur (+ i 2) (conj out [:op "<="]))
            (and (= \< c) (< (inc i) n) (= \> (nth s (inc i))))
            (recur (+ i 2) (conj out [:op "<>"]))
            (and (= \> c) (< (inc i) n) (= \= (nth s (inc i))))
            (recur (+ i 2) (conj out [:op ">="]))
            (contains? (set "<>=") c) (recur (inc i) (conj out [:op (str c)]))
            (= \& c) (recur (inc i) (conj out [:op "&"]))
            :else (let [[t j] (word-token s i)]
                    (if (= i j)
                      ;; A character nothing knows. Consumed rather than
                      ;; looped on for ever.
                      (recur (inc i) (conj out [:unknown (str c)]))
                      (recur j (conj out [:word t]))))))))))

(defn parse-ref
  "`B12` or `$B$12` → `[row col]`, or nil.

  `$` is absolute addressing, which matters when a formula is copied and
  nothing here copies formulas — so it is accepted and ignored rather than
  refused, because refusing it would reject a file Excel wrote."
  [word]
  (when-let [[_ letters digits]
             (re-matches #"\$?([A-Za-z]{1,3})\$?(\d{1,7})" (str word))]
    (when-let [col (model/column-number letters)]
      [#?(:clj (Long/parseLong digits) :cljs (js/parseInt digits 10)) col])))

;; ── moving what a formula points at ─────────────────────────────────────────
;;
;; Inserting a row above a formula's target has to move the reference with
;; it, or the formula quietly starts reading somebody else's number. That is
;; the reason `sheets.model/sort-range` refuses a range with a formula in it:
;; sorting moves rows arbitrarily and there is no rule that keeps a reference
;; pointing at the same value. Inserting and deleting are different — every
;; row moves by the same amount, in one direction — so there is a rule, and
;; it is the one every spreadsheet uses.

(defn- word-char?
  "Whether `c` can be part of a name or a reference.

  A regular expression on the one character rather than
  `Character/isLetterOrDigit`, which is the JVM's and this file is `.cljc` —
  the kind of thing that compiles here and throws under nbb."
  [c]
  (boolean (re-matches #"[A-Za-z0-9_$]" (str c))))

(def ^:private ref-pattern
  ;; `$` kept, because a formula that said `$B$2` should still say it: the
  ;; dollars are about copying, which nothing here does, and rewriting them
  ;; away would change a file Excel wrote for no reason. They do not stop the
  ;; shift — inserting a row above `$B$2` moves it to `$B$3` in Excel too.
  #"(\$?)([A-Za-z]{1,3})(\$?)(\d{1,7})")

(defn- rebuild-ref
  "`text` with its row or column replaced by `value`, `$` kept."
  [text axis value]
  (when-let [[_ col-abs letters row-abs digits] (re-matches ref-pattern text)]
    (if (= :row axis)
      (str col-abs letters row-abs value)
      (str col-abs (model/column-name value) row-abs digits))))

(defn- shifted-ref
  "One reference after `n` rows or columns are inserted at `at`, or nil when
  the thing it pointed at is gone.

  `n` is negative for a deletion. A reference into the deleted band has
  nothing left to point at, which is `#REF!` — the same answer a spreadsheet
  gives, and a better one than an address that now means a different cell."
  [text axis at n]
  (when-let [[_ col-abs letters row-abs digits] (re-matches ref-pattern text)]
    (when-let [col (model/column-number letters)]
      (let [row #?(:clj (Long/parseLong digits) :cljs (js/parseInt digits 10))
            value (if (= :row axis) row col)
            moved (cond
                    (< value at) value
                    (and (neg? n) (< value (+ at (- n)))) nil
                    :else (+ value n))]
        (when moved
          (if (= :row axis)
            (str col-abs letters row-abs moved)
            (str col-abs (model/column-name moved) row-abs digits)))))))

(defn- range-partner
  "`[end other]` when a `:` and a second reference follow position `j`.

  The two halves of `B2:B9` are separate words to the scanner, and moving
  them separately is what produced `B2:#REF!` for a row removed from inside
  a range."
  [s j end]
  (let [skip (fn [i] (loop [i i] (if (and (< i end) (contains? #{\space \tab} (nth s i)))
                                   (recur (inc i)) i)))
        colon (skip j)]
    (when (and (< colon end) (= \: (nth s colon)))
      (let [start (skip (inc colon))
            stop (loop [i start] (if (and (< i end) (word-char? (nth s i))) (recur (inc i)) i))]
        (when (> stop start) [stop (subs s start stop)])))))

(defn- shifted-range
  "Both ends of a range after the shift.

  An endpoint inside a removed band is clamped to the edge rather than lost:
  the range still names the rows that are left. When nothing is left — the
  band swallowed the whole range — the answer is `#REF!`, once, for the
  range rather than for each end."
  [from to axis at n]
  (let [value (fn [text] (let [[row col] (parse-ref text)] (if (= :row axis) row col)))
        a (value from) b (value to)
        low (min a b) high (max a b)]
    (if-not (neg? n)
      (str (shifted-ref from axis at n) ":" (shifted-ref to axis at n))
      (let [band-end (+ at (- n))
            clamp (fn [v edge]
                    (cond (< v at) v
                          (< v band-end) edge
                          :else (+ v n)))
            low' (clamp low at)
            high' (clamp high (dec at))]
        (if (> low' high')
          "#REF!"
          ;; Rendered from the clamped value rather than shifted again:
          ;; `shifted-ref` would apply the band rule a second time and turn
          ;; the endpoint it had just been clamped *to* into `#REF!`.
          (str (rebuild-ref from axis (if (= a low) low' high'))
               ":"
               (rebuild-ref to axis (if (= b high) high' low'))))))))

(defn shift-refs
  "`expr` with its cell references moved, as text.

  `axis` is `:row` or `:col`, `at` the first row or column affected, and `n`
  how many were inserted — negative for a deletion. A reference to something
  that was deleted becomes `#REF!`.

  Scanned rather than tokenised and re-emitted. `tokens` throws away
  whitespace, so rebuilding a formula from it would hand back `A1+B2` for
  `A1 + B2` — a diff on every formula in the tab, for a change that touched
  none of them. The scan only has to know the two things that make a run of
  characters not a reference: a double-quoted string is text, and a
  single-quoted run is a sheet name.

  `tab` and `home` say which sheet is being changed and which one this
  formula lives on. A bare `B2` means the formula's own sheet; `売上!B2`
  means that one. Without both, inserting a row in one tab would move the
  references in every other tab, which is the same bug in the other
  direction."
  ([expr axis at n] (shift-refs expr axis at n nil nil))
  ([expr axis at n tab home]
   (let [s (str expr)
         end (count s)
         applies? (fn [qualifier]
                    (or (nil? tab)
                        (if qualifier (= qualifier tab) (= home tab))))]
     (loop [i 0 out "" qualifier nil]
       (if (>= i end)
         out
         (let [c (nth s i)]
           (cond
             ;; A string literal: copied, and it clears the qualifier — the
             ;; word after one cannot be a sheet-qualified reference.
             (= \" c)
             (let [j (loop [j (inc i)]
                       (cond (>= j end) end
                             (and (= \" (nth s j)) (< (inc j) end) (= \" (nth s (inc j))))
                             (recur (+ j 2))
                             (= \" (nth s j)) (inc j)
                             :else (recur (inc j))))]
               (recur j (str out (subs s i j)) nil))

             ;; A quoted sheet name, which is the qualifier for the
             ;; reference after the `!`.
             (= \' c)
             (let [j (or (str/index-of s "'" (inc i)) end)]
               (recur (inc j) (str out (subs s i (inc j))) (subs s (inc i) j)))

             (word-char? c)
             (let [j (loop [j i]
                       (if (and (< j end)
                                (word-char? (nth s j)))
                         (recur (inc j))
                         j))
                   word (subs s i j)
                   ;; A word followed by `!` is a sheet name, not a
                   ;; reference — `Sheet1!A1` has two words in it.
                   sheet? (and (< j end) (= \! (nth s j)))]
               (cond
                 sheet? (recur j (str out word) word)
                 (applies? qualifier)
                 ;; A range is moved as a range. `B2:B3` with row 3 removed
                 ;; is `B2:B2` and not `B2:#REF!` — an endpoint inside the
                 ;; removed band is clamped to the edge of it, which is what
                 ;; a spreadsheet does and what makes deleting a row inside
                 ;; a SUM the ordinary thing it should be. Only a range with
                 ;; nothing left in it becomes `#REF!`.
                 (let [[pair-end other] (range-partner s j end)]
                   (if (and pair-end (parse-ref word) (parse-ref other))
                     (recur pair-end
                            (str out (shifted-range word other axis at n))
                            nil)
                     (recur j (str out (or (shifted-ref word axis at n)
                                           (if (parse-ref word) "#REF!" word)))
                            nil)))
                 :else (recur j (str out word) nil)))

             ;; `!` keeps the qualifier the word before it set; anything else
             ;; clears it.
             (= \! c) (recur (inc i) (str out c) qualifier)
             :else (recur (inc i) (str out c) nil))))))))

;; ── the grammar ─────────────────────────────────────────────────────────────
;;
;; Precedence, loosest first: comparison, `&`, `+ -`, `* /`, `^`, unary `-`,
;; then a primary. Recursive descent, one function per level, which is the
;; shape the grammar already has.

(declare parse-expr)

(defn- parse-args [ts]
  (loop [ts ts args []]
    (if (or (empty? ts) (= :rparen (first (first ts))))
      [args (rest ts)]
      (let [[a ts] (parse-expr ts)
            args (conj args a)]
        (if (= :comma (first (first ts)))
          (recur (rest ts) args)
          [args (rest ts)])))))

(defn- parse-primary [ts]
  (let [[kind text] (first ts)]
    (cond
      (nil? kind) [[:error "#NAME?"] nil]
      (= :number kind) [[:num text] (rest ts)]
      (= :string kind) [[:str text] (rest ts)]
      (and (= :op kind) (= "-" text))
      (let [[e ts] (parse-primary (rest ts))] [[:neg e] ts])
      (and (= :op kind) (= "+" text)) (parse-primary (rest ts))

      (= :lparen kind)
      (let [[e ts] (parse-expr (rest ts))]
        [e (if (= :rparen (first (first ts))) (rest ts) ts)])

      (= :word kind)
      (cond
        ;; `売上表!A1` and `'売上 表'!A1:A3` — a reference on another sheet.
        ;; The sheet name is a word here whether it was quoted or not, so
        ;; both spellings arrive the same shape.
        (= :bang (first (first (rest ts))))
        (let [after (rest (rest ts))
              from (second (first after))]
          (if (= :colon (first (first (rest after))))
            [[:range from (second (first (rest (rest after)))) text]
             (rest (rest (rest after)))]
            [[:ref from text] (rest after)]))

        ;; A name followed by `(` is a call; otherwise it is a reference,
        ;; and a reference that is not one is `#NAME?`.
        (= :lparen (first (first (rest ts))))
        (let [[args ts] (parse-args (rest (rest ts)))]
          [[:call (str/upper text) args] ts])

        ;; `A1:B9` — a range, which only means anything inside a call.
        (= :colon (first (first (rest ts))))
        [[:range text (second (first (rest (rest ts))))] (rest (rest (rest ts)))]

        ;; A cell reference or a named range — and which it is cannot be
        ;; decided here, because names live on the workbook and this only
        ;; has the text. `eval-node` resolves it and answers `#NAME?` if it
        ;; is neither.
        :else [[:ref text] (rest ts)])

      :else [[:error "#NAME?"] (rest ts)])))

(defn- parse-binary [ts levels]
  (if (empty? levels)
    (parse-primary ts)
    (let [ops (first levels)]
      (loop [[left ts] (parse-binary ts (rest levels))]
        (let [[kind text] (first ts)
              op (when (= :op kind) text)]
          (if (and op (contains? ops op))
            (let [[right ts] (parse-binary (rest ts) (rest levels))]
              (recur [[:op op left right] ts]))
            [left ts]))))))

(def ^:private precedence
  [#{"=" "<>" "<" ">" "<=" ">="} #{"&"} #{"+" "-"} #{"*" "/"} #{"^"}])

(defn- parse-expr [ts] (parse-binary ts precedence))

(defn parse
  "A formula's text as a tree. Never throws."
  [text]
  (let [text (str text)
        text (if (str/starts-with? text "=") (subs text 1) text)]
    (first (parse-expr (tokens text)))))

;; ── computing ───────────────────────────────────────────────────────────────

(defn as-number
  "Text as a number, or nil. The one place a string becomes one, and only
  because something asked for a number.

  Public because a chart has to ask the same question of the same values,
  and a second answer to \"is this a number\" is how a total and a bar come
  to disagree."
  [x]
  (cond
    (number? x) x
    (nil? x) nil
    :else (let [s (str/trim (str x))]
            (when-not (str/blank? s)
              #?(:clj (try (Double/parseDouble s) (catch Exception _ nil))
                 :cljs (let [n (js/parseFloat s)]
                         (when (and (not (js/isNaN n))
                                    (re-matches #"[-+]?[0-9]*\.?[0-9]+([eE][-+]?[0-9]+)?" s))
                           n)))))))

(defn format-number
  "A number as the text a cell holds.

  An integer without a decimal point, because `120.0` in a cell is a number
  wearing floating point's clothes. Anything else to ten significant places
  and no trailing zeros, which is enough to not surprise and not enough to
  show the noise at the end of a double."
  [n]
  (let [d (double n)]
    (cond
      ;; `(not= d d)` is the portable NaN test — it is the only value that is
      ;; not equal to itself, and `Double/isNaN` exists on one host only.
      (not= d d) "#VALUE!"
      #?(:clj (Double/isInfinite d) :cljs (not (js/isFinite d))) "#VALUE!"
      (zero? (mod d 1)) (str (long d))
      :else (-> #?(:clj (format "%.10f" d) :cljs (.toFixed d 10))
                (str/replace #"0+$" "")
                (str/replace #"\.$" "")))))

(declare value-at)

(defn- numbers-in
  "Every number in a list of evaluated arguments, ranges flattened.

  Text is skipped rather than refused, which is what an aggregate does: a
  column of amounts with a heading on top sums to the amounts."
  [xs]
  (keep as-number (flatten xs)))

(defn- compare-op [op a b]
  (let [na (as-number a) nb (as-number b)
        [x y] (if (and na nb) [na nb] [(str a) (str b)])
        c (compare x y)]
    (case op
      "=" (zero? c) "<>" (not (zero? c))
      "<" (neg? c) ">" (pos? c)
      "<=" (not (pos? c)) ">=" (not (neg? c))
      false)))

(defn- truthy?
  "Whether a value is true for `IF`, `AND`, `OR` and `NOT`.

  A spreadsheet has booleans and this model has text, so both spellings
  count: `TRUE` from a comparison, and a non-zero number. Empty text and
  zero are false, which is Excel's rule and what somebody writing
  `IF(A1,…)` means."
  [x]
  (cond
    (boolean? x) x
    (nil? x) false
    (= "" (str x)) false
    (as-number x) (not (zero? (as-number x)))
    (= "FALSE" (str/upper (str x))) false
    :else true))

(defn- matches?
  "Whether `v` satisfies a criterion the way `SUMIF` means it.

  A criterion is a value to equal, or a comparison written as text —
  `\">1000\"`, `\"<>Q1\"`. That second form is a spreadsheet convention and
  not a general one: the operator is part of the *string*, so a criterion
  reading `>1000` tests a comparison and one reading `1000` tests equality."
  [v criterion]
  (let [c (str criterion)]
    (if-let [[_ op rest'] (re-matches #"(<=|>=|<>|<|>|=)(.*)" c)]
      (compare-op op v rest')
      (let [nv (as-number v) nc (as-number c)]
        (if (and nv nc) (== nv nc) (= (str v) c))))))

(defn- apply-fn [name args]
  (let [nums (numbers-in args)
        flat (flatten args)]
    (cond
      (some error? flat) (first (filter error? flat))
      :else
      (case name
        "SUM" (reduce + 0 nums)
        "AVERAGE" (if (seq nums) (/ (reduce + 0.0 nums) (count nums)) "#DIV/0!")
        "COUNT" (count nums)
        "COUNTA" (count (remove #(or (nil? %) (= "" %)) flat))
        "MIN" (if (seq nums) (reduce min nums) 0)
        "MAX" (if (seq nums) (reduce max nums) 0)
        "ABS" (if-let [n (as-number (first flat))] (Math/abs (double n)) "#VALUE!")
        "ROUND" (let [n (as-number (first flat))
                      places (or (as-number (second flat)) 0)]
                  (if n
                    (let [f (Math/pow 10 places)]
                      ;; `Math/round` rather than `rint`: JS has no rint, and
                      ;; the half-up rounding a spreadsheet does is round's.
                      (/ (double (Math/round (* (double n) f))) f))
                    "#VALUE!"))

        ;; ── conditional aggregates ──
        ;;
        ;; The pair that makes a spreadsheet useful for anything real:
        ;; totalling the rows that match something. `SUMIF` takes an optional
        ;; third range to add up instead of the one it tested, which is how
        ;; Excel spells "test one column, total another".
        "COUNTIF" (let [[tested criterion] args]
                    (count (filter #(matches? % (first (flatten [criterion])))
                                   (flatten [tested]))))
        "SUMIF" (let [[tested criterion sum-range] args
                      c (first (flatten [criterion]))
                      xs (vec (flatten [tested]))
                      ys (vec (flatten [(if (nil? sum-range) tested sum-range)]))]
                  (reduce + 0
                          (keep-indexed
                           (fn [i v]
                             (when (matches? v c) (as-number (nth ys i nil))))
                           xs)))

        ;; ── text ──
        "LEN" (count (str (first flat)))
        "LEFT" (let [t (str (first flat))
                     n (long (or (as-number (second flat)) 1))]
                 (subs t 0 (max 0 (min n (count t)))))
        "RIGHT" (let [t (str (first flat))
                      n (long (or (as-number (second flat)) 1))]
                  (subs t (max 0 (- (count t) (max 0 n)))))
        "MID" (let [t (str (first flat))
                    start (long (or (as-number (nth flat 1 nil)) 1))
                    n (long (or (as-number (nth flat 2 nil)) 0))
                    from (min (max 0 (dec start)) (count t))]
                (subs t from (min (+ from (max 0 n)) (count t))))
        "UPPER" (str/upper (str (first flat)))
        "LOWER" (str/lower (str (first flat)))
        "TRIM" (str/trim (str (first flat)))
        "CONCATENATE" (apply str (map str flat))

        ;; ── logic ──
        ;;
        ;; Not short-circuiting, unlike `IF`. Excel's are not either — every
        ;; argument is evaluated and an error in any of them is the answer,
        ;; which the check at the top of this function already does.
        "AND" (every? truthy? flat)
        "OR" (boolean (some truthy? flat))
        "NOT" (not (truthy? (first flat)))

        ;; `IF` never reaches here — `eval-node` handles it before its
        ;; arguments are evaluated. Named so that one arriving anyway would
        ;; not read as an unknown function.
        "IF" "#NAME?"
        "#NAME?"))))

(defn- eval-node [node tab seen opts]
  (let [[kind a b] node]
    (case kind
      :num (or (as-number a) "#VALUE!")
      :str a
      :error a
      :neg (let [v (eval-node a tab seen opts)]
             (cond (error? v) v
                   (as-number v) (- (as-number v))
                   :else "#VALUE!"))
      :ref (let [[row col] (parse-ref a)
                 sheet (nth node 2 nil)
                 ;; A qualified reference reads another sheet; an
                 ;; unqualified one reads this one. `#REF!` for a sheet that
                 ;; is not there, which is what a spreadsheet says about an
                 ;; address it cannot resolve.
                 target (if sheet (get (:tabs opts) sheet) tab)
                 opts (cond-> opts sheet (assoc :sheet sheet))]
             (cond
               (and sheet (nil? target)) "#REF!"
               row (value-at target row col seen opts)
               ;; A word that is not a cell reference may be a named range —
               ;; `=SUM(売上)`. Resolved to the range it stands for and then
               ;; evaluated as one, so a name behaves exactly like the
               ;; addresses it replaces rather than like a second kind of
               ;; thing.
               (get (:names opts) (str a))
               (eval-node (let [{:keys [from to]} (get (:names opts) (str a))]
                            [:range from to])
                          tab seen opts)
               ;; Neither an address nor a name anybody defined. Excel's
               ;; answer for a word it does not know.
               :else "#NAME?"))
      :range (let [from (parse-ref a) to (parse-ref b)
                   sheet (nth node 3 nil)
                   target (if sheet (get (:tabs opts) sheet) tab)
                   opts (cond-> opts sheet (assoc :sheet sheet))]
               (cond
                 (and sheet (nil? target)) "#REF!"
                 (and from to)
                 (vec (for [row (range (min (first from) (first to))
                                       (inc (max (first from) (first to))))
                            col (range (min (second from) (second to))
                                       (inc (max (second from) (second to))))]
                        (value-at target row col seen opts)))
                 :else "#REF!"))
      ;; `IF` chooses before it computes. Everything else takes evaluated
      ;; arguments, and evaluating both branches of an IF defeats the thing
      ;; it is most used for: `IF(A1=0,"ゼロ",100/A1)` guards a division by
      ;; zero, and computing the guarded branch anyway makes the whole
      ;; formula #DIV/0! — the error the guard exists to avoid. Measured
      ;; before it was fixed.
      :call (if (= "IF" a)
              (let [test (eval-node (first b) tab seen opts)]
                (cond
                  (error? test) test
                  (truthy? test) (if (> (count b) 1) (eval-node (nth b 1) tab seen opts) "")
                  :else (if (> (count b) 2) (eval-node (nth b 2) tab seen opts) "")))
              (apply-fn a (mapv #(eval-node % tab seen opts) b)))
      :op (let [op a
                x (eval-node b tab seen opts)
                y (eval-node (nth node 3) tab seen opts)]
            (cond
              (error? x) x
              (error? y) y
              :else
              (cond
                  (contains? #{"=" "<>" "<" ">" "<=" ">="} op) (compare-op op x y)
                  (= "&" op) (str x y)
                  :else
                  (let [nx (as-number x) ny (as-number y)]
                    (if-not (and nx ny)
                      "#VALUE!"
                      (case op
                        "+" (+ nx ny) "-" (- nx ny) "*" (* nx ny)
                        "/" (if (zero? ny) "#DIV/0!" (/ (double nx) ny))
                        "^" (Math/pow nx ny)
                        "#VALUE!"))))))
      "#NAME?")))

(defn value-at
  "What the cell at `row`,`col` comes to.

  `seen` is the chain of cells being computed. A cell that appears in its own
  chain is `#CIRCULAR!` — reported rather than recursed into, because the
  alternative is a stack overflow, and a spreadsheet that crashes on a
  self-reference is worse than one that says so.

  The chain is keyed by **sheet and cell**, not by cell. With one tab those
  are the same thing; with two, `売上表!A1` and `原価表!A1` are both `[1 1]`,
  so a cell-only key calls an ordinary cross-tab reference a cycle — and
  would miss a real one that goes out to another sheet and back."
  ([tab row col] (value-at tab row col #{} {}))
  ([tab row col seen] (value-at tab row col seen {}))
  ([tab row col seen opts]
   (let [;; Two keys, not one. The cells map is addressed by cell; the chain
         ;; of what is being computed is addressed by sheet *and* cell,
         ;; because two tabs both have an A1.
         cell (get-in tab [:sheets/cells [row col]])
         link [(:sheet opts) row col]]
     (cond
       (contains? seen link) "#CIRCULAR!"
       (contains? cell :sheets/formula)
       (let [v (eval-node (parse (:sheets/formula cell)) tab (conj seen link) opts)]
         (cond (error? v) v
               (number? v) (format-number v)
               (boolean? v) (if v "TRUE" "FALSE")
               (nil? v) ""
               :else (str v)))
       :else (or (:sheets/value cell) "")))))

(defn names-of
  "A workbook's named ranges as `{name {:from \"A1\" :to \"B9\"}}`, for the tab
  `tab-id`.

  A name belongs to the workbook and a range belongs to a tab, so a name
  pointing at another tab is not resolvable from here — it is dropped rather
  than resolved against the wrong sheet, which would be an answer computed
  from the wrong numbers.

  The tab is matched by its **title**, falling back to its id when it has
  none — the same rule `sheets.xlsx` uses to write a `definedName`, because
  a `definedName` references a sheet by its name and that is what somebody
  defining a range writes. Matching the map key instead resolved a name in a
  workbook whose tabs happen to be keyed by their titles and in no other,
  which is every workbook this Drive creates."
  [workbook tab]
  (let [tab-name (or (:sheets/title tab) (:sheets/id tab))]
    (into {}
          (keep (fn [[name range]]
                  (when (= tab-name (:sheets/tab range))
                    (let [[from to] (str/split (str (:sheets/range range)) #":" 2)]
                      (when (and from to) [(str name) {:from from :to to}])))))
          (:sheets/named-ranges workbook))))

(defn values
  "Every cell of `tab` as what it comes to, keyed the same way the cells are.

  Computed on demand and never written back: a stored result is a second
  copy of something derived, stale the moment an input changes and
  indistinguishable afterwards from a value somebody typed."
  ([tab] (values tab {}))
  ([tab opts]
   (into {}
         (map (fn [[key _]] [key (value-at tab (first key) (second key) #{} opts)]))
         (:sheets/cells tab))))

(defn workbook-values
  "Every cell of every tab, with the workbook's named ranges resolvable.

  The arity to use from an application: `values` on a bare tab cannot see
  names, because names live on the workbook and a tab does not know which
  workbook it is in."
  [workbook]
  ;; Keyed by title, the same as a named range and the same as a
  ;; `definedName` — a formula writes `売上表!A1`, which is the sheet's name
  ;; and not the key it happens to be stored under.
  (let [by-name (into {}
                      (map (fn [[tab-id tab]]
                             [(or (:sheets/title tab) tab-id) tab]))
                      (:sheets/tabs workbook))]
    (into {}
          (map (fn [[tab-id tab]]
                 [tab-id (values tab {:names (names-of workbook tab)
                                      :tabs by-name
                                      :sheet (or (:sheets/title tab) tab-id)})]))
          (:sheets/tabs workbook))))
