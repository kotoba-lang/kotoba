(ns kotoba.crm.leadscore
  "Deterministic weighted-point marketing lead-scoring recompute — the
  same PURE 'recompute one side of an equation and compare' family as
  `kotoba.crm.revrec` (never trust a proposal's claimed figure, always
  recompute the ground truth and compare within tolerance), applied to
  lead score instead of recognized revenue. First consumer:
  `cloud-itonami-isic-6201` (marketing-automation SaaS platform actor,
  HubSpot Marketing Hub / Salesforce Marketing Cloud-class): its governor
  must recompute a lead's score from raw engagement history and compare
  it against any proposed score before allowing a stage transition
  (e.g. `:lead` -> `:mql`) to proceed on the strength of that score.

  Honest scope (R0, see `coverage` below): a FIXED weighted-point model
  only. Unlike revrec's ASC 606 / IFRS 15, there is no external
  standard-setter to cite for lead-scoring weights — `point-values`
  below is this namespace's OWN documented spec (reasonable, not
  authoritative). Per-event recency time-decay is supported but is
  opt-in and OFF by default; decay of a lead's score purely for
  inactivity, ML/predictive scoring, and per-account custom weight
  overrides are explicitly NOT modeled at all — see `coverage`.")

(defn- abs* [x] (if (neg? x) (- x) x))

