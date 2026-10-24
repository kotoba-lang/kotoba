(ns kotoba.reji.currency
  "Denomination tables for a small set of currencies (coins + notes), keyed by
   ISO 4217 code. All amounts are plain integers in the currency's smallest
   circulating unit (\"minor units\" — e.g. yen, paisa, fen, centavo, halala,
   fils) — no floats anywhere, so nothing here is subject to binary-decimal
   rounding error. `:reji.currency/subdivision` is how many minor units make
   one major unit (1 for JPY, which has no subdivision in circulation; 100
   for the rest here). Adding a currency with a different subdivision (e.g.
   1000 for a 3-decimal currency such as KWD/BHD/OMR) needs no code change —
   only a new table entry."
  (:require [kotoba.lang.text :as str]))

(defn- denom
  "One denomination: `value` is an integer count of minor units, `kind` is
   :coin or :note, `label` is the human-facing string (e.g. \"¥500\")."
  [value kind label]
  {:reji.denom/value value :reji.denom/kind kind :reji.denom/label label})

(def currencies
  "code -> {:reji.currency/code :reji.currency/name :reji.currency/symbol
            :reji.currency/subdivision :reji.currency/decimal-places
            :reji.currency/denominations [denom ...]}  (denominations sorted
   descending by value)."
  {"JPY"
   {:reji.currency/code "JPY" :reji.currency/name "Japanese Yen"
    :reji.currency/symbol "¥" :reji.currency/subdivision 1 :reji.currency/decimal-places 0
    :reji.currency/denominations
    [(denom 10000 :note "¥10000") (denom 5000 :note "¥5000")
     (denom 2000 :note "¥2000") (denom 1000 :note "¥1000")
     (denom 500 :coin "¥500") (denom 100 :coin "¥100")
     (denom 50 :coin "¥50") (denom 10 :coin "¥10")
     (denom 5 :coin "¥5") (denom 1 :coin "¥1")]}

   "INR"
   {:reji.currency/code "INR" :reji.currency/name "Indian Rupee"
    :reji.currency/symbol "₹" :reji.currency/subdivision 100 :reji.currency/decimal-places 2
    :reji.currency/denominations
    [(denom 50000 :note "₹500") (denom 20000 :note "₹200")
     (denom 10000 :note "₹100") (denom 5000 :note "₹50")
     (denom 2000 :note "₹20") (denom 2000 :coin "₹20")
     (denom 1000 :note "₹10") (denom 1000 :coin "₹10")
     (denom 500 :coin "₹5") (denom 200 :coin "₹2")
     (denom 100 :coin "₹1")]}

   "CNY"
   {:reji.currency/code "CNY" :reji.currency/name "Chinese Yuan (Renminbi)"
    :reji.currency/symbol "¥" :reji.currency/subdivision 100 :reji.currency/decimal-places 2
    :reji.currency/denominations
    [(denom 10000 :note "¥100") (denom 5000 :note "¥50")
     (denom 2000 :note "¥20") (denom 1000 :note "¥10")
     (denom 500 :note "¥5") (denom 100 :note "¥1")
     (denom 100 :coin "¥1") (denom 50 :coin "¥0.5")
     (denom 10 :coin "¥0.1")]}

   "BRL"
   {:reji.currency/code "BRL" :reji.currency/name "Brazilian Real"
    :reji.currency/symbol "R$" :reji.currency/subdivision 100 :reji.currency/decimal-places 2
    :reji.currency/denominations
    [(denom 20000 :note "R$200") (denom 10000 :note "R$100")
     (denom 5000 :note "R$50") (denom 2000 :note "R$20")
     (denom 1000 :note "R$10") (denom 500 :note "R$5")
     (denom 200 :note "R$2") (denom 100 :coin "R$1")
     (denom 50 :coin "R$0.50") (denom 25 :coin "R$0.25")
     (denom 10 :coin "R$0.10") (denom 5 :coin "R$0.05")]}

   "MXN"
   {:reji.currency/code "MXN" :reji.currency/name "Mexican Peso"
    :reji.currency/symbol "$" :reji.currency/subdivision 100 :reji.currency/decimal-places 2
    :reji.currency/denominations
    [(denom 100000 :note "$1000") (denom 50000 :note "$500")
     (denom 20000 :note "$200") (denom 10000 :note "$100")
     (denom 5000 :note "$50") (denom 2000 :note "$20")
     (denom 2000 :coin "$20") (denom 1000 :coin "$10")
     (denom 500 :coin "$5") (denom 200 :coin "$2")
     (denom 100 :coin "$1") (denom 50 :coin "$0.50")
     (denom 20 :coin "$0.20") (denom 10 :coin "$0.10")
     (denom 5 :coin "$0.05")]}

   "SAR"
   {:reji.currency/code "SAR" :reji.currency/name "Saudi Riyal"
    :reji.currency/symbol "SR" :reji.currency/subdivision 100 :reji.currency/decimal-places 2
    :reji.currency/denominations
    [(denom 50000 :note "SR500") (denom 20000 :note "SR200")
     (denom 10000 :note "SR100") (denom 5000 :note "SR50")
     (denom 1000 :note "SR10") (denom 500 :note "SR5")
     (denom 100 :coin "SR1") (denom 50 :coin "50 halalas")
     (denom 25 :coin "25 halalas") (denom 10 :coin "10 halalas")
     (denom 5 :coin "5 halalas")]}

   "AED"
   {:reji.currency/code "AED" :reji.currency/name "UAE Dirham"
    :reji.currency/symbol "AED" :reji.currency/subdivision 100 :reji.currency/decimal-places 2
    :reji.currency/denominations
    [(denom 100000 :note "AED1000") (denom 50000 :note "AED500")
     (denom 20000 :note "AED200") (denom 10000 :note "AED100")
     (denom 5000 :note "AED50") (denom 2000 :note "AED20")
     (denom 1000 :note "AED10") (denom 500 :note "AED5")
     (denom 100 :coin "AED1") (denom 50 :coin "50 fils")
     (denom 25 :coin "25 fils")]}})

