(ns newsfeed.instant
  "Normalise the two date formats syndication feeds actually use — RFC 822/1123
   (RSS `<pubDate>`) and ISO 8601 (Atom `<published>`/`<updated>`) — to a single
   `YYYY-MM-DDTHH:MM:SSZ` string in UTC.

   Deliberately no platform date type. A feed date is a value being normalised,
   not a moment being measured; going through `java.util.Date` / `js/Date`
   would make the same input parse differently on the two runtimes (the JS
   parser is lenient and locale-influenced) and make the result untestable
   without a clock. Civil-date arithmetic is exact and portable.

   Unparseable input returns nil rather than a guess. Callers keep the raw
   string alongside, so nothing is lost."
  (:require [kotoba.lang.text :as str]))

;; ── civil date arithmetic (Howard Hinnant's algorithms, integer-exact) ───────

(defn days-from-civil
  "Days since 1970-01-01 for a proleptic Gregorian y-m-d."
  [y m d]
  (let [y   (if (<= m 2) (dec y) y)
        era (quot (if (>= y 0) y (- y 399)) 400)
        yoe (- y (* era 400))
        doy (+ (quot (+ (* 153 (+ m (if (> m 2) -3 9))) 2) 5) (dec d))
        doe (+ (* yoe 365) (quot yoe 4) (- (quot yoe 100)) doy)]
    (+ (* era 146097) doe -719468)))

(defn civil-from-days
  "Days since 1970-01-01 → [y m d]."
  [z]
  (let [z   (+ z 719468)
        era (quot (if (>= z 0) z (- z 146096)) 146097)
        doe (- z (* era 146097))
        yoe (quot (+ (- doe (quot doe 1460)) (quot doe 36524) (- (quot doe 146096))) 365)
        y   (+ yoe (* era 400))
        doy (- doe (+ (* 365 yoe) (quot yoe 4) (- (quot yoe 100))))
        mp  (quot (+ (* 5 doy) 2) 153)
        d   (inc (- doy (quot (+ (* 153 mp) 2) 5)))
        m   (+ mp (if (< mp 10) 3 -9))]
    [(if (<= m 2) (inc y) y) m d]))

(defn- pad2 [n] (if (< n 10) (str "0" n) (str n)))

(defn- ->iso
  "y-m-d h:m:s at `offset-min` east of UTC → the same instant as a UTC string."
  [y mo d h mi s offset-min]
  (let [secs (+ (* 86400 (days-from-civil y mo d)) (* 3600 h) (* 60 mi) s (* -60 offset-min))
        days (long (Math/floor (/ secs 86400.0)))
        rem  (- secs (* days 86400))
        [uy um ud] (civil-from-days days)]
    (str uy "-" (pad2 um) "-" (pad2 ud) "T"
         (pad2 (quot rem 3600)) ":" (pad2 (quot (mod rem 3600) 60)) ":"
         (pad2 (mod rem 60)) "Z")))

;; ── shared vocabulary ────────────────────────────────────────────────────────

(def ^:private months
  {"jan" 1 "feb" 2 "mar" 3 "apr" 4 "may" 5 "jun" 6
   "jul" 7 "aug" 8 "sep" 9 "oct" 10 "nov" 11 "dec" 12})

;; RFC 822 §5.1 zones plus the North American daylight names feeds still emit.
;; Anything else with a letter zone is treated as UTC by RFC 2822's rule for
;; unrecognised zones, which is what "-0000" means anyway.
(def ^:private zone-min
  {"ut" 0 "utc" 0 "gmt" 0 "z" 0
   "est" -300 "edt" -240 "cst" -360 "cdt" -300
   "mst" -420 "mdt" -360 "pst" -480 "pdt" -420})

(defn- digits? [s] (and (seq s) (every? #(<= 48 (int %) 57) (map #(#?(:clj int :cljs (fn [c] (.charCodeAt c 0))) %) s))))

(defn- ->int [s]
  (when (and s (digits? s))
    #?(:clj (Long/parseLong s) :cljs (js/parseInt s 10))))

(defn- offset->min
  "\"+0900\" | \"+09:00\" | \"GMT\" | \"Z\" → minutes east of UTC, or nil."
  [tz]
  (when-let [tz (some-> tz str/trim not-empty)]
    (let [low (str/lower tz)]
      (or (zone-min low)
          (when (#{"+" "-"} (subs tz 0 1))
            (let [sign (if (= "-" (subs tz 0 1)) -1 1)
                  body (str/replace (subs tz 1) ":" "")]
              (when (and (>= (count body) 3) (digits? body))
                (let [body (if (= 3 (count body)) (str "0" body) body)]
                  (* sign (+ (* 60 (->int (subs body 0 2))) (->int (subs body 2 4))))))))))))

;; ── the two formats ──────────────────────────────────────────────────────────

(defn parse-rfc822
  "\"Mon, 03 Aug 2026 12:04:29 +0900\" → \"2026-08-03T03:04:29Z\". The leading
   day-of-week is optional, as is the seconds field."
  [s]
  (when-let [s (some-> s str/trim not-empty)]
    (let [s (if-let [c (str/index-of s ",")] (str/trim (subs s (inc c))) s)
          parts (str/split s #"\s+")]
      (when (>= (count parts) 4)
        (let [[d mon y t & more] parts
              [h mi sec] (str/split (or t "") #":")
              tz (offset->min (or (first more) "gmt"))]
          (when-let [mo (months (str/lower (str mon)))]
            (let [dd (->int d) yy (->int y) hh (->int h) mm (->int mi)]
              (when (and dd yy hh mm)
                (->iso (if (< yy 100) (+ 1900 yy) yy) mo dd hh mm
                       (or (->int sec) 0) (or tz 0))))))))))

(defn parse-iso
  "\"2026-08-03T12:04:29.123+09:00\" → \"2026-08-03T03:04:29Z\". A bare date is
   read as midnight UTC."
  [s]
  (when-let [s (some-> s str/trim not-empty)]
    (let [[date rest] (str/split (str/replace s #"\s+" "T") #"T" 2)
          [y mo d] (str/split (str date) #"-")
          yy (->int y) mm (->int mo) dd (->int d)]
      (when (and yy mm dd)
        (if (str/blank? (str rest))
          (->iso yy mm dd 0 0 0 0)
          (let [tz-at (or (str/index-of rest "Z") (str/index-of rest "z")
                          (str/index-of rest "+")
                          ;; a '-' only counts as the zone once past the time
                          (let [i (str/last-index-of rest "-")] (when (and i (> i 2)) i)))
                clock (if tz-at (subs rest 0 tz-at) rest)
                tz    (if tz-at (subs rest tz-at) "Z")
                clock (if-let [dot (str/index-of clock ".")] (subs clock 0 dot) clock)
                [h mi sec] (str/split clock #":")]
            (when-let [hh (->int h)]
              (->iso yy mm dd hh (or (->int mi) 0) (or (->int sec) 0)
                     (or (offset->min tz) 0)))))))))

(defn normalize
  "Either format → \"YYYY-MM-DDTHH:MM:SSZ\", or nil."
  [s]
  (when-let [s (some-> s str/trim not-empty)]
    (if (and (>= (count s) 5) (digits? (subs s 0 4)) (= "-" (subs s 4 5)))
      (parse-iso s)
      (or (parse-rfc822 s) (parse-iso s)))))

(defn day
  "The date part of a normalised instant: \"2026-08-03T…Z\" → \"2026-08-03\"."
  [iso]
  (when (and (string? iso) (>= (count iso) 10)) (subs iso 0 10)))

(defn days-between
  "Whole days from the earlier ISO instant to the later one, or nil."
  [from-iso to-iso]
  (let [d (fn [iso] (when-let [dt (day iso)]
                      (let [[y m dd] (map ->int (str/split dt #"-"))]
                        (when (and y m dd) (days-from-civil y m dd)))))]
    (when-let [a (d from-iso)] (when-let [b (d to-iso)] (- b a)))))