(def point-values
  "Public, assertable point-value table — the only weights this recompute
  knows about. There is no external standard for lead-scoring weights
  (unlike revrec's ASC 606/IFRS 15 citations), so these are simply this
  namespace's own documented spec, chosen to be reasonable defaults:

    :email-open          1  — opened a marketing email
    :email-click         3  — clicked a link inside a marketing email
    :pricing-page-view   5  — viewed the pricing page
    :form-fill          10  — submitted any gated form (ebook, webinar, etc.)
    :demo-request       20  — requested a live product demo

  An engagement event is a map `{:kind <one of the keys above> :date
  {:year Y :month M :day D}}` (`:date` is required only when recency
  decay is requested — see `recompute-score`)."
  {:email-open         1
   :email-click        3
   :pricing-page-view  5
   :form-fill          10
   :demo-request       20})

(defn unrecognized-events
  "The subset of `engagement-history` whose `:kind` is not a key of
  `point-values` — i.e. the events `recompute-score` ignores (0 points
  each, per `coverage`). Exists so a caller/governor can be alerted to
  unknown event kinds explicitly, rather than the ignoring being silent
  end-to-end — this fleet's convention is 'never guess silently', and a
  0-point contribution for an unrecognized kind is not itself an
  authorized substitute for 'I don't know what this event is'."
  [engagement-history]
  (remove (comp point-values :kind) (or engagement-history [])))

(defn- day-number
  "Portable proleptic-Gregorian day number for a `{:year Y :month M :day
  D}` map — plain integer arithmetic (Fliegel & Van Flandern's
  algorithm), no platform date library, so this stays a reader-
  conditional-free .cljc exactly like revrec's date maps."
  [{:keys [year month day]}]
  (let [a (quot (- 14 month) 12)
        y (- (+ year 4800) a)
        m (- (+ month (* 12 a)) 3)]
    (+ day
       (quot (+ (* 153 m) 2) 5)
       (* 365 y)
       (quot y 4)
       (- (quot y 100))
       (quot y 400)
       -32045)))

(defn- days-between
  "Whole days from `from-date` to `to-date` (both `{:year :month :day}`
  maps), may be negative if `from-date` is after `to-date`."
  [from-date to-date]
  (- (day-number to-date) (day-number from-date)))

(defn- decay-multiplier
  "Exponential half-life recency multiplier: 1.0 at zero elapsed days,
  0.5 after `half-life-days`, etc. Elapsed days are clamped to >= 0 (an
  event dated after `as-of-date` counts as 'just happened', full
  weight) — this is an invented, documented decay model, not a citable
  standard, and is only ever applied when a caller opts in."
  [half-life-days days-elapsed]
  (let [days (max 0 days-elapsed)]
    #?(:clj  (Math/pow 0.5 (/ days (double half-life-days)))
       :cljs (js/Math.pow 0.5 (/ days half-life-days)))))

(defn- round-points [x]
  #?(:clj  (long (Math/round (double x)))
     :cljs (js/Math.round x)))

(defn recompute-score
  "The ground-truth lead score: the sum of `point-values` for every
  event in `engagement-history` whose `:kind` is recognized
  (unrecognized kinds contribute 0 points — see `unrecognized-events`
  to surface them), rounded to the nearest whole point. `nil` and an
  empty history both correctly recompute to `0` — a lead with no
  engagement genuinely has a zero score, this is not a guard case.

  Recency decay is OPTIONAL and OFF by default: pass a second map
  argument with both `:decay-half-life-days` and `:as-of-date` to apply
  exponential half-life decay (see `decay-multiplier`) to each event's
  weight based on how many days before `:as-of-date` it occurred. If
  `:decay-half-life-days` is supplied WITHOUT `:as-of-date` (or vice
  versa) this returns `nil` (no opinion) rather than silently picking a
  reference date or ignoring the request — the same own-precondition
  guard discipline as `revrec/recognized-revenue-to-date` guarding
  `term-months`."
  ([engagement-history] (recompute-score engagement-history {}))
  ([engagement-history {:keys [as-of-date decay-half-life-days]}]
   (if (not= (some? as-of-date) (some? decay-half-life-days))
     nil
     (round-points
      (reduce
       (fn [total {:keys [kind date]}]
         (let [weight (get point-values kind 0)
               mult   (if decay-half-life-days
                        (decay-multiplier decay-half-life-days
                                           (days-between date as-of-date))
                        1.0)]
           (+ total (* weight mult))))
       0.0
       (or engagement-history []))))))

(defn mismatch
  "Compares a PROPOSED lead score against the recomputed ground truth
  (undecayed — `mismatch` always uses the plain point sum, never the
  opt-in recency-decay variant, so a governor gets one unambiguous
  ground truth), within `tolerance-points` (defaults to `0`). Lead
  scores are integers, not currency: unlike revrec's cents-rounding
  0.01 default tolerance, there is no rounding step here that would
  justify any slack, so exact match is the correct default — any
  nonzero default tolerance would let a governor pass a materially
  wrong score through unchallenged. Returns nil when within tolerance,
  else a diagnostic map — never throws, so a governor can always turn
  this into a SOFT always-escalate gate rather than a hard crash."
  ([engagement-history proposed-score]
   (mismatch engagement-history proposed-score 0))
  ([engagement-history proposed-score tolerance-points]
   (let [truth (recompute-score engagement-history)]
     (when (> (abs* (- proposed-score truth)) tolerance-points)
       {:recomputed truth
        :proposed   proposed-score
        :delta      (- proposed-score truth)}))))

(defn coverage
  "Honest, machine-checkable report of what R0 actually covers."
  []
  {:model :fixed-weighted-point
   :point-values point-values
   :note (str "R0 scope: a FIXED weighted-point sum over recognized "
              "engagement-event kinds only (see point-values). "
              "Unrecognized event kinds are IGNORED (contribute 0 "
              "points, not an error) — use unrecognized-events to "
              "surface them instead of relying on silent 0-scoring. "
              "Per-event recency time-decay is supported but OFF by "
              "default (opt-in via :decay-half-life-days + :as-of-date "
              "on recompute-score); mismatch never applies decay. NOT "
              "modeled at all: ML/predictive scoring, per-account "
              "custom weight overrides, and decay of a lead's score "
              "purely for inactivity (a quiet lead's score never "
              "erodes on its own) — extend only by adding a genuinely "
              "new, documented scoring rule, never by guessing.")})
