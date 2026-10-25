(ns sgp4.tle
  "The two-line element set, parsed by column.

  A TLE is a fixed-column punched-card format, not a delimited one. Two of
  its fields carry an *assumed* decimal point and a two-character exponent
  (`28098-4` means 0.28098e-4), and a whitespace-splitting parser gets those
  wrong in a way that still produces a number -- which is the failure mode
  worth designing against, because a wrong BSTAR does not crash a
  propagator, it just moves the satellite.

  So every field is taken by its documented column range, and the parse
  refuses rather than guesses.

  Refusals are values: `parse` returns
  `{:ok? false :error <keyword> :detail <string>}`, never an exception.
  A caller ingesting ten thousand TLEs must be able to drop the four bad
  ones and record why, without a try/catch per line."
  (:require [kotoba.lang.text :as str]
            [sgp4.time :as t]))

(def two-pi (* 2.0 Math/PI))
(def deg->rad (/ Math/PI 180.0))

(defn- err
  ([k] {:ok? false :error k})
  ([k detail] {:ok? false :error k :detail detail}))

(defn- field
  "Columns `a`..`b` of `s`, 1-indexed and inclusive, trimmed.

  Returns nil if the line is too short -- callers turn that into a refusal
  rather than silently reading a shorter field."
  [s a b]
  (when (>= (count s) b)
    (str/trim (subs s (dec a) b))))

