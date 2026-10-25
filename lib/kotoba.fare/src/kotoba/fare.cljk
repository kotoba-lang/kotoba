(ns kotoba.fare
  "Filed fares, fare rules, fare construction and lowest-fare search —
  pure data contracts.

  A kotoba-lang capability library for the pricing half of a flight
  shopping engine. `kotoba.itinerary` answers *which sequences of flights
  actually connect*; `kotoba.reservation` answers *how many are left to
  sell* and *what one operator's own rate plan charges*. Neither answers
  the question a fare search is asked: **given these itineraries and
  these filed fares, what is the lowest price that is actually
  applicable, and why.**

  Portable (.cljc) across JVM / ClojureScript / SCI / GraalVM. No
  network, no I/O, no ambient clock, no floating point.

  ## Why this is worth having at all

  A language model asked for the cheapest fare will produce a number. It
  will be plausible, formatted correctly, and frequently wrong — the
  advance-purchase window unchecked, a blackout date ignored, a fare
  applied to a carrier that never filed it. The point of this namespace
  is not to make an advisor better at that. It is to let a GOVERNOR
  recompute the answer from the filed fares and reject the claim when
  the arithmetic disagrees:

    `price-matches-claim?`  -- is that total what these fares actually add to?
    `fare-applies?`         -- is this fare even eligible for this journey?
    `no-cheaper-than?`      -- is \"cheapest\" actually the cheapest here?

  The last one is the one that does not exist anywhere else in this
  fleet. `kotoba.reservation/quote-matches-claim?` verifies a price
  against ONE rate plan. Verifying a *shopping* claim means re-running
  the search, because \"this is the lowest fare\" is a statement about
  every fare that was not chosen.

  ## Determinism, and why there are no floats here

  Every amount is an integer. Fares filed in a currency are integers in
  that currency's MINOR UNIT (JPY: 1 = ¥1; USD: 1 = 1 cent). Fares filed
  in Neutral Units of Construction are integers in HUNDREDTHS OF A NUC,
  converted with an integer rate of exchange scaled by 10^4 (see
  `nuc->minor`). Percentage taxes are integers in BASIS POINTS
  (`bp-scale` = 10000 = 100%), applied with truncating integer division.

  Truncation is a real decision. IATA's own currency rounding rules
  round NUC fares UP to the next unit for most currencies; this library
  truncates instead, so a converted fare can only ever land at or below
  the rounded one. That is deliberate: this library will not quietly
  invent a rounding convention that changes what a passenger is charged.
  An operator whose filing requires IATA rounding files in the currency
  and passes `:fare/amount` directly, and the conversion never runs.

  ## No clock, and no derived facts

  Nothing here reads a clock, and nothing here derives a date fact. An
  advance-purchase check needs to know how many days lie between the
  sale and the flight; this namespace takes that number as data rather
  than computing it, exactly the way `kotoba.reservation/quote-for`
  takes each date's weekday as data. `kotoba.itinerary/days-between` and
  `/weekday-of` are the pure functions both an advisor and a governor
  should derive those facts with — one implementation, so that a
  disagreement about eligibility can never turn out to be a
  disagreement about what day it was.

  ## Unverifiable is not the same as satisfied

  When a fare files a rule and the fact needed to check it is missing,
  the fare does NOT apply, and the reported violation says so
  (`:advance-purchase-unverifiable`, `:day-of-week-unverifiable`, ...).
  Assuming compliance because the input was incomplete is how a search
  returns a fare nobody is entitled to. This follows the same stance
  ADR-2800002200 took for `cloud-itonami-isic-5110`: a check that cannot
  run is a violation, not a pass.

  ## What this library does NOT implement

  Named, because a fare engine that quietly omits a category prices
  tickets that cannot be issued:

  - **ATPCO category 10, fare combinability.** Components here price
    INDEPENDENTLY, which is what makes `search` able to take the cheapest
    applicable fare per component (see `search`). Real combinability
    restricts which fare components may sit in one ticket, and would
    invalidate that optimization. Not implemented, not approximated.
  - **Categories 12 (surcharges), 14 (travel restrictions), 17 (HIP /
    higher intermediate point), 23 (miscellaneous), 25 (fare by rule).**
    Surcharges are accepted as caller-supplied data (`:surcharges`)
    rather than derived from a filing.
  - **Routing maps as graphs.** `:fare/routing` here is an ordered list
    of permitted points and a component's intermediates must be a
    subsequence of it. Published routing maps are directed graphs with
    alternate branches; the subsequence rule accepts a strict subset of
    what a real map permits, so it can reject a fare that is genuinely
    applicable. It never accepts one that is not.
  - **Ticketing, filing, settlement.** Nothing here files a fare with an
    authority, issues a document, or moves money."
  (:require [kotoba.lang.text :as str]))

