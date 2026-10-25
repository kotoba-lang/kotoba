(ns kakeibo.amount
  "Exact money parsing for statement rows.

  Statement rows arrive as text (`\"1,234\"`, `\"¥1,234\"`, `\"１，２３４円\"`,
  `\"(1,234)\"`, `\"-1,234\"`). This namespace turns that text into a signed
  integer in the currency's *minor unit* — the same convention
  `kotoba-lang/banking` and `kotoba-lang/card` use, so no BigDecimal and no
  float ever touches a money value.

  Two properties are deliberate:

  - **No floating point, no host interop.** Digits are folded into an integer
    with `(+ (* 10 acc) d)`, so the same code is exact on the JVM, in
    ClojureScript, and under a Kotoba/Wasm host. There is no `parseInt`, no
    `Long/parseLong`, no reader conditional.
  - **Fail closed.** Anything not understood returns a problem map rather
    than `nil` or `0`. A statement line silently read as zero is worse than a
    rejected batch: it understates spending and nothing surfaces the loss."
  (:require [kotoba.lang.text :as str]))

;; ---------------------------------------------------------------------------
;; Width / sign normalization
;; ---------------------------------------------------------------------------

(def ^:private fullwidth-zero 0xFF10)     ; ０
(def ^:private fullwidth-nine 0xFF19)     ; ９
(def ^:private fullwidth-upper-a 0xFF21)  ; Ａ
(def ^:private fullwidth-upper-z 0xFF3A)  ; Ｚ
(def ^:private fullwidth-lower-a 0xFF41)  ; ａ
(def ^:private fullwidth-lower-z 0xFF5A)  ; ｚ
(def ^:private ascii-zero 0x30)
(def ^:private ascii-upper-a 0x41)
(def ^:private ascii-lower-a 0x61)

