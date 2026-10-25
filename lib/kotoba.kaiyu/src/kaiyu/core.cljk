(ns kaiyu.core
  "回遊 — how visitors move through a site, measured without identifying them.

  The rules a site needs in order to answer 『どの面が読まれ、次にどこへ行くか』
  from counters alone: a closed route vocabulary, coarse dwell buckets, an
  acquisition bucket derived from (never containing) the referrer, first-order
  transition edges, and the window arithmetic a report is read through.

  Everything here is pure and portable. Storage and transport are the host's:
  a Worker writes D1 rows, a Pages Function writes its own, a browser sends a
  beacon. What must NOT be the host's is the vocabulary — two sites that pick
  their own bucket boundaries produce numbers that look comparable and are not.

  ## The invariant this library exists to hold

  **No visitor identifier, ever.** Not a session id, not a cookie of its own,
  not a fingerprint, not a duration in seconds, not a path, not a query value.
  Only counts, dates, and names drawn from closed sets that live in this file.
  shinshi.club's `legal/privacy.md` §1.2 states publicly that the service holds
  『counts and dates only — no IP address, no device fingerprint, and no user
  identifier』; a library that made it easy to widen that would make the
  statement false. So the API takes vocabularies as arguments and refuses
  anything outside them, rather than offering a `sanitize` that lets values
  through in a modified form.

  What that costs, stated once so nobody rediscovers it as a surprise: paths of
  three or more hops, per-user funnels, causal attribution of an exit, and
  cohort-by-behaviour comparisons are all unavailable. They are not missing
  features. Buying them means changing what is stored about people, which is a
  privacy decision and not a library decision.

  ## Origin

  Extracted 2026-08-07 from two independent implementations that had converged
  on the same shape a day earlier (ADR-2608060900): `club-shinshi-app`'s
  `shinshi.worker.telemetry` (Worker + D1) and `net-babiniku`'s
  `babiniku.analytics` + `functions/api/track.js` (browser + Pages Function).
  Both had already duplicated the bucket boundaries, the whitelist-not-sanitize
  rule and the window arithmetic; the third consumer is what makes the
  duplication worth removing rather than worth watching."
  (:require [kotoba.lang.text :as str]))

;; ───────────────────────────── dwell ─────────────────────────────

(def dwell-buckets
  "Coarse buckets of ACTIVE seconds, in order. Ordered because a report renders
  them as a distribution and an alphabetical sort puts `10_29` before `lt10`.

  Coarse on purpose: on a low-traffic site an exact per-visit duration starts
  to behave like an identifier, so the duration is never stored — only which
  bucket it fell in. The boundaries are the ones shinshi.club and babiniku.net
  both shipped; changing them is not a code change, it is a decision to make
  historical rows incomparable with new ones."
  ["lt10" "10_29" "30_59" "60_179" "180_plus"])

(def dwell-bucket-set (set dwell-buckets))

(defn dwell-bucket
  "Active seconds → bucket name. `seconds` is what the visitor actually spent
  looking at the view: a host must not count time in a background tab (see
  `kaiyu.session`), or an abandoned tab reports a night's worth of attention."
  [seconds]
  (let [s (or seconds 0)]
    (cond
      (< s 10) "lt10"
      (< s 30) "10_29"
      (< s 60) "30_59"
      (< s 180) "60_179"
      :else "180_plus")))

(defn valid-dwell-bucket?
  [bucket]
  (contains? dwell-bucket-set bucket))

;; ─────────────────────────── acquisition ───────────────────────────

