(ns kotoba.itinerary
  "Scheduled legs, connection legality and itinerary construction — pure
  data contracts.

  A kotoba-lang capability library for the journey-planning half of a
  fare search. `kotoba-lang/reservation` answers *how many are left to
  sell* and *what this one costs* for a SINGLE operator's own inventory.
  It cannot answer the question a shopping engine is actually asked:
  **which sequences of flights actually get someone from A to B, and are
  they legally connectable?**

  That is what this namespace is. Given a pool of scheduled legs it
  builds the itineraries that connect, and — the part that matters for
  this fleet — it lets a governor RECOMPUTE the legality of an itinerary
  an advisor proposed, rather than restating the advisor's claim. See
  `violations`.

  Portable (.cljc) across JVM / ClojureScript / SCI / GraalVM. No
  network, no I/O, no ambient clock.

  ## Time is integer minutes since the epoch, and always an argument

  Connection legality is arithmetic on instants, so every leg carries
  `:leg/depart-min` and `:leg/arrive-min` — integer minutes since
  1970-01-01T00:00Z. Local wall-clock strings may ride along for display
  (`:leg/depart` / `:leg/arrive`) but nothing here ever computes with
  them.

  Nothing in this namespace reads a clock. A governor recomputing an
  itinerary's legality an hour later must reach the same verdict, so
  \"now\" is never ambient.

  ## What this library does NOT know

  Stated up front, because a shopping engine that quietly guesses at
  these is worse than one that refuses:

  - **No timezone database.** `datetime->minutes` takes the UTC offset as
    an argument. Deriving \"Asia/Tokyo on this date\" needs tzdata, which
    is a real dependency with a real update cadence; pretending to know
    it from a three-letter airport code is how a shopping engine sells a
    connection that does not exist.
  - **No published MCT table.** `mct-for` is the LOOKUP STRUCTURE for
    minimum connect times (per airport, per carrier pair, online vs
    interline), not the data. Real MCTs are published per
    airport/terminal/carrier-pair and change; an operator supplies their
    own table.
  - **No co-terminal knowledge.** HND and NRT are different airports
    here. A caller that wants them treated as one origin runs `build`
    once per airport and concatenates.
  - **No mileage data.** `kotoba.fare` checks maximum-permitted-mileage
    against segment mileages the caller supplies; neither library ships
    a distance table."
  (:require [kotoba.lang.text :as str]))

;; ---------------------------------------------------------------------------
;; Calendar and clock arithmetic — proleptic Gregorian, exact integers
;; ---------------------------------------------------------------------------
;; Opt-in the same way `kotoba.reservation`'s calendar section is: the
;; core path never calls these for you. They exist so a caller — and a
;; governor recomputing after the fact — derive instants the same way,
;; from the same pure functions, instead of each hand-rolling it.

