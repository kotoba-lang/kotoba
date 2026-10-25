(ns kotoba.insurance.jp
  "Japan health-insurance identifiers -- pure format / check-digit validation.

  The 保険者番号 (hokensha-bangou, health-insurer number) printed on a
  Japanese health-insurance card (被保険者証) is an 8-digit number: a
  2-digit 法別番号 (insurance-category code), a 2-digit 都道府県番号
  (prefecture code), a 3-digit 保険者別番号 (insurer serial) and a 1-digit
  検証番号 (check digit) computed from the first seven digits.

  医療機関コード (medical-institution code) and 薬局コード (pharmacy code)
  -- together 医療機関等コード -- are a 10-digit number: a 2-digit
  都道府県番号, a 1-digit 点数表番号 (fee-schedule number, decoding to a
  医科/歯科/薬局 category), a 2-digit 郡市区番号 (district code), a 4-digit
  医療機関(薬局)番号 and a 1-digit 検証番号 computed from the first nine
  digits.

  Field widths and both check-digit algorithms are taken verbatim from the
  Ministry of Health, Labour and Welfare notification 別添２ 『保険者番号、
  公費負担者番号、公費負担医療の受給者番号並びに医療機関コード及び薬局コード
  設定要領』:

  - 第１ (保険者番号): weights of 2 and 1 alternate starting from the
    rightmost digit of the 7-digit body, a doubled digit >= 10 is folded to
    its own digit sum, and the check digit is 10 minus the last digit of
    that weighted sum (wrapping 10 -> 0). Verified against 第1-5's own
    worked example: body 0613048 -> weighted sum 22 -> check digit 8 ->
    full number 06130488. Independently re-confirmed 2026-07-08 against a
    second, later (2024-07-12) primary source
    (mhlw.go.jp/content/12400000/001275316.pdf), whose own 第１ worked
    example uses the identical numbers.
  - 第４ (医療機関コード及び薬局コード): the *same* alternating-2/1
    fold-mod10 algorithm, applied to the 9-digit body 都道府県番号(2) +
    点数表番号(1) + 郡市区番号(2) + 医療機関(薬局)番号(4). Verified against
    that same 2024-07-12 primary source's own 第４-５ worked example: 都道
    府県番号=34, 点数表番号=1, 郡市区番号=07, 医療機関番号=1236 -> weighted
    sum 28 -> check digit 2 (that source additionally shows the 郡市区+
    医療機関+検証 portion formatted as \"07,1236,2\", which is how it
    prints what it calls 医療機関等コード -- a 7-digit sub-field distinct
    from the 10-digit full identifier this namespace works with). See
    ADR-2607084100 and the archived source PDF at
    orgs/kotoba-lang/emr-claims-primary-sources/jp-mhlw/.

  This namespace only recognizes the *shape* of these numbers and
  *recomputes the same check digit an insurer's/local bureau's system
  would* -- it does not know which 保険者別番号 or 医療機関(薬局)番号 are
  actually issued, and does not touch diagnosis codes, fee schedules, or
  any real claims-adjustment logic. Like the rest of kotoba.insurance, this
  is a pure function; an operator's real insurer-master/institution-master
  lookup sits behind it.

  都道府県番号 (2-digit prefecture code) is embedded below as a 94-entry
  constant table: the 47 primary codes \"01\"-\"47\" (JIS X 0401, 1970) plus
  the 47 alternate codes \"51\"-\"97\" that 別添２ documents for use once a
  prefecture's primary-code range of 保険者別番号/医療機関(薬局)番号 is
  exhausted (\"当該コードで設定可能な...番号がなくなり次第、右に掲げるコード
  ...を設定する\"). Unlike the tens-of-thousands-of-rows 診療行為/薬剤/
  傷病名 masters that kotoba.insurance deliberately does *not* embed and
  instead ingests (see the iryo actor's master-honesty ADR-2606074000), a
  stable 94-entry public code table carries no meaningful maintenance/
  licensing burden.

  医療機関(薬局)番号 numeric ranges (医科 1,000-2,999 / 歯科 3,000-3,999 /
  薬局 4,000-4,999, with any number whose middle two or last two digits
  read \"90\" permanently unassigned) are taken from 第４-３ of the same
  notification.

  known gap, not implemented: a secondary source (Wikipedia,
  「処方箋発行医療機関コード」) describes a legacy exception for some
  医療機関コード issued before Japan's 1976 unification onto the current
  10-digit scheme (in 埼玉県/千葉県/東京都/神奈川県, descending from a 1967
  7-digit scheme), whose 検証番号 is said to be computed over the bare
  7-digit 医療機関コード body alone (郡市区番号+医療機関番号+検証番号),
  omitting 都道府県番号 and 点数表番号 from the check-digit input entirely.
  Neither primary source consulted for this namespace documents that
  exception, so it is **not implemented** here rather than guessed at --
  `iryokikan-bangou-check-digit` and `valid-iryokikan-bangou?` always use
  the full 9-digit body."
  (:require [kotoba.lang.text :as str]))

(defn- digit->int
  "Portable char / 1-char-string -> 0-9 int, or nil if c is not a decimal
  digit. Works the same on JVM Characters and ClojureScript's 1-char
  strings, since (str c) normalizes either to a 1-char string."
  [c]
  (str/index-of "0123456789" (str c)))

(defn- digits->int
  "Portable digit-string -> non-negative int, or nil if s contains any
  non-decimal-digit character. No platform Integer/parseInt or
  js/parseInt -- built from digit->int so it behaves identically on
  JVM/ClojureScript/SCI/GraalVM."
  [s]
  (reduce (fn [acc c]
            (let [d (digit->int c)]
              (if d (+ (* acc 10) d) (reduced nil))))
          0
          (seq (str s))))

(defn- pad2
  "Zero-pad a non-negative int < 100 to a 2-character string."
  [n]
  (if (< n 10) (str "0" n) (str n)))

(defn- fold-digits
  "Sum of the decimal digits of a non-negative int < 100. A doubled digit
  is at most 18 (9 * 2), so this is at most a two-term sum."
  [n]
  (if (< n 10) n (+ (quot n 10) (rem n 10))))

(defn- weighted-check-digit
  "Shared 検証番号 algorithm (別添２ 第１-５ / 第４-５, byte-identical
  wording in both): weight the digits 2/1 alternating from the *rightmost*
  digit (which gets weight 2), fold any doubled value >= 10 to its own
  digit sum, sum the folded values, and return 10 minus the last digit of
  that sum (wrapping 10 -> 0, per \"１の位の数が０のときは検証番号を０\").
  digits is a seq of 0-9 ints (any length -- both the 7-digit 保険者番号
  body and the 9-digit 医療機関コード body use this same shape of formula)."
  [digits]
  (let [n     (count digits)
        total (reduce +
                      (map-indexed
                        (fn [i d]
                          (let [weight (if (even? (- n 1 i)) 2 1)]
                            (fold-digits (* d weight))))
                        digits))]
    (mod (- 10 (mod total 10)) 10)))

(defn hokensha-bangou-check-digit
  "Compute the 検証番号 (check digit, an int 0-9) for a 7-digit body
  (法別番号 2 + 都道府県番号 2 + 保険者別番号 3, as a 7-character digit
  string or anything str-able to one). Returns nil when body is not
  exactly 7 decimal digits."
  [body]
  (when (re-matches #"\d{7}" (str body))
    (weighted-check-digit (mapv digit->int (seq (str body))))))

(defn parse-hokensha-bangou
  "Split an 8-digit 保険者番号 string into its components. Returns nil when
  s is not exactly 8 decimal digits. Does not check the check digit -- see
  valid-hokensha-bangou?."
  [s]
  (let [s (str s)]
    (when (re-matches #"\d{8}" s)
      {:hokensha/houbetsu-bangou       (subs s 0 2)
       :hokensha/todoufuken-bangou     (subs s 2 4)
       :hokensha/hokensha-betsu-bangou (subs s 4 7)
       :hokensha/kenshou-bangou        (subs s 7 8)})))

(defn valid-hokensha-bangou?
  "True when s is an 8-digit 保険者番号 whose 8th digit matches the check
  digit recomputed from its first 7 digits."
  [s]
  (boolean
    (when-let [{:hokensha/keys [houbetsu-bangou todoufuken-bangou
                                 hokensha-betsu-bangou kenshou-bangou]}
               (parse-hokensha-bangou s)]
      (= (str (hokensha-bangou-check-digit
                (str houbetsu-bangou todoufuken-bangou hokensha-betsu-bangou)))
         kenshou-bangou))))

(defn validate-hokensha-bangou
  "Return a validation result for a 保険者番号, in the same
  {:insurance/valid? ... :insurance/error ...} shape as
  kotoba.insurance/validate-policy and validate-claim."
  [s]
  (cond
    (not (re-matches #"\d{8}" (str s)))
    {:insurance/valid? false :insurance/error :not-8-digits}

    (not (valid-hokensha-bangou? s))
    {:insurance/valid? false :insurance/error :bad-check-digit}

    :else
    (merge {:insurance/valid? true} (parse-hokensha-bangou s))))

;; ---------------------------------------------------------------------
;; 都道府県番号 (prefecture code, "01"-"47" primary + "51"-"97" alternate)
;; ---------------------------------------------------------------------

(def ^:private todoufuken-names-primary
  "都道府県番号 (2-digit string, 01-47) -> 都道府県名. This is the JIS X
  0401 (制定 1970) prefecture-code assignment, which is public, stable and
  only 47 entries -- general knowledge, not a proprietary/copyrighted
  master. If any single entry is ever found to be wrong, fix that entry
  rather than distrust the whole table -- the code<->prefecture pairing has
  been stable for decades and is reused verbatim as the 都道府県番号 field
  inside both 保険者番号 and 医療機関コード."
  {"01" "北海道"   "02" "青森県"   "03" "岩手県"   "04" "宮城県"
   "05" "秋田県"   "06" "山形県"   "07" "福島県"   "08" "茨城県"
   "09" "栃木県"   "10" "群馬県"   "11" "埼玉県"   "12" "千葉県"
   "13" "東京都"   "14" "神奈川県" "15" "新潟県"   "16" "富山県"
   "17" "石川県"   "18" "福井県"   "19" "山梨県"   "20" "長野県"
   "21" "岐阜県"   "22" "静岡県"   "23" "愛知県"   "24" "三重県"
   "25" "滋賀県"   "26" "京都府"   "27" "大阪府"   "28" "兵庫県"
   "29" "奈良県"   "30" "和歌山県" "31" "鳥取県"   "32" "島根県"
   "33" "岡山県"   "34" "広島県"   "35" "山口県"   "36" "徳島県"
   "37" "香川県"   "38" "愛媛県"   "39" "高知県"   "40" "福岡県"
   "41" "佐賀県"   "42" "長崎県"   "43" "熊本県"   "44" "大分県"
   "45" "宮崎県"   "46" "鹿児島県" "47" "沖縄県"})

(def todoufuken-names
  "都道府県番号 -> 都道府県名, both the 47 primary codes (\"01\"-\"47\") and
  the 47 alternate codes (\"51\"-\"97\", each primary code + 50) that 別添２
  documents for use once a prefecture's primary-code range of 保険者別番号/
  医療機関(薬局)番号 is exhausted: \"都道府県ごと左に掲げるコード（例：北海道
  の場合01）から設定し、当該コードで設定可能な保険者別番号がなくなり次第、
  右に掲げるコード（例：北海道の場合51）を設定する\" (別添２, 保険者番号の
  項). Both ranges are equally valid, currently-issuable codes -- this is
  not a legacy/deprecated vs. current split."
  (into todoufuken-names-primary
        (map (fn [[k v]] [(pad2 (+ 50 (digits->int k))) v]))
        todoufuken-names-primary))

(defn valid-todoufuken-bangou?
  "True when s is one of the 94 two-digit 都道府県番号 (\"01\"-\"47\"
  primary or \"51\"-\"97\" alternate)."
  [s]
  (contains? todoufuken-names (str s)))

(defn todoufuken-name
  "都道府県名 for a 2-digit 都道府県番号 string, or nil when s is not one
  of the 94 valid codes."
  [s]
  (get todoufuken-names (str s)))

;; ---------------------------------------------------------------------
;; 点数表番号 (fee-schedule number -> 医科/歯科/薬局 category)
;; ---------------------------------------------------------------------

(def tensuhyou-bangou-categories
  "点数表番号 (1-digit string) -> category keyword, per 別添２ 第４-５(１):
  「点数表番号は医科１、歯科３、薬局４とするものとする」. Only these three
  digits are documented by the primary source this namespace was verified
  against (MHLW notification 001275316, 2024-07-12, 第４). Secondary
  sources (e.g. Wikipedia) additionally describe \"2\" (健診等機関 -- set
  separately by 支払基金) and \"6\" (訪問看護), but the primary source does
  not document either, so they are deliberately left unmapped here --
  out of this library's scope -- rather than guessed at."
  {"1" :medical    ; 医科
   "3" :dental     ; 歯科
   "4" :pharmacy}) ; 薬局

(defn tensuhyou-bangou-category
  "医科/歯科/薬局 category keyword for a 1-digit 点数表番号 string, or nil
  when it is not one of \"1\"/\"3\"/\"4\" (see tensuhyou-bangou-categories
  docstring for why \"2\"/\"6\" are not mapped)."
  [s]
  (get tensuhyou-bangou-categories (str s)))

(defn valid-tensuhyou-bangou?
  "True when s is one of the 3 documented 点数表番号 (\"1\"/\"3\"/\"4\")."
  [s]
  (contains? tensuhyou-bangou-categories (str s)))

;; ---------------------------------------------------------------------
;; 医療機関(薬局)番号 (4-digit institution/pharmacy serial) -- numeric range
;; ---------------------------------------------------------------------

(def iryokikan-kikan-bangou-ranges
  "点数表番号 category keyword -> [min max] (inclusive) for the 4-digit
  医療機関(薬局)番号, per 別添２ 第４-３: 「医療機関(薬局)番号は、医療機関に
  ついて、医科にあっては1,000から2,999、歯科にあっては3,000から3,999、薬局
  にあっては4,000から4,999の一連番号を...定めるものとする」."
  {:medical  [1000 2999]
   :dental   [3000 3999]
   :pharmacy [4000 4999]})

(defn valid-iryokikan-kikan-bangou-range?
  "True when a 4-digit 医療機関(薬局)番号 string falls inside the numeric
  range defined for its 点数表番号 category (see
  iryokikan-kikan-bangou-ranges). False when tensuhyou-bangou is not one of
  the 3 documented categories, or kikan-bangou is not a 4-digit numeral.
  Does not check the 欠番 (unassigned) 90-band exclusion -- see
  iryokikan-kikan-bangou-ketsuban?."
  [tensuhyou-bangou kikan-bangou]
  (boolean
    (when-let [[lo hi] (get iryokikan-kikan-bangou-ranges
                            (tensuhyou-bangou-category tensuhyou-bangou))]
      (when (re-matches #"\d{4}" (str kikan-bangou))
        (when-let [n (digits->int kikan-bangou)]
          (<= lo n hi))))))

(defn iryokikan-kikan-bangou-ketsuban?
  "True when a 4-digit 医療機関(薬局)番号 string is a known-unassigned
  (欠番) number: per 別添２ 第４-３ ただし書き, \"４桁の医療機関(薬局)番号の
  うち、中２桁又は下２桁が90となる番号は欠番とするものとする\" -- i.e. a
  number whose middle two digits (2nd+3rd) or last two digits (3rd+4th)
  read \"90\". Returns false (not an error) for input that is not a plain
  4-digit numeral -- shape is validated elsewhere; this predicate only
  encodes the 90-band exclusion."
  [s]
  (boolean
    (when (re-matches #"\d{4}" (str s))
      (let [s (str s)]
        (or (= "90" (subs s 1 3))
            (= "90" (subs s 2 4)))))))

;; ---------------------------------------------------------------------
;; 医療機関コード (medical-institution code, 10 digits)
;; ---------------------------------------------------------------------

(defn parse-iryokikan-bangou
  "Split a 10-digit 医療機関コード string into its components: 都道府県番号
  (2) + 点数表番号 (1) + 郡市区番号 (2) + 医療機関(薬局)番号 (4) + 検証番号
  (1). Returns nil when s is not exactly 10 decimal digits."
  [s]
  (let [s (str s)]
    (when (re-matches #"\d{10}" s)
      {:iryokikan/todoufuken-bangou (subs s 0 2)
       :iryokikan/tensuhyou-bangou  (subs s 2 3)
       :iryokikan/gunshiku-bangou   (subs s 3 5)
       :iryokikan/kikan-bangou      (subs s 5 9)
       :iryokikan/kenshou-bangou    (subs s 9 10)})))

(defn iryokikan-bangou-check-digit
  "Compute the 検証番号 (check digit, an int 0-9) for a 9-digit body
  (都道府県番号 2 + 点数表番号 1 + 郡市区番号 2 + 医療機関(薬局)番号 4, as a
  9-character digit string or anything str-able to one). Returns nil when
  body is not exactly 9 decimal digits. Verified against 別添２ 第４-５'s
  own worked example: body 341071236 -> weighted sum 28 -> check digit 2."
  [body]
  (when (re-matches #"\d{9}" (str body))
    (weighted-check-digit (mapv digit->int (seq (str body))))))

(defn valid-iryokikan-todoufuken-bangou?
  "True when s is a 10-digit 医療機関コード whose leading 都道府県番号 is
  one of the 94 valid codes (\"01\"-\"47\"/\"51\"-\"97\")."
  [s]
  (boolean
    (when-let [{:iryokikan/keys [todoufuken-bangou]} (parse-iryokikan-bangou s)]
      (valid-todoufuken-bangou? todoufuken-bangou))))

(defn valid-iryokikan-bangou?
  "True when s is a 10-digit 医療機関コード whose 10th digit matches the
  check digit recomputed from its first 9 digits. Does not check the
  都道府県番号 range, 点数表番号 category, or 医療機関番号 range -- see
  validate-iryokikan-bangou for the full check."
  [s]
  (boolean
    (when-let [{:iryokikan/keys [todoufuken-bangou tensuhyou-bangou
                                  gunshiku-bangou kikan-bangou
                                  kenshou-bangou]}
               (parse-iryokikan-bangou s)]
      (= (str (iryokikan-bangou-check-digit
                (str todoufuken-bangou tensuhyou-bangou gunshiku-bangou kikan-bangou)))
         kenshou-bangou))))

(defn validate-iryokikan-bangou-shape
  "Return a *shape-only* validation result for a 医療機関コード (10
  digits), checking only digit-count and 都道府県番号 range -- not the
  点数表番号 category, the 医療機関番号 numeric range, or the 検証番号 check
  digit. A true result means 'shape and prefecture code are plausible', not
  'this is a checksum-correct 医療機関コード' -- see
  validate-iryokikan-bangou for the full check."
  [s]
  (cond
    (not (re-matches #"\d{10}" (str s)))
    {:insurance/valid? false :insurance/error :not-10-digits}

    (not (valid-iryokikan-todoufuken-bangou? s))
    {:insurance/valid? false :insurance/error :bad-todoufuken-bangou}

    :else
    (merge {:insurance/valid? true} (parse-iryokikan-bangou s))))

(defn validate-iryokikan-bangou
  "Return a full validation result for a 医療機関コード, in the same
  {:insurance/valid? ... :insurance/error ...} shape as
  validate-hokensha-bangou. Checks, in order: digit-count (:not-10-digits),
  都道府県番号 range (:bad-todoufuken-bangou), 点数表番号 category
  (:bad-tensuhyou-bangou -- only \"1\"/\"3\"/\"4\" are recognized),
  医療機関(薬局)番号 numeric range for that category
  (:bad-kikan-bangou-range), and finally the 検証番号 check digit
  (:bad-check-digit). A true result merges in the parsed fields plus
  :iryokikan/category (the decoded 医科/歯科/薬局 keyword). Does not check
  the 欠番 (unassigned) 90-band exclusion -- call
  iryokikan-kikan-bangou-ketsuban? separately if that matters to a caller."
  [s]
  (if-not (re-matches #"\d{10}" (str s))
    {:insurance/valid? false :insurance/error :not-10-digits}
    (let [{:iryokikan/keys [todoufuken-bangou tensuhyou-bangou kikan-bangou]
           :as parsed}
          (parse-iryokikan-bangou s)]
      (cond
        (not (valid-todoufuken-bangou? todoufuken-bangou))
        {:insurance/valid? false :insurance/error :bad-todoufuken-bangou}

        (not (valid-tensuhyou-bangou? tensuhyou-bangou))
        {:insurance/valid? false :insurance/error :bad-tensuhyou-bangou}

        (not (valid-iryokikan-kikan-bangou-range? tensuhyou-bangou kikan-bangou))
        {:insurance/valid? false :insurance/error :bad-kikan-bangou-range}

        (not (valid-iryokikan-bangou? s))
        {:insurance/valid? false :insurance/error :bad-check-digit}

        :else
        (merge {:insurance/valid? true
                :iryokikan/category (tensuhyou-bangou-category tensuhyou-bangou)}
               parsed)))))
