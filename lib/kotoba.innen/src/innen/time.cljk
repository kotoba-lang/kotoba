(ns innen.time
  "Historical time for a dependency record that spans human history.

   Dates here are ISO-8601 strings that MAY be partial and MAY be BCE:
   `\"1600\"`, `\"1600-12\"`, `\"1600-12-31\"`, `\"-0221\"` (221 BCE, ISO-8601
   extended year form). Partial precision is a first-class fact, not a defect
   to be papered over -- \"the Dutch East India Company was chartered in 1602\"
   is a real, sourced statement, and inventing `1602-01-01` to make comparison
   easy would fabricate a day that no source states.

   Every date therefore carries a PRECISION and resolves to a closed
   [lower, upper] key interval rather than a single point:

     \"1602\"       -> [16020101 16021231]  precision :year
     \"1602-03\"    -> [16020301 16020331]  precision :month
     \"1602-03-20\" -> [16020320 16020320]  precision :day

   Comparison functions take the conservative side of that interval so that a
   coarse date is never silently treated as a specific day. `contains?` on a
   year-precision interval means \"somewhere in that year\", and callers that
   need day-level certainty can ask (`certain?`).

   The key encoding is `year * 10000 + month * 100 + day`, which is monotone
   for negative years too (-221 -> -2210000, and -0221-03 -> -2209699 > the
   year's own lower bound), so ordering works across the BCE/CE boundary
   without a separate branch. It is NOT a day count -- differences between
   keys are not durations, and this namespace deliberately offers no
   `duration` function rather than an almost-right one. Proleptic-Gregorian
   vs Julian calendar drift for pre-1582 dates is likewise NOT modelled: a
   pre-1582 date is stored exactly as its source states it, and
   `:innen.time/calendar` records which calendar the source used when the
   source says so."
  (:require [kotoba.lang.text :as str]))

(def precisions
  "Precision of a stated date, coarsest first."
  [:year :month :day])

(defn- parse-int*
  [s]
  #?(:clj (try (Long/parseLong s) (catch Exception _ nil))
     :cljs (let [n (js/parseInt s 10)] (when-not (js/isNaN n) n))))

(defn parse
  "Parse an ISO-8601 (possibly partial, possibly BCE) date string into
   `{:innen.time/year :innen.time/month :innen.time/day :innen.time/precision}`.
   Returns nil for anything unparseable -- callers must treat nil as \"no
   usable date\", never as \"now\" or \"year 0\"."
  [s]
  (when (and (string? s) (seq (str/trim s)))
    (let [s (str/trim s)
          bce? (str/starts-with? s "-")
          body (if bce? (subs s 1) s)
          parts (str/split body #"-")
          [y m d] (map parse-int* parts)]
      (when (and y (or (nil? m) (<= 1 m 12)) (or (nil? d) (<= 1 d 31)))
        (let [y (if bce? (- y) y)]
          (cond-> {:innen.time/year y
                   :innen.time/precision (cond d :day m :month :else :year)}
            m (assoc :innen.time/month m)
            d (assoc :innen.time/day d)))))))

(defn- key* [y m d] (+ (* y 10000) (* m 100) d))

(defn lower-key
  "The earliest instant a stated date can mean, as a comparable key."
  [s]
  (when-let [{:innen.time/keys [year month day]} (parse s)]
    (key* year (or month 1) (or day 1))))

(defn upper-key
  "The latest instant a stated date can mean, as a comparable key. Uses 31 as
   the coarse month upper bound: this over-covers short months by a few days,
   which is the safe direction for an interval query (it never excludes a real
   date), and is documented rather than hidden."
  [s]
  (when-let [{:innen.time/keys [year month day]} (parse s)]
    (key* year (or month 12) (or day 31))))

(defn certain?
  "True when the stated date is precise to the day -- i.e. when a day-level
   claim about it is the source's claim and not this namespace's inference."
  [s]
  (= :day (:innen.time/precision (parse s))))

(defn before?
  "True when a is strictly, unambiguously before b (a's latest possible
   instant precedes b's earliest). Overlapping coarse dates return false --
   unknown order is not `false` dressed up as an answer, so callers that care
   should use (comparable? a b)."
  [a b]
  (let [ua (upper-key a) lb (lower-key b)]
    (boolean (and ua lb (< ua lb)))))

(defn comparable?
  "True when a and b are ordered with certainty in one direction or the other
   (their possible-instant intervals do not overlap)."
  [a b]
  (or (before? a b) (before? b a)))

(defn interval
  "Normalise an interval map `{:from \"1602\" :to \"1799-12-31\"}` into
   comparable keys. A missing `:from` means \"unknown start\" and a missing
   `:to` means \"still in force as of the record's own as-of date\" -- both are
   represented as nil bounds, never as sentinel dates."
  [{:keys [from to]}]
  {:innen.time/from-key (lower-key from)
   :innen.time/to-key (upper-key to)
   :innen.time/from from
   :innen.time/to to
   :innen.time/open-ended? (nil? to)})

(defn within?
  "Is `date` inside `iv`? Nil bounds are open. A coarse `date` counts as inside
   when ANY instant it could denote is inside -- the permissive reading, chosen
   because excluding a possibly-in-range fact from a historical slice loses
   real evidence, whereas including it is visible and checkable."
  [iv date]
  (let [{:innen.time/keys [from-key to-key]} (interval iv)
        lo (lower-key date)
        hi (upper-key date)]
    (boolean (and lo hi
                  (or (nil? to-key) (<= lo to-key))
                  (or (nil? from-key) (>= hi from-key))))))

(defn overlap?
  "Do two intervals share any possible instant? Nil bounds are open."
  [a b]
  (let [{a-from :innen.time/from-key a-to :innen.time/to-key} (interval a)
        {b-from :innen.time/from-key b-to :innen.time/to-key} (interval b)]
    (and (or (nil? a-to) (nil? b-from) (>= a-to b-from))
         (or (nil? b-to) (nil? a-from) (>= b-to a-from)))))

(defn sane-interval?
  "An interval is sane when both bounds parse (or are absent) and, when both
   are present and comparable, from is not after to."
  [{:keys [from to] :as iv}]
  (let [f (when from (lower-key from))
        t (when to (upper-key to))]
    (and (or (nil? from) (some? f))
         (or (nil? to) (some? t))
         (or (nil? f) (nil? t) (<= f t))
         (some? iv))))

(defn span-years
  "Coarse span in years between an interval's bounds, or nil when either bound
   is unknown. Years only -- see the namespace docstring on why no finer
   duration is offered."
  [{:keys [from to]}]
  (let [a (:innen.time/year (parse from))
        b (:innen.time/year (parse to))]
    (when (and a b) (- b a))))