(def bp-scale
  "Basis-point scale: 10000 bp = 100%."
  10000)

(def roe-scale
  "Scale of an integer rate of exchange: `roe` is minor units per NUC,
  multiplied by 10^4. A ROE of 1 NUC = ¥152.2100 is filed here as
  1522100."
  10000)

(def nuc-scale
  "Scale of `:fare/amount-nuc`: hundredths of a NUC. NUC 1234.56 is filed
  here as 123456."
  100)

(defn apply-bp
  "Apply an integer basis-point modifier to an integer minor-unit amount,
  truncating toward zero."
  [amount bp]
  (quot (* amount (or bp 0)) bp-scale))

(defn nuc->minor
  "Convert `amount-nuc` (hundredths of a NUC) to minor units at integer
  `roe` (minor units per NUC × 10^4), truncating.

    (nuc->minor 123456 1522100) ; NUC 1234.56 at ¥152.2100 => ¥187,912
    => 187912

  Truncates rather than applying IATA currency rounding — see the ns
  docstring. Returns nil when either input is not an integer, so a
  missing ROE produces an unpriceable component rather than a free one."
  [amount-nuc roe]
  (when (and (integer? amount-nuc) (integer? roe))
    (quot (* amount-nuc roe) (* nuc-scale roe-scale))))

;; ---------------------------------------------------------------------------
;; Filed fares
;; ---------------------------------------------------------------------------