(defn- parse-double*
  "Strict double. Returns nil for anything that is not entirely a number,
  including the empty string and `NaN` spellings.

  `#?(:clj Double/parseDouble)` accepts `\"1d\"`, `\"0x1p3\"` and
  `\"NaN\"`; `js/parseFloat` accepts `\"1.2abc\"`. Neither is what a
  fixed-column field means, so the shape is checked first."
  [s]
  (when (and s (re-matches #"[+-]?(\d+\.?\d*|\.\d+)([eE][+-]?\d+)?" s))
    #?(:clj (try (Double/parseDouble s) (catch Exception _ nil))
       :cljs (let [v (js/Number s)] (when-not (js/isNaN v) v)))))

(defn assumed-decimal
  "Parse a TLE exponent field such as `28098-4`, ` 00000-0`, `-11606-4`.

  The leading digits carry an assumed `0.` and the trailing signed digit is
  a power of ten. An empty or all-blank field is 0.0 -- that is what the
  format means, and it is the common case for `nddot`."
  [s]
  (let [s (some-> s str/trim)]
    (cond
      (or (nil? s) (= "" s)) 0.0
      :else
      (let [[_ sign mant esign eexp]
            (re-matches #"([+-]?)(\d+)([+-])(\d+)" s)]
        (cond
          mant (let [m (parse-double* (str "0." mant))
                     e (parse-double* eexp)]
                 (when (and m e)
                   (* (if (= "-" sign) -1.0 1.0)
                      m
                      (Math/pow 10.0 (* (if (= "-" esign) -1.0 1.0) e)))))
          ;; Some producers emit a plain decimal here instead of the
          ;; assumed-point form. Accept it, but only if it really is one.
          :else (parse-double* s))))))

(defn checksum
  "TLE modulo-10 checksum over the first 68 columns: digits add their value,
  `-` adds 1, everything else adds 0."
  [line]
  (mod (reduce (fn [acc ch]
                 (cond
                   #?(:clj (Character/isDigit ^char ch)
                      :cljs (and (>= (.charCodeAt ch 0) 48) (<= (.charCodeAt ch 0) 57)))
                   (+ acc #?(:clj (Character/digit ^char ch 10)
                             :cljs (- (.charCodeAt ch 0) 48)))
                   (= \- ch) (inc acc)
                   :else acc))
               0
               (take 68 line))
       10))

(defn- check-line
  [line n]
  (cond
    (nil? line) (err :tle/missing-line (str "line " n " is absent"))
    (< (count line) 69) (err :tle/short-line
                             (str "line " n " is " (count line) " chars, need 69"))
    (not= (str n) (subs line 0 1)) (err :tle/wrong-line-number
                                        (str "line " n " starts with " (subs line 0 1)))
    :else nil))

(defn parse
  "Parse a TLE into mean elements in the units SGP4 wants.

  `opts`:
  - `:name`         optional line-0 name to carry through
  - `:verify-checksum?` (default true) -- refuse a line whose modulo-10
    checksum does not match column 69. Some feeds strip or mangle it; set
    false deliberately and know that a transposed digit will then be
    accepted silently.

  On success returns `{:ok? true :tle {...}}` with angles in **radians**
  and mean motion in **radians/minute**, which is what `sgp4.core` takes.
  The raw revolutions-per-day value is kept as `:no-kozai-rev-day` because
  it is the one humans read."
  ([line1 line2] (parse line1 line2 {}))
  ([line1 line2 opts]
   (let [verify? (get opts :verify-checksum? true)
         line1 (some-> line1 (str/replace #"[\r\n]+$" ""))
         line2 (some-> line2 (str/replace #"[\r\n]+$" ""))]
     (or (check-line line1 1)
         (check-line line2 2)
         (when verify?
           (let [c1 (parse-double* (field line1 69 69))
                 c2 (parse-double* (field line2 69 69))]
             (cond
               (or (nil? c1) (nil? c2))
               (err :tle/checksum-not-a-digit)
               (not= (long c1) (checksum line1))
               (err :tle/checksum-mismatch
                    (str "line 1: column 69 says " (long c1)
                         ", computed " (checksum line1)))
               (not= (long c2) (checksum line2))
               (err :tle/checksum-mismatch
                    (str "line 2: column 69 says " (long c2)
                         ", computed " (checksum line2))))))
         (let [satnum1 (field line1 3 7)
               satnum2 (field line2 3 7)
               epoch-yy (parse-double* (field line1 19 20))
               epoch-day (parse-double* (field line1 21 32))
               ndot (parse-double* (str/replace (or (field line1 34 43) "") #"^\+" ""))
               nddot (assumed-decimal (field line1 45 52))
               bstar (assumed-decimal (field line1 54 61))
               inclo (parse-double* (field line2 9 16))
               nodeo (parse-double* (field line2 18 25))
               ecco-raw (field line2 27 33)
               ecco (parse-double* (str "0." ecco-raw))
               argpo (parse-double* (field line2 35 42))
               mo (parse-double* (field line2 44 51))
               no (parse-double* (field line2 53 63))
               missing (->> {:satnum satnum1 :epoch-year epoch-yy :epoch-day epoch-day
                             :ndot ndot :nddot nddot :bstar bstar
                             :inclo inclo :nodeo nodeo :ecco ecco
                             :argpo argpo :mo mo :no no}
                            (keep (fn [[k v]] (when (nil? v) k)))
                            sort vec)]
           (cond
             (seq missing)
             (err :tle/unparsable-field (str "fields did not parse: " (str/join ", " missing)))

             (not= satnum1 satnum2)
             (err :tle/satnum-mismatch (str "line 1 says " satnum1 ", line 2 says " satnum2))

             (not (< 0.0 no))
             (err :tle/non-positive-mean-motion (str "mean motion " no " rev/day"))

             ;; Eccentricity is read as `0.<digits>` so it cannot be >= 1 by
             ;; construction; a negative is only reachable through a mangled
             ;; field. Checked anyway, because SGP4's own error 1 is
             ;; "eccentricity out of range" and it is better to name it here.
             (not (<= 0.0 ecco 0.9999999))
             (err :tle/eccentricity-out-of-range (str "e = " ecco))

             :else
             (let [[jd frac] (t/tle-epoch->jd (long epoch-yy) epoch-day)]
               {:ok? true
                :tle {:satnum satnum1
                      :name (:name opts)
                      :classification (field line1 8 8)
                      :intl-designator (field line1 10 17)
                      :element-set-number (some-> (field line1 65 68) parse-double* long)
                      :rev-at-epoch (some-> (field line2 64 68) parse-double* long)
                      :epoch-year (long epoch-yy)
                      :epoch-day epoch-day
                      :jdsatepoch jd
                      :jdsatepoch-frac frac
                      ;; SGP4 units
                      :no-kozai (* no (/ two-pi 1440.0))   ; rad/min
                      :no-kozai-rev-day no
                      :ecco ecco
                      :inclo (* inclo deg->rad)
                      :nodeo (* nodeo deg->rad)
                      :argpo (* argpo deg->rad)
                      :mo (* mo deg->rad)
                      :bstar bstar
                      ;; carried for provenance; SGP4 itself does not use them
                      :ndot (* ndot (/ two-pi 1440.0 1440.0))
                      :nddot (* nddot (/ two-pi 1440.0 1440.0 1440.0))
                      :line1 line1
                      :line2 line2}})))))))

(defn parse-catalog
  "Parse a whole CelesTrak-style catalog: repeating 3-line (name, 1, 2) or
  2-line groups, in one pass.

  Returns `{:ok [tle ...] :failed [{:error ... :detail ... :line1 ...}]}`.
  **Both keys are always present.** A catalog with one bad line must not
  look like a catalog with none, and a caller that only reads `:ok` should
  have to ignore `:failed` explicitly rather than by omission."
  ([text] (parse-catalog text {}))
  ([text opts]
   (let [lines (->> (str/split-lines (or text ""))
                    (map #(str/replace % #"\r$" ""))
                    (remove #(str/blank? %))
                    vec)]
     (loop [i 0 ok (transient []) bad (transient [])]
       (if (>= i (count lines))
         {:ok (persistent! ok) :failed (persistent! bad)}
         (let [l (nth lines i)]
           (cond
             ;; a name line: the next two must be 1 and 2
             (not (str/starts-with? l "1 "))
             (if (and (< (+ i 2) (count lines))
                      (str/starts-with? (nth lines (inc i)) "1 ")
                      (str/starts-with? (nth lines (+ i 2)) "2 "))
               (let [r (parse (nth lines (inc i)) (nth lines (+ i 2))
                              (assoc opts :name (str/trim l)))]
                 (if (:ok? r)
                   (recur (+ i 3) (conj! ok (:tle r)) bad)
                   (recur (+ i 3) ok (conj! bad (assoc r :name (str/trim l)
                                                       :line1 (nth lines (inc i)))))))
               (recur (inc i) ok (conj! bad {:ok? false
                                             :error :tle/orphan-line
                                             :detail "line is neither a TLE line 1 nor followed by one"
                                             :line1 l})))

             (and (< (inc i) (count lines))
                  (str/starts-with? (nth lines (inc i)) "2 "))
             (let [r (parse l (nth lines (inc i)) opts)]
               (if (:ok? r)
                 (recur (+ i 2) (conj! ok (:tle r)) bad)
                 (recur (+ i 2) ok (conj! bad (assoc r :line1 l)))))

             :else
             (recur (inc i) ok (conj! bad {:ok? false
                                           :error :tle/unpaired-line-1
                                           :detail "line 1 is not followed by a line 2"
                                           :line1 l})))))))))