(defn parse-date
  "Parse an ISO `YYYY-MM-DD` into `[y m d]` integers, or nil when the
  string is not that shape."
  [s]
  (when (string? s)
    (when-let [[_ y m d] (re-matches #"(\d{4})-(\d{2})-(\d{2})" s)]
      [(parse-long y) (parse-long m) (parse-long d)])))

(defn days-from-civil
  "Days since 1970-01-01 for a proleptic-Gregorian `[y m d]`. Howard
  Hinnant's algorithm: exact integer arithmetic, no floating point, no
  locale, no clock."
  [[y m d]]
  (let [y (if (<= m 2) (dec y) y)
        era (quot (if (>= y 0) y (- y 399)) 400)
        yoe (- y (* era 400))                                  ; [0, 399]
        doy (+ (quot (+ (* 153 (+ m (if (> m 2) -3 9))) 2) 5) (dec d))
        doe (+ (* yoe 365) (quot yoe 4) (- (quot yoe 100)) doy)]
    (+ (* era 146097) doe -719468)))

(defn weekday-of
  "Proleptic-Gregorian weekday for an ISO date string: 0=Sunday .. 6=Saturday.
  nil for an unparseable date.

  `kotoba.fare` keys its day-of-week rule (ATPCO category 2) on exactly
  this numbering, and takes the weekday as data. This is the function
  both the advisor and the governor should derive it with, so that a
  disagreement about eligibility is never a disagreement about what day
  it was."
  [s]
  (when-let [ymd (parse-date s)]
    (mod (+ 4 (days-from-civil ymd)) 7)))                      ; 1970-01-01 was a Thursday

(defn days-between
  "Whole days from `from` to `to`, both ISO dates. Negative when `to`
  precedes `from`; nil when either is unparseable.

  This is how an advance-purchase requirement (ATPCO category 5) and a
  minimum/maximum stay (categories 6/7) get their day counts. `kotoba.fare`
  takes those counts as data rather than deriving them, so that the
  arithmetic lives in one place and both sides of a governor check use it."
  [from to]
  (let [a (parse-date from), b (parse-date to)]
    (when (and a b) (- (days-from-civil b) (days-from-civil a)))))

(defn parse-datetime
  "Parse `YYYY-MM-DDTHH:MM` (seconds optional and ignored) into
  `[y m d hh mm]`, or nil."
  [s]
  (when (string? s)
    (when-let [[_ y m d hh mm] (re-matches #"(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2})(?::\d{2})?" s)]
      [(parse-long y) (parse-long m) (parse-long d) (parse-long hh) (parse-long mm)])))

(defn datetime->minutes
  "Minutes since 1970-01-01T00:00Z for a LOCAL datetime string at
  `utc-offset-minutes` east of UTC (JST = 540, EST = -300).

  The offset is an argument because this library has no timezone
  database — see the ns docstring. A caller who passes the wrong offset
  gets a wrong instant, but a *stated* wrong one, which a governor
  recomputing from the same schedule data will reproduce and an auditor
  can find. Returns nil for an unparseable datetime."
  [s utc-offset-minutes]
  (when-let [[y m d hh mm] (parse-datetime s)]
    (- (+ (* (days-from-civil [y m d]) 1440) (* hh 60) mm)
       (or utc-offset-minutes 0))))

(defn date-of-minute
  "The UTC calendar date containing epoch-minute `n`, as `YYYY-MM-DD`.
  Used for reporting, not for rule evaluation — a fare's date rules are
  about the LOCAL date of travel, which the caller derives from its own
  offsets."
  [n]
  (when (integer? n)
    (let [z (+ (quot n 1440) (if (and (neg? n) (pos? (mod n 1440))) -1 0))
          z (+ z 719468)
          era (quot (if (>= z 0) z (- z 146096)) 146097)
          doe (- z (* era 146097))
          yoe (quot (+ (- doe (quot doe 1460)) (quot doe 36524) (- (quot doe 146096))) 365)
          y (+ yoe (* era 400))
          doy (- doe (+ (* 365 yoe) (quot yoe 4) (- (quot yoe 100))))
          mp (quot (+ (* 5 doy) 2) 153)
          d (+ (- doy (quot (+ (* 153 mp) 2) 5)) 1)
          m (+ mp (if (< mp 10) 3 -9))
          y (if (<= m 2) (inc y) y)
          pad (fn [v] (if (< v 10) (str "0" v) (str v)))]
      (str y "-" (pad m) "-" (pad d)))))

;; ---------------------------------------------------------------------------
;; Legs
;; ---------------------------------------------------------------------------

(defn- code? [s n]
  (and (string? s) (= n (count s)) (= s (str/upper s))))

(defn leg
  "Construct one scheduled leg: `carrier` flight `number` from `origin` to
  `destination`, departing at epoch-minute `depart-min` and arriving at
  `arrive-min`.

  Optional:
    :id        -- caller's identifier; defaults to carrier+number+depart
    :classes   -- {booking-class -> seats-available}, e.g. {\"Y\" 9 \"B\" 4}
    :depart    -- local wall-clock string, carried for display only
    :arrive    -- likewise
    :miles     -- great-circle or ticketed mileage for this leg, used by
                  `kotoba.fare` for maximum-permitted-mileage checks
    :equipment -- aircraft type, carried for disclosure

  Returns nil for a structurally invalid leg — a leg that arrives before
  it departs, or one whose airport codes are not three upper-case letters
  — rather than a leg that lies about itself. A shopping engine that
  accepts a backwards leg will happily construct an itinerary that
  arrives before it leaves."
  [carrier number origin destination depart-min arrive-min
   & {:keys [id classes depart arrive miles equipment]}]
  (when (and (code? carrier 2) (some? number)
             (code? origin 3) (code? destination 3)
             (not= origin destination)
             (integer? depart-min) (integer? arrive-min)
             (< depart-min arrive-min))
    (cond-> {:leg/id          (or id (str carrier number "-" depart-min))
             :leg/carrier     carrier
             :leg/number      (str number)
             :leg/origin      origin
             :leg/destination destination
             :leg/depart-min  depart-min
             :leg/arrive-min  arrive-min}
      classes   (assoc :leg/classes classes)
      depart    (assoc :leg/depart depart)
      arrive    (assoc :leg/arrive arrive)
      miles     (assoc :leg/miles miles)
      equipment (assoc :leg/equipment equipment))))

(defn duration-minutes
  "Airborne-plus-ground time of one leg, in minutes."
  [l]
  (- (:leg/arrive-min l 0) (:leg/depart-min l 0)))

(defn seats-in-class
  "Seats shown available in `booking-class` on `l`. 0 when the leg
  publishes no availability for that class.

  Availability is a claim by whoever supplied the schedule, not a
  guarantee — `kotoba.reservation` is where an operator's own inventory
  is authoritative. This is here so a search can decline to return a
  solution in a class the schedule already says is closed."
  [l booking-class]
  (get (:leg/classes l) booking-class 0))

;; ---------------------------------------------------------------------------
;; Minimum connect times
;; ---------------------------------------------------------------------------

(defn mct-table
  "Build a minimum-connect-time lookup from an operator's own published
  data. Entries, most specific first:

    {[\"NRT\" \"NH\" \"UA\"] 90     ; this airport, this carrier pair
     [\"NRT\" :online]      45     ; same carrier onto itself
     [\"NRT\" :interline]   90     ; carrier change
     [\"NRT\" :default]     60     ; anything else at this airport
     [:default]            60}    ; anything else anywhere

  The structure is the contract; the numbers are the operator's. This
  library ships no MCT data — see the ns docstring."
  [m]
  (into {} (filter (fn [[_ v]] (integer? v)) m)))

(defn mct-for
  "Minimum connect minutes at `airport` arriving on `carrier-in` and
  departing on `carrier-out`, resolved against `table` most-specific
  first. Falls back to `fallback` (default 60) when the table says
  nothing."
  ([table airport carrier-in carrier-out] (mct-for table airport carrier-in carrier-out 60))
  ([table airport carrier-in carrier-out fallback]
   (let [online? (= carrier-in carrier-out)]
     (or (get table [airport carrier-in carrier-out])
         (get table [airport (if online? :online :interline)])
         (get table [airport :default])
         (get table [:default])
         fallback))))

(defn connect-minutes
  "Ground time between arriving on `a` and departing on `b`. Negative when
  `b` leaves before `a` lands."
  [a b]
  (- (:leg/depart-min b 0) (:leg/arrive-min a 0)))

(defn connects?
  "Can a passenger legally connect from `a` onto `b`?

  Requires that `b` departs from where `a` arrives, that the ground time
  is at least the applicable minimum connect time, and that it is no
  longer than `:max-connect` (default 24h — beyond that it is a stopover,
  which is a different fare-construction question, not a connection).

  Options: `:mct-table`, `:mct-fallback`, `:max-connect`."
  [a b & {:keys [mct-table mct-fallback max-connect]}]
  (and (= (:leg/destination a) (:leg/origin b))
       (let [gap (connect-minutes a b)
             need (mct-for (or mct-table {}) (:leg/destination a)
                           (:leg/carrier a) (:leg/carrier b)
                           (or mct-fallback 60))]
         (and (>= gap need) (<= gap (or max-connect 1440))))))

;; ---------------------------------------------------------------------------
;; Itineraries
;; ---------------------------------------------------------------------------

(defn itinerary
  "Construct an itinerary from an ordered, non-empty vector of legs.
  Returns nil when `legs` is empty — an itinerary with no legs is not a
  journey, and letting one exist means a search can report a zero-elapsed
  \"solution\" that goes nowhere."
  [legs]
  (when (seq legs)
    (let [legs (vec legs)]
      {:itin/legs        legs
       :itin/origin      (:leg/origin (first legs))
       :itin/destination (:leg/destination (peek legs))
       :itin/depart-min  (:leg/depart-min (first legs))
       :itin/arrive-min  (:leg/arrive-min (peek legs))})))

(defn elapsed-minutes
  "Door-to-door elapsed time of an itinerary, in minutes."
  [it]
  (- (:itin/arrive-min it 0) (:itin/depart-min it 0)))

(defn connection-count
  "Number of connections (legs − 1)."
  [it]
  (max 0 (dec (count (:itin/legs it)))))

(defn carriers
  "Distinct marketing carriers on an itinerary, in order of first
  appearance."
  [it]
  (into [] (distinct) (map :leg/carrier (:itin/legs it))))

(defn points
  "Every airport an itinerary touches, in order: origin, each connection
  point, destination."
  [it]
  (let [legs (:itin/legs it)]
    (into [(:leg/origin (first legs))] (map :leg/destination) legs)))

(defn intermediate-points
  "The connection points only — what a fare's routing (ATPCO category 25
  routing map) is checked against."
  [it]
  (let [p (points it)]
    (if (> (count p) 2) (subvec (vec p) 1 (dec (count p))) [])))

(defn total-miles
  "Sum of `:leg/miles` across the itinerary, or nil when any leg omits
  it. nil rather than a partial sum on purpose: a maximum-permitted-mileage
  check against a sum that silently dropped a leg would pass fares it
  should reject."
  [it]
  (let [ms (map :leg/miles (:itin/legs it))]
    (when (every? integer? ms) (reduce + 0 ms))))

;; ---------------------------------------------------------------------------
;; Construction — the search over a schedule
;; ---------------------------------------------------------------------------

(def default-limits
  "The bounds `build` applies when a caller states none. They exist to
  keep a search finite, and every one of them is reported back on the
  result so a caller can tell a bound apart from an empty market."
  {:max-connections     2
   :max-elapsed-minutes 1800                                    ; 30h
   :max-connect         1440                                    ; 24h
   :mct-fallback        60
   :max-results         200})

(defn- extend-path
  [pool acc {:keys [destination max-connections max-elapsed-minutes] :as opts} path visited]
  (let [last-leg (peek path)]
    (cond
      (= (:leg/destination last-leg) destination)
      ;; The elapsed ceiling is checked HERE, on emit, not only while
      ;; extending. Checking it only on the extension step let a nonstop
      ;; through unmeasured -- it never takes that branch -- so a caller
      ;; asking for "under two hours" was handed a seven-hour flight.
      (if (> (- (:leg/arrive-min last-leg) (:leg/depart-min (first path))) max-elapsed-minutes)
        acc
        (conj acc (itinerary path)))

      (>= (dec (count path)) max-connections)
      acc

      :else
      (reduce
       (fn [acc nxt]
         (if (or (visited (:leg/destination nxt))
                 (not (connects? last-leg nxt
                                 :mct-table (:mct-table opts)
                                 :mct-fallback (:mct-fallback opts)
                                 :max-connect (:max-connect opts)))
                 (> (- (:leg/arrive-min nxt) (:leg/depart-min (first path)))
                    max-elapsed-minutes))
           acc
           (extend-path pool acc opts (conj path nxt)
                        (conj visited (:leg/destination nxt)))))
       acc
       (get pool (:leg/destination last-leg) [])))))

(defn build
  "Build every itinerary in `legs` that gets from `:origin` to
  `:destination` within the stated bounds.

  Options (defaults from `default-limits`):
    :origin :destination        -- required, IATA airport codes
    :depart-not-before          -- epoch minute; earliest first departure
    :depart-not-after           -- epoch minute; latest first departure
    :booking-class              -- when given, every leg must show a seat
                                   in this class (`seats-in-class` > 0)
    :max-connections            -- 0 = nonstop only
    :max-elapsed-minutes        -- door-to-door ceiling
    :max-connect                -- ground time above which it is a stopover
    :mct-table :mct-fallback    -- minimum connect times
    :max-results                -- cap on returned itineraries

  Returns
  `{:itin/results [it ..] :itin/found n :itin/truncated? bool :itin/limits {..}}`
  sorted by elapsed time then departure.

  `:itin/truncated?` is not decoration. A search that silently returns
  its first 200 hits reads as \"this is the market\" when it is not, and
  the cheapest fare may be on the itinerary that got cut. `:itin/found`
  is the count BEFORE the cap, so a caller can always tell the two
  apart.

  Revisiting an airport is pruned: an itinerary that touches the same
  point twice is a circle trip, which prices under different rules than
  the through fares this pool is being searched for."
  ;; `:destination` is read by `extend-path` out of `opts`, not here.
  [legs {:keys [origin depart-not-before depart-not-after booking-class] :as opts}]
  (let [opts (merge default-limits opts)
        usable (filterv (fn [l]
                          (and (map? l) (:leg/origin l)
                               (or (nil? booking-class) (pos? (seats-in-class l booking-class)))))
                        legs)
        pool (group-by :leg/origin usable)
        starts (filterv (fn [l]
                          (and (= origin (:leg/origin l))
                               (or (nil? depart-not-before) (>= (:leg/depart-min l) depart-not-before))
                               (or (nil? depart-not-after) (<= (:leg/depart-min l) depart-not-after))))
                        usable)
        all (reduce (fn [acc s]
                      (extend-path pool acc opts [s] #{origin (:leg/destination s)}))
                    []
                    starts)
        sorted (vec (sort-by (juxt elapsed-minutes :itin/depart-min) all))
        cap (:max-results opts)]
    {:itin/results    (vec (take cap sorted))
     :itin/found      (count sorted)
     :itin/truncated? (> (count sorted) cap)
     :itin/limits     (select-keys opts [:max-connections :max-elapsed-minutes
                                         :max-connect :mct-fallback :max-results])}))

;; ---------------------------------------------------------------------------
;; Independent verification — the governor seam
;; ---------------------------------------------------------------------------

(defn violations
  "Recompute an itinerary's legality from the legs themselves and report
  EVERY way it fails, not the first.

  This is the seam a governor uses. An advisor can assemble a plausible
  three-leg itinerary and assert that it connects; it cannot be trusted
  to have checked the minimum connect time at the second stop, and a
  language model will produce a 20-minute interline connection at Narita
  without hesitation. This function does the arithmetic against the same
  schedule data, so the check is a recompute rather than a restatement.

  Options are the same as `build`'s, plus `:origin` / `:destination` to
  assert the itinerary is for the journey that was actually requested.

  Returns a vector of keywords, empty when the itinerary is sound:
    :empty-itinerary :legs-do-not-chain :non-chronological
    :below-minimum-connect-time :connection-exceeds-maximum
    :too-many-connections :exceeds-maximum-elapsed :revisits-a-point
    :origin-mismatch :destination-mismatch :class-not-available"
  ([it] (violations it {}))
  ([it opts]
   (let [{:keys [origin destination booking-class] :as o} (merge default-limits opts)
         legs (:itin/legs it)]
     (if (empty? legs)
       [:empty-itinerary]
       (let [pairs (map vector legs (rest legs))
             pts (points it)
             v (cond-> []
                 (some (fn [[a b]] (not= (:leg/destination a) (:leg/origin b))) pairs)
                 (conj :legs-do-not-chain)

                 (some (fn [[a b]] (neg? (connect-minutes a b))) pairs)
                 (conj :non-chronological)

                 ;; A NEGATIVE gap is reported as :non-chronological only.
                 ;; It is trivially also below every minimum, but saying so
                 ;; adds nothing: an operator told "departs before the
                 ;; previous leg lands" has the whole diagnosis, and a second
                 ;; keyword restating it would make the vector longer without
                 ;; making it more informative.
                 (some (fn [[a b]]
                         (and (= (:leg/destination a) (:leg/origin b))
                              (>= (connect-minutes a b) 0)
                              (< (connect-minutes a b)
                                 (mct-for (or (:mct-table o) {}) (:leg/destination a)
                                          (:leg/carrier a) (:leg/carrier b)
                                          (:mct-fallback o)))))
                       pairs)
                 (conj :below-minimum-connect-time)

                 (some (fn [[a b]] (> (connect-minutes a b) (:max-connect o))) pairs)
                 (conj :connection-exceeds-maximum)

                 (> (connection-count it) (:max-connections o))
                 (conj :too-many-connections)

                 (> (elapsed-minutes it) (:max-elapsed-minutes o))
                 (conj :exceeds-maximum-elapsed)

                 (not= (count pts) (count (distinct pts)))
                 (conj :revisits-a-point)

                 (and origin (not= origin (:itin/origin it)))
                 (conj :origin-mismatch)

                 (and destination (not= destination (:itin/destination it)))
                 (conj :destination-mismatch)

                 (and booking-class
                      (some #(zero? (seats-in-class % booking-class)) legs))
                 (conj :class-not-available))]
         v)))))

(defn valid?
  "True when `violations` finds nothing wrong with `it` under `opts`."
  ([it] (empty? (violations it)))
  ([it opts] (empty? (violations it opts))))

(defn describe-violation
  "Human-readable label for a violation keyword — for operator consoles
  and audit records, never for control flow."
  [k]
  (case k
    :empty-itinerary             "an itinerary with no legs is not a journey"
    :legs-do-not-chain           "a leg does not depart from where the previous one arrived"
    :non-chronological           "a leg departs before the previous one arrives"
    :below-minimum-connect-time  "a connection is shorter than the minimum connect time"
    :connection-exceeds-maximum  "a connection is long enough to be a stopover, not a connection"
    :too-many-connections        "more connections than the search allowed"
    :exceeds-maximum-elapsed     "door-to-door time exceeds the maximum allowed"
    :revisits-a-point            "the itinerary touches the same airport twice"
    :origin-mismatch             "the itinerary does not start where the journey was requested from"
    :destination-mismatch        "the itinerary does not end where the journey was requested to"
    :class-not-available         "a leg shows no seat available in the requested booking class"
    (str/replace (name k) "-" " ")))