(defn fare
  "Construct a filed fare: `basis` (the fare basis code) filed by
  `carrier` for the market `origin`->`destination`, in booking `class`.

  Exactly one of `:amount` (minor units, with `:currency`) or
  `:amount-nuc` (hundredths of a NUC) must be given. A fare filed in NUC
  needs a `:roe` at pricing time; one filed in a currency never converts.

  Optional:
    :direction  -- :one-way (default) or :round-trip; a round-trip fare
                   prices half per direction, so callers that want the
                   half-round-trip amount file it as such
    :routing    -- ordered vector of permitted intermediate points; nil
                   means unrestricted (see the ns docstring on routing)
    :mpm        -- maximum permitted mileage for the component
    :carriers   -- set of carriers whose flights the fare may be used on;
                   defaults to #{carrier}
    :cabin      -- :economy / :premium-economy / :business / :first,
                   carried for display and never priced
    :rules      -- see `rules`

  Returns nil for a structurally invalid fare rather than one that lies
  about its own market or price."
  [basis carrier origin destination class
   & {:keys [amount currency amount-nuc direction routing mpm carriers cabin rules]}]
  (let [priced? (or (and (integer? amount) (not (neg? amount)) (string? currency))
                    (and (integer? amount-nuc) (not (neg? amount-nuc))))]
    (when (and (string? basis) (string? carrier) (string? origin) (string? destination)
               (some? class) (not= origin destination) priced?)
      (cond-> {:fare/basis       basis
               :fare/carrier     carrier
               :fare/origin      origin
               :fare/destination destination
               :fare/class       class
               :fare/direction   (or direction :one-way)
               :fare/carriers    (or carriers #{carrier})
               :fare/rules       (or rules {})}
        amount     (assoc :fare/amount amount :fare/currency currency)
        amount-nuc (assoc :fare/amount-nuc amount-nuc)
        routing    (assoc :fare/routing (vec routing))
        mpm        (assoc :fare/mpm mpm)
        cabin      (assoc :fare/cabin cabin)))))

(defn rules
  "Construct the rule record carried on a fare. Every key is optional; a
  fare with no rules is unrestricted, which is what an unrestricted
  published fare is.

  The subset implemented, with the ATPCO category each corresponds to:

    :dow             -- cat 2  day/time: set of weekdays (0=Sun..6=Sat)
                        travel may commence on
    :travel-from     -- cat 3  seasonality: earliest travel date
    :travel-to       -- cat 3  seasonality: latest travel date
    :carriers        -- cat 4  flight application (see `fare`'s :carriers)
    :advance-days    -- cat 5  advance reservation/ticketing, minimum days
    :min-stay-days   -- cat 6  minimum stay
    :max-stay-days   -- cat 7  maximum stay
    :blackout        -- cat 11 set of dates on which travel is barred
    :sale-from       -- cat 15 sales restrictions: earliest sale date
    :sale-to         -- cat 15 sales restrictions: latest sale date
    :point-of-sale   -- cat 15 set of permitted points of sale
    :penalty         -- cat 16 penalties; carried for DISCLOSURE only and
                        never priced here — a change fee is charged when a
                        change happens, not when a ticket is shopped

  Categories not in this list are not implemented; see the ns docstring
  rather than assuming a missing key means unrestricted."
  [& {:keys [dow travel-from travel-to advance-days min-stay-days max-stay-days
             blackout sale-from sale-to point-of-sale penalty]}]
  (cond-> {}
    dow           (assoc :rule/dow (set dow))
    travel-from   (assoc :rule/travel-from travel-from)
    travel-to     (assoc :rule/travel-to travel-to)
    advance-days  (assoc :rule/advance-days advance-days)
    min-stay-days (assoc :rule/min-stay-days min-stay-days)
    max-stay-days (assoc :rule/max-stay-days max-stay-days)
    blackout      (assoc :rule/blackout (set blackout))
    sale-from     (assoc :rule/sale-from sale-from)
    sale-to       (assoc :rule/sale-to sale-to)
    point-of-sale (assoc :rule/point-of-sale (set point-of-sale))
    penalty       (assoc :rule/penalty penalty)))

;; ---------------------------------------------------------------------------
;; Rule evaluation
;; ---------------------------------------------------------------------------

(defn- iso<= [a b] (<= (compare a b) 0))

(defn fare-applies?
  "Evaluate `f`'s filed rules against `ctx` and report EVERY violation,
  not the first.

  `ctx` carries the facts a rule needs, all as DATA — nothing is derived
  here (see the ns docstring):

    :travel-date    -- ISO date travel on this component commences
    :weekday        -- 0=Sun..6=Sat for that date
                       (`kotoba.itinerary/weekday-of` derives it)
    :advance-days   -- days between sale and travel
                       (`kotoba.itinerary/days-between` derives it)
    :stay-days      -- days between outbound and return travel
    :sale-date      -- ISO date of sale
    :point-of-sale  -- where the ticket is being sold

  Returns `{:fare/ok? bool :fare/violations [kw ..]}`.

  A filed rule whose fact is absent from `ctx` yields a
  `-unverifiable` violation rather than a pass — an incomplete request
  must not buy a restricted fare. Rules that are NOT filed are simply not
  checked; that is the difference between a fare with no advance-purchase
  requirement and a request that forgot to say when it was being sold."
  [f ctx]
  (let [r (:fare/rules f)
        {:keys [travel-date weekday advance-days stay-days sale-date point-of-sale]} ctx
        v (cond-> []
            ;; cat 3 seasonality
            (and (:rule/travel-from r) (nil? travel-date))       (conj :travel-date-unverifiable)
            (and (:rule/travel-from r) travel-date
                 (not (iso<= (:rule/travel-from r) travel-date))) (conj :before-season)
            (and (:rule/travel-to r) (nil? travel-date))         (conj :travel-date-unverifiable)
            (and (:rule/travel-to r) travel-date
                 (not (iso<= travel-date (:rule/travel-to r))))  (conj :after-season)

            ;; cat 11 blackout
            (and (:rule/blackout r) (nil? travel-date))          (conj :travel-date-unverifiable)
            (and (:rule/blackout r) travel-date
                 (contains? (:rule/blackout r) travel-date))     (conj :blackout-date)

            ;; cat 2 day/time
            (and (:rule/dow r) (nil? weekday))                   (conj :day-of-week-unverifiable)
            (and (:rule/dow r) weekday
                 (not (contains? (:rule/dow r) weekday)))        (conj :day-of-week-not-permitted)

            ;; cat 5 advance reservation/ticketing
            (and (:rule/advance-days r) (nil? advance-days))     (conj :advance-purchase-unverifiable)
            (and (:rule/advance-days r) advance-days
                 (< advance-days (:rule/advance-days r)))        (conj :inside-advance-purchase-window)

            ;; cat 6/7 minimum and maximum stay
            (and (:rule/min-stay-days r) (nil? stay-days))       (conj :stay-unverifiable)
            (and (:rule/min-stay-days r) stay-days
                 (< stay-days (:rule/min-stay-days r)))          (conj :below-minimum-stay)
            (and (:rule/max-stay-days r) (nil? stay-days))       (conj :stay-unverifiable)
            (and (:rule/max-stay-days r) stay-days
                 (> stay-days (:rule/max-stay-days r)))          (conj :above-maximum-stay)

            ;; cat 15 sales restrictions
            (and (:rule/sale-from r) (nil? sale-date))           (conj :sale-date-unverifiable)
            (and (:rule/sale-from r) sale-date
                 (not (iso<= (:rule/sale-from r) sale-date)))    (conj :before-sale-window)
            (and (:rule/sale-to r) (nil? sale-date))             (conj :sale-date-unverifiable)
            (and (:rule/sale-to r) sale-date
                 (not (iso<= sale-date (:rule/sale-to r))))      (conj :after-sale-window)
            (and (:rule/point-of-sale r) (nil? point-of-sale))   (conj :point-of-sale-unverifiable)
            (and (:rule/point-of-sale r) point-of-sale
                 (not (contains? (:rule/point-of-sale r) point-of-sale)))
            (conj :point-of-sale-not-permitted))
        v (vec (distinct v))]
    {:fare/ok? (empty? v) :fare/violations v}))

;; ---------------------------------------------------------------------------
;; Fare components
;; ---------------------------------------------------------------------------

(defn component
  "A fare component: one contiguous run of legs priced by a single fare.

  Derives only structure from the legs — market endpoints, intermediate
  points, carriers, mileage — never a date fact."
  [legs]
  (when (seq legs)
    (let [legs (vec legs)
          pts (into [(:leg/origin (first legs))] (map :leg/destination) legs)
          ms (map :leg/miles legs)]
      {:comp/legs         legs
       :comp/origin       (:leg/origin (first legs))
       :comp/destination  (:leg/destination (peek legs))
       :comp/intermediate (if (> (count pts) 2) (subvec pts 1 (dec (count pts))) [])
       :comp/carriers     (into #{} (map :leg/carrier) legs)
       :comp/miles        (when (every? integer? ms) (reduce + 0 ms))})))

(defn- subsequence?
  "Is `xs` a (not necessarily contiguous) subsequence of `ys`?"
  [xs ys]
  (loop [xs (seq xs) ys (seq ys)]
    (cond
      (nil? xs) true
      (nil? ys) false
      (= (first xs) (first ys)) (recur (next xs) (next ys))
      :else (recur xs (next ys)))))

(defn fare-matches-component?
  "Can `f` be used to price `c` at all, ignoring date rules?

  Checks the structural facts a fare is filed against: the market
  endpoints, the carriers actually flown, the booking class shown open on
  every leg, the routing, and maximum permitted mileage.

  Returns `{:fare/ok? bool :fare/violations [kw ..]}`. Mileage is a
  violation when the fare files an MPM and the component cannot produce a
  mileage — an unmeasurable component must not slip past a mileage cap."
  [f c]
  (let [v (cond-> []
            (not= (:fare/origin f) (:comp/origin c))            (conj :market-origin-mismatch)
            (not= (:fare/destination f) (:comp/destination c))  (conj :market-destination-mismatch)

            (not (every? (:fare/carriers f) (:comp/carriers c)))
            (conj :carrier-not-permitted)

            (some #(and (:leg/classes %)
                        (not (pos? (get (:leg/classes %) (:fare/class f) 0))))
                  (:comp/legs c))
            (conj :class-not-available)

            (and (:fare/routing f)
                 (not (subsequence? (:comp/intermediate c) (:fare/routing f))))
            (conj :routing-not-permitted)

            (and (:fare/mpm f) (nil? (:comp/miles c)))          (conj :mileage-unverifiable)
            (and (:fare/mpm f) (:comp/miles c)
                 (> (:comp/miles c) (:fare/mpm f)))             (conj :exceeds-maximum-permitted-mileage))]
    {:fare/ok? (empty? v) :fare/violations v}))

(defn component-amount
  "The fare amount for `c` under `f`, in minor units of `currency`.

  A fare filed in `currency` is used as filed. A fare filed in NUC is
  converted at `roe`. A fare filed in some OTHER currency is not
  convertible here and yields nil — cross-currency conversion without a
  stated rate is exactly the kind of silent guess this library refuses.
  A `:round-trip` fare contributes half, truncated."
  [f _c {:keys [currency roe]}]
  (let [raw (cond
              (and (:fare/amount f) (= currency (:fare/currency f))) (:fare/amount f)
              (:fare/amount-nuc f)                                   (nuc->minor (:fare/amount-nuc f) roe)
              :else nil)]
    (when raw
      (if (= :round-trip (:fare/direction f)) (quot raw 2) raw))))

(defn price-component
  "Price `c` with `f`: check that the fare structurally fits, that its
  rules are satisfied under `ctx`, and compute the amount.

  Returns `{:pc/component c :pc/fare f :pc/amount n :pc/ok? bool
            :pc/violations [kw ..]}`. `:pc/amount` is nil when the fare is
  not applicable or not convertible — never 0, because a zero is a price
  and a nil is a refusal to state one."
  [f c {:keys [ctx] :as opts}]
  (let [structural (fare-matches-component? f c)
        rulewise (fare-applies? f (or ctx {}))
        amount (component-amount f c opts)
        v (cond-> (into (:fare/violations structural) (:fare/violations rulewise))
            (nil? amount) (conj :not-priceable-in-requested-currency))]
    {:pc/component  c
     :pc/fare       f
     :pc/amount     (when (empty? v) amount)
     :pc/ok?        (empty? v)
     :pc/violations (vec (distinct v))}))

;; ---------------------------------------------------------------------------
;; Surcharges and taxes
;; ---------------------------------------------------------------------------

(defn surcharge
  "A carrier-imposed surcharge (YQ/YR and the like), in minor units.
  `per` is `:itinerary`, `:component` or `:segment`.

  Taken as caller-supplied data rather than derived: ATPCO category 12 is
  not implemented (ns docstring)."
  [code amount & {:keys [per]}]
  (when (and (string? code) (integer? amount))
    {:sur/code code :sur/amount amount :sur/per (or per :itinerary)}))

(defn tax
  "A tax. `:flat` carries `:amount` in minor units; `:percent` carries
  `:bp` basis points applied to base + surcharges. `per` is
  `:itinerary`, `:component` or `:segment`."
  [code kind amount-or-bp & {:keys [per]}]
  (when (and (string? code) (contains? #{:flat :percent} kind) (integer? amount-or-bp))
    (cond-> {:tax/code code :tax/kind kind :tax/per (or per :itinerary)}
      (= :flat kind)    (assoc :tax/amount amount-or-bp)
      (= :percent kind) (assoc :tax/bp amount-or-bp))))

(defn- multiplier [per n-components n-segments]
  (case per
    :itinerary 1
    :component n-components
    :segment   n-segments
    1))

;; ---------------------------------------------------------------------------
;; Priced solutions
;; ---------------------------------------------------------------------------

(defn price
  "Total a set of priced components into one solution.

  Order of operations, stated because it changes the answer: base is the
  sum of the component fares; surcharges are added at their stated
  multiplicity; PERCENT taxes apply to base + surcharges; flat taxes are
  added last. A caller whose jurisdiction taxes a different base files
  the tax as `:flat` and computes it themselves.

  Returns nil when any component is not priceable — a partial total is
  worse than no total, because it looks like a fare.

  Returns
  `{:price/base n :price/surcharges n :price/tax n :price/total n
    :price/currency c :price/components [pc ..] :price/lines [..]}`,
  all integers in minor units."
  [priced-components {:keys [currency surcharges taxes]}]
  (when (and (seq priced-components) (every? :pc/ok? priced-components))
    (let [n-comp (count priced-components)
          n-seg (reduce + 0 (map #(count (get-in % [:pc/component :comp/legs])) priced-components))
          base (reduce + 0 (map :pc/amount priced-components))
          sur-lines (for [s surcharges
                          :when s
                          :let [amt (* (:sur/amount s) (multiplier (:sur/per s) n-comp n-seg))]]
                      {:line/kind :surcharge :line/code (:sur/code s) :line/amount amt})
          sur (reduce + 0 (map :line/amount sur-lines))
          taxable (+ base sur)
          tax-lines (for [t taxes
                          :when t
                          :let [mult (multiplier (:tax/per t) n-comp n-seg)
                                amt (if (= :percent (:tax/kind t))
                                      (* (apply-bp taxable (:tax/bp t)) mult)
                                      (* (:tax/amount t) mult))]]
                      {:line/kind :tax :line/code (:tax/code t) :line/amount amt})
          tax (reduce + 0 (map :line/amount tax-lines))]
      {:price/base       base
       :price/surcharges sur
       :price/tax        tax
       :price/total      (+ base sur tax)
       :price/currency   currency
       :price/components (vec priced-components)
       :price/lines      (vec (concat (map (fn [pc] {:line/kind :fare
                                                     :line/code (get-in pc [:pc/fare :fare/basis])
                                                     :line/amount (:pc/amount pc)})
                                           priced-components)
                                      sur-lines tax-lines))})))

;; ---------------------------------------------------------------------------
;; Fare construction — partitioning an itinerary into components
;; ---------------------------------------------------------------------------

(def max-legs
  "Ceiling on legs per itinerary in `search`. Partitioning n legs into
  contiguous components is 2^(n-1) ways, so this bounds the search at 128
  partitions per itinerary. Itineraries longer than this are REPORTED as
  skipped, never silently dropped."
  8)

(defn partitions-of
  "Every way of cutting `legs` into contiguous fare components, as a
  vector of vectors-of-vectors. 2^(n-1) of them."
  [legs]
  (let [legs (vec legs), n (count legs)]
    (cond
      (zero? n) []
      (= n 1) [[legs]]
      :else
      (vec (for [mask (range (bit-shift-left 1 (dec n)))]
             (loop [i 1, cur [(nth legs 0)], out []]
               (if (= i n)
                 (conj out cur)
                 (if (bit-test mask (dec i))
                   (recur (inc i) [(nth legs i)] (conj out cur))
                   (recur (inc i) (conj cur (nth legs i)) out)))))))))

(defn- cheapest-for-partition
  "Price one partition by taking the cheapest applicable fare for each
  component independently. Returns nil when any component has no
  applicable fare.

  Independent per-component minimisation is globally optimal for this
  partition ONLY because no rule implemented here couples one component
  to another. ATPCO category 10 (combinability) does exactly that
  coupling and is not implemented — see the ns docstring. If it is ever
  added, this function is where the assumption breaks."
  [parts fares opts]
  (let [priced (for [legs parts
                     :let [c (component legs)
                           best (->> fares
                                     (map #(price-component % c opts))
                                     (filter :pc/ok?)
                                     (sort-by :pc/amount)
                                     first)]]
                 best)]
    (when (every? some? priced) (vec priced))))

(defn search
  "Lowest-fare search: price every itinerary every legal way and return
  the cheapest solutions.

  `itineraries` are `kotoba.itinerary` maps (anything with `:itin/legs`);
  `fares` are `fare` maps. Options:

    :currency    -- required; the currency solutions are priced in
    :roe         -- integer rate of exchange for NUC-filed fares
    :ctx         -- rule facts, see `fare-applies?`
    :surcharges  -- [surcharge ..]
    :taxes       -- [tax ..]
    :max-solutions -- cap on returned solutions (default 20)

  Returns
  `{:search/solutions [{:price/.. :search/itinerary it} ..]
    :search/found n :search/truncated? bool
    :search/unpriceable n :search/skipped [..]}`
  sorted by total ascending, then by departure.

  `:search/skipped` names every itinerary that was NOT searched because
  it exceeded `max-legs`, and `:search/truncated?` says whether solutions
  were cut. Both exist for the same reason `kotoba.itinerary/build`
  reports its bounds: a shopping result that quietly omits candidates
  reads as \"this is the market\", and the omitted one may be the cheapest."
  [itineraries fares {:keys [max-solutions] :as opts}]
  (let [cap (or max-solutions 20)
        skipped (vec (for [it itineraries
                           :when (> (count (:itin/legs it)) max-legs)]
                       {:skip/itinerary it :skip/reason :too-many-legs-to-partition}))
        searchable (remove #(> (count (:itin/legs %)) max-legs) itineraries)
        solutions (for [it searchable
                        parts (partitions-of (:itin/legs it))
                        :let [pcs (cheapest-for-partition parts fares opts)
                              p (when pcs (price pcs opts))]
                        :when p]
                    (assoc p :search/itinerary it))
        ;; Several partitions of one itinerary can price identically; keep
        ;; the cheapest per itinerary rather than reporting the same journey
        ;; N times and crowding genuinely different options out of the cap.
        best-per-itin (->> solutions
                           (group-by #(mapv (juxt :leg/carrier :leg/number :leg/depart-min)
                                            (get-in % [:search/itinerary :itin/legs])))
                           vals
                           (map #(first (sort-by :price/total %))))
        sorted (vec (sort-by (juxt :price/total
                                   #(get-in % [:search/itinerary :itin/depart-min]))
                             best-per-itin))]
    {:search/solutions   (vec (take cap sorted))
     :search/found       (count sorted)
     :search/truncated?  (> (count sorted) cap)
     :search/unpriceable (- (count searchable) (count sorted))
     :search/skipped     skipped}))

(defn cheapest
  "The single cheapest solution from a `search` result, or nil."
  [result]
  (first (:search/solutions result)))

;; ---------------------------------------------------------------------------
;; Independent verification — the governor seam
;; ---------------------------------------------------------------------------

(defn price-matches-claim?
  "Recompute the total from `priced-components` and compare it to
  `claimed-total`.

  Verifies the arithmetic of a quoted itinerary without trusting the
  advisor that produced it. A nil or unpriceable set never matches,
  including against a claim of zero — otherwise a junk request would pass
  by claiming nothing was owed."
  [priced-components opts claimed-total]
  (let [p (price priced-components opts)]
    (boolean (and p (number? claimed-total) (= (:price/total p) claimed-total)))))

(defn no-cheaper-than?
  "Re-run the search over the same itineraries and fares and confirm that
  NOTHING prices below `claimed-total`.

  This is the check that makes a \"lowest fare\" claim verifiable. An
  advisor states a cheapest price; the governor re-derives every priced
  solution in the same universe and rejects the claim if any of them
  comes in lower. It is a statement about the fares that were NOT chosen,
  which is why restating the advisor's own answer could never verify it.

  Fails closed: an empty universe, an unpriceable one, or a non-numeric
  claim returns false. \"Nothing was cheaper\" and \"nothing could be
  priced\" are not the same fact, and only the first one may pass."
  [itineraries fares opts claimed-total]
  (let [r (search itineraries fares opts)
        c (cheapest r)]
    (boolean (and c (number? claimed-total) (>= claimed-total (:price/total c))))))

(defn cheapest-matches-claim?
  "Stricter than `no-cheaper-than?`: the recomputed cheapest total must
  EQUAL `claimed-total`.

  Use this when an advisor asserts a specific lowest price. Use
  `no-cheaper-than?` when it merely asserts that nothing beats what it
  offered — a distinction that matters, because an advisor quoting ABOVE
  the true minimum is overcharging even though nothing was cheaper than
  its own quote."
  [itineraries fares opts claimed-total]
  (let [c (cheapest (search itineraries fares opts))]
    (boolean (and c (number? claimed-total) (= claimed-total (:price/total c))))))

(defn describe-violation
  "Human-readable label for a violation keyword — for operator consoles
  and audit records, never for control flow."
  [k]
  (case k
    :market-origin-mismatch               "the fare is not filed from this component's origin"
    :market-destination-mismatch          "the fare is not filed to this component's destination"
    :carrier-not-permitted                "a leg is flown by a carrier the fare does not permit"
    :class-not-available                  "a leg shows no seat open in the fare's booking class"
    :routing-not-permitted                "the component routes via a point the fare does not permit"
    :mileage-unverifiable                 "the fare files a mileage cap and the component has no mileage"
    :exceeds-maximum-permitted-mileage    "the component exceeds the fare's maximum permitted mileage"
    :not-priceable-in-requested-currency  "the fare cannot be expressed in the requested currency"
    :before-season                        "travel commences before the fare's season"
    :after-season                         "travel commences after the fare's season"
    :blackout-date                        "travel commences on a blacked-out date"
    :day-of-week-not-permitted            "the fare does not permit travel commencing on this weekday"
    :inside-advance-purchase-window       "inside the fare's advance-purchase window"
    :below-minimum-stay                   "shorter than the fare's minimum stay"
    :above-maximum-stay                   "longer than the fare's maximum stay"
    :before-sale-window                   "before the fare's sale window opens"
    :after-sale-window                    "after the fare's sale window closes"
    :point-of-sale-not-permitted          "the fare is not filed for this point of sale"
    :travel-date-unverifiable             "the fare files a date rule and no travel date was supplied"
    :day-of-week-unverifiable             "the fare files a day rule and no weekday was supplied"
    :advance-purchase-unverifiable        "the fare files advance purchase and no sale interval was supplied"
    :stay-unverifiable                    "the fare files a stay rule and no stay length was supplied"
    :sale-date-unverifiable               "the fare files a sale window and no sale date was supplied"
    :point-of-sale-unverifiable           "the fare files a point of sale and none was supplied"
    (str/replace (name k) "-" " ")))