(defn codes
  "All supported ISO 4217 currency codes, sorted."
  []
  (sort (keys currencies)))

(defn currency
  "The currency record for `code`, or throws if unknown."
  [code]
  (or (get currencies code)
      (throw (ex-info (str "unknown currency: " code)
                       {:reji/error :unknown-currency :code code}))))

(defn denominations
  "This currency's denominations, sorted descending by value."
  [code]
  (->> (:reji.currency/denominations (currency code))
       (sort-by :reji.denom/value >)
       vec))

(defn- parse-int [s]
  #?(:clj (Long/parseLong s)
     :cljs (js/parseInt s 10)))

(defn- pad-right
  "Pad/truncate `s` to exactly `len` chars by appending zeros on the right —
   used for parsing a decimal fraction (\"5\" at 2 places means \"50\", i.e.
   50/100, not 5/100)."
  [s len]
  (let [n (count s)]
    (if (>= n len) (subs s 0 len) (str s (apply str (repeat (- len n) \0))))))

(defn- pad-left
  "Pad `s` to at least `len` chars with leading zeros — used for formatting a
   remainder back into a fixed-width decimal fraction (5/100 must print as
   \"05\", not \"50\")."
  [s len]
  (let [n (count s)]
    (if (>= n len) s (str (apply str (repeat (- len n) \0)) s))))

(defn parse-amount
  "Parse a decimal string like \"1234\" or \"12.50\" into an integer count of
   minor units for `code`, without going through any floating-point value.
   Throws if the string has a fractional part but the currency has no
   subdivision (e.g. \"10.5\" for JPY)."
  [code s]
  (let [{:reji.currency/keys [subdivision decimal-places]} (currency code)
        s (str/replace (str/trim s) "," "")
        neg? (str/starts-with? s "-")
        s (if neg? (subs s 1) s)
        [major-s minor-s] (str/split s #"\." 2)
        major (parse-int (if (str/blank? major-s) "0" major-s))]
    (when (and minor-s (zero? decimal-places) (not (re-matches #"0*" minor-s)))
      (throw (ex-info (str code " has no subdivision, got fractional amount: " s)
                       {:reji/error :no-subdivision :code code :amount s})))
    (let [minor (if (and minor-s (pos? decimal-places))
                  (parse-int (pad-right minor-s decimal-places))
                  0)
          total (+ (* major subdivision) minor)]
      (if neg? (- total) total))))

(defn- group-thousands [digits]
  (let [rev (str/reverse digits)
        groups (map str/reverse (re-seq #".{1,3}" rev))]
    (str/join "," (reverse groups))))

(defn format-amount
  "Render an integer count of minor units back into a display string for
   `code`, e.g. (format-amount \"JPY\" 1234) => \"¥1,234\",
   (format-amount \"INR\" 123450) => \"₹1,234.50\"."
  [code minor]
  (let [{sym :reji.currency/symbol :reji.currency/keys [subdivision decimal-places]} (currency code)
        neg? (neg? minor)
        m (if neg? (- minor) minor)
        major (quot m subdivision)
        rem (mod m subdivision)]
    (str (when neg? "-") sym (group-thousands (str major))
         (when (pos? decimal-places)
           (str "." (pad-left (str rem) decimal-places))))))