(defn- code-point [c] #?(:clj (int c) :cljs (.charCodeAt (str c) 0)))
(defn- from-code [n] #?(:clj (char n) :cljs (js/String.fromCharCode n)))

;; Deliberately absent: ー (U+30FC, katakana-hiragana prolonged sound mark).
;; It looks like a dash and is not one — folding it to "-" corrupts ordinary
;; payee names (コーヒー -> コ-ヒ-). Only the three characters that really are
;; hyphens/minuses are folded.
(def ^:private punctuation-map
  {"，" "," "．" "." "－" "-" "−" "-" "‐" "-" "　" " "})

(defn normalize-width
  "Fold full-width digits, Latin letters and punctuation to ASCII.

  Japanese bank exports mix both widths in the same column — amounts as
  `１，２３４` and payee names as `ＡＭＡＺＯＮ．ＣＯ．ＪＰ` — so this runs
  before any parsing or matching rather than being an option a caller can
  forget. Kana and kanji are left exactly as they are."
  [s]
  (when (some? s)
    (->> (str s)
         (map (fn [c]
                (let [cp (code-point c)]
                  (cond
                    (and (>= cp fullwidth-zero) (<= cp fullwidth-nine))
                    (from-code (+ ascii-zero (- cp fullwidth-zero)))

                    (and (>= cp fullwidth-upper-a) (<= cp fullwidth-upper-z))
                    (from-code (+ ascii-upper-a (- cp fullwidth-upper-a)))

                    (and (>= cp fullwidth-lower-a) (<= cp fullwidth-lower-z))
                    (from-code (+ ascii-lower-a (- cp fullwidth-lower-a)))

                    :else (get punctuation-map (str c) (str c))))))
         (apply str))))

;; ---------------------------------------------------------------------------
;; Scale
;; ---------------------------------------------------------------------------

(def ^:private scale->fraction-digits
  {1 0, 10 1, 100 2, 1000 3, 10000 4})

(defn fraction-digits
  "Number of fractional digits a minor-unit scale allows, or nil when the
  scale is not a supported power of ten. JPY is scale 1 (no subunit); USD and
  EUR are scale 100; KWD and BHD are scale 1000."
  [scale]
  (get scale->fraction-digits scale))

;; ---------------------------------------------------------------------------
;; Parsing
;; ---------------------------------------------------------------------------

(def ^:private max-digits 15)

(defn- abs* [n] (if (neg? n) (- n) n))
(defn- pow10 [n] (reduce (fn [acc _] (* 10 acc)) 1 (range n)))

(defn- digit-value [c]
  (let [cp (code-point c)]
    (when (and (>= cp ascii-zero) (<= cp (+ ascii-zero 9)))
      (- cp ascii-zero))))

(defn- fold-digits
  "Fold a digit-only string into an integer without interop or floats."
  [s]
  (reduce (fn [acc c] (+ (* 10 acc) (digit-value c))) 0 s))

(defn- negative-marker? [s]
  (or (str/starts-with? s "-")
      (and (str/starts-with? s "(") (str/ends-with? s ")"))))

(defn parse
  "Parse statement text into `{:amount/minor <signed int>}` or
  `{:amount/problem <keyword> :amount/input <original>}`.

  `scale` is minor units per major unit (1 for JPY, 100 for USD).

  Accounting parentheses mean negative, as does a leading `-`. A trailing
  `-` (some Japanese CSV exports) also means negative. Currency symbols,
  unit words (`円`, `JPY`), separators and spaces are discarded."
  [text scale]
  (let [fd (fraction-digits scale)]
    (cond
      (nil? fd)
      {:amount/problem :unsupported-scale :amount/input text :amount/scale scale}

      (or (nil? text) (and (string? text) (str/blank? text)))
      {:amount/problem :blank :amount/input text}

      :else
      (let [raw  (str/trim (normalize-width text))
            neg? (or (negative-marker? raw) (str/ends-with? raw "-"))
            ;; Keep only digits and the decimal point; everything else
            ;; (¥ $ , 円 JPY spaces parens signs) is presentation.
            kept (apply str (filter #(or (some? (digit-value %)) (= \. %)) raw))
            parts (str/split kept #"\." -1)]
        (cond
          (str/blank? (str/replace kept "." ""))
          {:amount/problem :no-digits :amount/input text}

          (> (count parts) 2)
          {:amount/problem :multiple-decimal-points :amount/input text}

          :else
          (let [int-part  (or (first parts) "")
                frac-part (or (second parts) "")]
            (cond
              (> (count frac-part) fd)
              {:amount/problem :fraction-exceeds-scale
               :amount/input text :amount/scale scale}

              (> (+ (count int-part) fd) max-digits)
              {:amount/problem :too-many-digits :amount/input text}

              :else
              (let [padded (str frac-part (apply str (repeat (- fd (count frac-part)) "0")))
                    magnitude (fold-digits (str int-part padded))]
                {:amount/minor (if neg? (- magnitude) magnitude)}))))))))

(defn parse-signed
  "Parse an in/out column pair into one signed minor-unit amount.

  Japanese statements split money into 入金金額 (in) and 出金金額 (out)
  columns, exactly one of which is populated per row. Outflow is negative so
  a period sum is a net change, and a row with both or neither populated is a
  problem rather than a guess."
  [{:keys [in out]} scale]
  (let [blank? (fn [v] (or (nil? v) (and (string? v) (str/blank? v))))
        in?    (not (blank? in))
        out?   (not (blank? out))]
    (cond
      (and in? out?)   {:amount/problem :both-in-and-out :amount/input {:in in :out out}}
      (and (not in?) (not out?)) {:amount/problem :blank :amount/input {:in in :out out}}
      in?  (parse in scale)
      :else (let [r (parse out scale)]
              (if (:amount/problem r)
                r
                ;; An out column may already carry its own minus sign; take the
                ;; magnitude first so "1,234" and "-1,234" in 出金金額 agree.
                {:amount/minor (- (abs* (:amount/minor r)))})))))

(defn format-minor
  "Render a minor-unit integer back to major units, for display only.

  Kept next to the parser so the round-trip is testable; nothing in the
  ledger path formats money."
  [minor scale]
  (let [fd (fraction-digits scale)]
    (when (and (some? minor) (some? fd))
      (let [neg? (neg? minor)
            mag  (abs* minor)]
        (if (zero? fd)
          (str (when neg? "-") mag)
          (let [divisor (pow10 fd)
                whole (quot mag divisor)
                frac  (rem mag divisor)
                frac-str (str frac)
                padded (str (apply str (repeat (- fd (count frac-str)) "0")) frac-str)]
            (str (when neg? "-") whole "." padded)))))))