(def visit-sources
  "How a visit arrived. A closed set of five, and the NAME is all that is ever
  sent or stored — never the referrer, the campaign id or the search term it
  was derived from."
  #{"direct" "search" "social" "referral" "campaign"})

(def ^:private search-hosts ["google." "bing." "yahoo." "duckduckgo." "ecosia." "baidu."])

(def ^:private social-hosts ["bsky" "twitter.com" "x.com" "instagram." "tiktok."
                             "reddit." "youtube." "facebook." "t.co" "mastodon"
                             "misskey" "linkedin." "pinterest."])

(defn acquisition-source
  "Classify an arrival into one of `visit-sources`.

  `opts`:
    :campaign?    truthy when the URL carried a campaign marker (utm_source and
                  friends). Deliberately a BOOLEAN, not the value — passing the
                  value in would put a campaign id one typo away from the table.
    :referrer-host  lowercase hostname of the referrer, or nil for a direct hit.
    :own-hosts    hostnames belonging to this site, so an internal referrer is
                  not counted as an external referral.

  Campaign wins over everything: a visit that arrived through an ad is an ad
  visit even when the ad was posted on a social network, because the question
  the bucket answers is 『どこに払ったか』."
  [{:keys [campaign? referrer-host own-hosts]}]
  (let [host (some-> referrer-host str str/lower str/trim not-empty)
        has? (fn [fragments] (boolean (some #(str/includes? host %) fragments)))]
    (cond
      campaign? "campaign"
      (nil? host) "direct"
      (some #(str/includes? host (str/lower %)) (or own-hosts [])) "direct"
      (has? search-hosts) "search"
      (has? social-hosts) "social"
      :else "referral")))

;; ───────────────────────────── routes ─────────────────────────────

(def home-route
  "Every spelling of the landing page collapses here, so `/`, an empty string
  and `home` do not become three rows describing one page."
  "home")

(def other-route
  "Everything the vocabulary does not name. The counts stay correct; one bucket
  is just coarser than it could be."
  "other")

(defn normalize-route
  "Bound a client-supplied route name to `vocabulary` (a set of segment names).

  A whitelist, never a sanitizer. The distinction is the whole point: a
  sanitizer lets an unexpected value through in a modified form, which is how a
  scene id, a typed search term or a full path ends up in a table that promises
  counts and dates only. Anything not named becomes `other`.

  Drift is tolerable in exactly one direction. A route the app added but the
  vocabulary does not name reports as `other` — coarser, still correct. The
  reverse, accepting whatever the client sends, is what must never happen, and
  is why this takes the vocabulary as an argument instead of reading it from
  the payload."
  [vocabulary route]
  (let [s (some-> route str str/lower str/trim)]
    (cond
      (or (nil? s) (str/blank? s) (= s "/") (= s home-route)) home-route
      (contains? (set vocabulary) s) s
      :else other-route)))

;; ─────────────────────────── transitions ───────────────────────────

(defn transition
  "The edge to record for a move from `from` to `to`, or nil when the move is
  not a navigation worth counting.

  Both ends are normalized first — an edge is only as bounded as its weakest
  end. nil when the normalized ends are equal, which covers two cases that look
  different and are the same: re-entering the view already showing, and moving
  between two items inside one section (/video/scene/a → /video/scene/b). The
  reader did not leave the section, and section-to-itself edges are numerous
  enough to bury the edges that carry signal."
  [vocabulary from to]
  (let [f (normalize-route vocabulary from)
        t (normalize-route vocabulary to)]
    (when-not (= f t)
      {:from f :to t})))

;; ─────────────────────────── report window ───────────────────────────

(def max-window-days
  "Upper bound on a report window. Not a performance limit — a bound on how
  much history one query can be asked to summarise before the answer stops
  meaning anything to a human reading 『最近』."
  90)

(defn- parse-day
  "YYYY-MM-DD → epoch ms at UTC midnight, or nil."
  [day]
  (when (and (string? day) (re-matches #"\d{4}-\d{2}-\d{2}" day))
    #?(:clj (-> (java.time.LocalDate/parse day)
                (.atStartOfDay java.time.ZoneOffset/UTC)
                .toInstant
                .toEpochMilli)
       :cljs (let [ms (.getTime (js/Date. (str day "T00:00:00Z")))]
               (when-not (js/isNaN ms) ms)))))

(defn- format-day [epoch-ms]
  #?(:clj (-> (java.time.Instant/ofEpochMilli (long epoch-ms))
              (.atZone java.time.ZoneOffset/UTC)
              .toLocalDate
              str)
     :cljs (subs (.toISOString (js/Date. epoch-ms)) 0 10)))

(defn window
  "`{:days n :from \"YYYY-MM-DD\" :to \"YYYY-MM-DD\"}` for a trailing window
  ending on `end-day` (defaults to `today`).

  **Both ends are inclusive**: 7 days ending 2026-08-07 is 08-01..08-07, which
  is what a human means by 『今週』. Off by one here and every number on the
  page is quietly for a different week than its label.

  `days` is clamped into [1, max-window-days]; a negative, zero, missing or
  non-numeric value becomes the default rather than inverting the range."
  ([today] (window today {}))
  ([today {:keys [days end-day default-days]}]
   (let [default (or default-days 7)
         n (if (and (number? days) (not (#?(:clj Double/isNaN :cljs js/isNaN) (double days))))
             (-> (long days) (max 1) (min max-window-days))
             default)
         end (or (parse-day end-day) (parse-day today))
         end-str (format-day end)
         from (format-day (- end (* (dec n) 86400000)))]
     {:days n :from from :to end-str})))

(defn measurement-state
  "How to read an empty section, given the day collection for it began.

  - `:not-measured` — nothing was ever collected, or collection began after the
    window ended. An empty row set here means the question was never asked.
  - `:partial` — collection began inside the window, so the section describes
    part of it.
  - `:measured` — collection covers the whole window; empty means empty.

  This exists because `collected-since: null` rendered next to a zero reads as
  『誰も来ていない』 when it often means 『まだ測っていない』 — and, as
  ADR-2608060900 records, once meant 『読めていない』. A report that cannot
  distinguish these is not a report."
  [{:keys [from to]} collected-since]
  (cond
    (nil? collected-since) :not-measured
    (nil? (parse-day collected-since)) :not-measured
    (> (parse-day collected-since) (parse-day to)) :not-measured
    (> (parse-day collected-since) (parse-day from)) :partial
    :else :measured))

(defn trailing-window
  "The last `days` days of `win`, as a window.

  What a caller re-queries to find out whether a section is still collecting.
  `measurement-state` only knows where collection BEGAN; a beacon that wrote
  for two days and died returns the same `:partial` as one still writing, and
  a report cannot distinguish those from one response. Re-asking the same read
  face for its own trailing span is the cheapest thing that can: the host
  already filters by window, so no store has to learn a new query.

  Clamped to at least one day and never longer than `win` — a trailing span as
  long as the window answers nothing, because 「直近 7 日は 0 行」 and 「この
  window は 0 行」 are the same sentence."
  [{:keys [days to] :as win} trailing-days]
  (let [n (-> (if (number? trailing-days) (long trailing-days) 1)
              (max 1)
              (min (or days 1)))]
    (window to {:days n})))

(defn recent
  "`{:days n :rows k}` — how many rows the trailing `n` days of the window hold.

  Recorded rather than judged: whether 0 rows in the last three days means a
  dead beacon or a quiet site is not something counts can settle, and
  `kaiyu.diagnose` is where that question gets asked. Kept beside
  `:collected-since` because the two are the same kind of fact — the ends of
  the span the rows are true within — and a reader given only the near end
  completes the far one as 『今日まで』.

  **nil unless a count was actually read.** A probe that failed — the request
  threw, the host answered 502, the caller never made it — must not enter as
  zero rows, because zero rows is the whole evidence for 『収集が止まっている』
  and a failed probe would manufacture it. Returning nil makes no claim, and a
  section without `:recent` produces no staleness finding at all. This is the
  same failure ADR-2608136000 names: a check that could not run returning the
  value of a check that ran and found nothing."
  [{:keys [days]} row-count]
  (when (and (number? row-count) (not (neg? row-count)))
    {:days days :rows (long row-count)}))

(defn section
  "Wrap a section's rows with the boundary a reader needs to interpret them.

  `rows` is whatever the host's store returned; this does not touch it. What is
  added is `:collected-since` and the `:state` above, together — separately
  they are two numbers a caller has to remember to compare.

  The 4-arity carries `recent` (see above), the far end of that span. It is
  optional because only a caller that can re-query can produce it, and a
  caller that cannot must not be made to guess: absent, every reading behaves
  exactly as it did before this arity existed."
  ([win rows collected-since] (section win rows collected-since nil))
  ([win rows collected-since recent]
   (cond-> {:rows (vec rows)
            :collected-since collected-since
            :state (measurement-state win collected-since)}
     (some? recent) (assoc :recent recent))))
