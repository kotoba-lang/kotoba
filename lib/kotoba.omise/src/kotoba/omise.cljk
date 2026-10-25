(ns kotoba.omise
  "Stores (お店), opening hours and pickup points — pure data contracts.

  A kotoba-lang capability library for the cloud-itonami-5320 (community
  last-mile courier) open business. No network, no I/O, no clock access —
  the caller always passes the day/time to check, so every function is a
  pure, deterministic contract. Models the records a merchant-facing
  courier operator keeps: store records, weekly opening-hours windows,
  open-at? checks, pickup points, and geo distance between two points.

  Portable (.cljc) across JVM / ClojureScript / SCI / GraalVM."
  (:require [kotoba.lang.text :as str]))

;; ---------------------------------------------------------------------------
;; Opening hours — weekly windows, pure time arithmetic (no clock)
;; ---------------------------------------------------------------------------

(def days
  "Weekday keywords accepted in an hours map."
  #{:mon :tue :wed :thu :fri :sat :sun})

(defn hhmm->minutes
  "\"HH:MM\" → minutes since midnight, or nil when malformed/out of range.

  **\"24:00\" is accepted and means 1440 (end of day).** Shops routinely write
  a midnight close as 24:00, and rejecting it made \"09:00–24:00\" —- an
  ordinary late-night closing time — impossible to express at all. Only
  \"24:00\" exactly is allowed at that hour; \"24:30\" is still malformed."
  [s]
  (when (string? s)
    (when-let [[_ h m] (re-matches #"(\d{2}):(\d{2})" s)]
      (let [h #?(:clj (Long/parseLong h) :cljs (js/parseInt h 10))
            m #?(:clj (Long/parseLong m) :cljs (js/parseInt m 10))]
        (when (or (and (<= 0 h 23) (<= 0 m 59))
                  (and (= 24 h) (zero? m)))
          (+ (* 60 h) m))))))

(defn hhmm-valid? [s] (some? (hhmm->minutes s)))

(defn- window-minutes
  "[open close] as minutes, or nil when either end is malformed."
  [w]
  (when (and (vector? w) (= 2 (count w)))
    (let [[o c] (map hhmm->minutes w)]
      (when (and o c) [o c]))))

(defn overnight-window?
  "Does this window run past midnight (open after close, e.g. 22:00–02:00)?"
  [w]
  (boolean (when-let [[o c] (window-minutes w)] (> o c))))

(defn window-valid?
  "A window is [\"HH:MM\" \"HH:MM\"].

  **open > close means the window runs past midnight** (22:00–02:00), which
  is how convenience stores, izakaya and late-night pharmacies actually
  trade. Requiring open < close made those shops unrepresentable — not
  merely awkward to express, but rejected by `store` outright.

  open must be a real time of day (24:00 cannot *open* anything) and close
  must be after 00:00. open = close is rejected: it reads as either a
  zero-length window or a 24-hour one, and guessing which would silently
  pick the wrong answer for someone."
  [w]
  (boolean
   (when-let [[o c] (window-minutes w)]
     (and (< o 1440) (pos? c) (not= o c)))))

(defn hours-valid?
  "An hours map is {day [[open close] ..]} — every key a weekday keyword,
  every value a vector of valid windows. An empty map (always closed) is
  valid."
  [hours]
  (and (map? hours)
       (every? days (keys hours))
       (every? (fn [ws] (and (vector? ws) (every? window-valid? ws)))
               (vals hours))))

;; ---------------------------------------------------------------------------
;; Store
;; ---------------------------------------------------------------------------

(defn geo-valid?
  "{:lat .. :lng ..} within WGS-84 ranges."
  [{:keys [lat lng] :as g}]
  (and (map? g) (number? lat) (number? lng)
       (<= -90.0 lat 90.0) (<= -180.0 lng 180.0)))

(defn store
  "Construct a store record. status is one of :active/:suspended/:closed.
  Returns nil when the status, hours or geo is malformed."
  [id name address & {:keys [geo hours jurisdiction pickup-ready? status]}]
  (let [st (or status :active)
        hrs (or hours {})]
    ;; **id が空でも通していた。** `validate-store` は同じ入力を :missing-id で
    ;; 弾くので、構築器と検証器が別々の答えを出していた —— 空 id の店が作れて
    ;; しまうと、pickup-point の :pickup/store が指す先が無い参照になる
    ;; （`pickup-point` は自分の store-id の空文字は拒否していたのに、店側は
    ;; 空を許していた）。
    (when (and (not (str/blank? (str id)))
               (contains? #{:active :suspended :closed} st)
               (hours-valid? hrs)
               (or (nil? geo) (geo-valid? geo)))
      {:omise/id            id
       :omise/name          name
       :omise/address       address
       :omise/geo           geo
       :omise/hours         hrs
       :omise/jurisdiction  jurisdiction
       :omise/pickup-ready? (boolean pickup-ready?)
       :omise/status        st})))

(defn active? [s] (= :active (:omise/status s)))

(def ^:private previous-day
  {:mon :sun :tue :mon :wed :tue :thu :wed :fri :thu :sat :fri :sun :sat})

(defn open-at?
  "Is the store's hours table open at `day` (weekday keyword) and `hhmm`?
  Pure — the caller supplies the moment; a store with no windows for the
  day (or an invalid time) is closed. Open is inclusive, close exclusive.

  **A window that runs past midnight keeps the store open into the next
  day.** A bar whose Friday window is 22:00–02:00 is open at Saturday
  01:00, so this checks the *previous* day's overnight windows as well as
  today's. Forgetting that half is the classic version of this bug: the
  hours table looks right, and the shop reads as closed exactly during the
  hours it is busiest."
  [store day hhmm]
  (boolean
   (when-let [t (hhmm->minutes hhmm)]
     (let [hours (:omise/hours store)
           today (get hours day)
           spilled (get hours (previous-day day))]
       (or
        ;; 当日の通常 window（open ≤ t < close）
        (some (fn [w] (when-let [[o c] (window-minutes w)]
                        (and (< o c) (<= o t) (< t c))))
              today)
        ;; 当日に開いて日を跨ぐ window の、当日側（open ≤ t < 24:00）
        (some (fn [w] (when-let [[o c] (window-minutes w)]
                        (and (> o c) (<= o t))))
              today)
        ;; 前日に開いて日を跨いだ window の、当日側（t < close）
        (some (fn [w] (when-let [[o c] (window-minutes w)]
                        (and (> o c) (< t c))))
              spilled))))))

(defn pickup-available?
  "Can a courier pick up at this store at `day`/`hhmm`? — the single
  question the courier governor asks: the store must be :active, flagged
  pickup-ready, and open at that moment."
  [store day hhmm]
  (and (active? store)
       (true? (:omise/pickup-ready? store))
       (open-at? store day hhmm)))

;; ---------------------------------------------------------------------------
;; Pickup point
;; ---------------------------------------------------------------------------

(defn pickup-point
  "Construct a pickup-point record attached to a store. Returns nil when
  either id is blank or the geo is malformed."
  [id store-id label & {:keys [geo]}]
  (when (and (string? id) (not (str/blank? id))
             (string? store-id) (not (str/blank? store-id))
             (or (nil? geo) (geo-valid? geo)))
    {:pickup/id    id
     :pickup/store store-id
     :pickup/label label
     :pickup/geo   geo}))

;; ---------------------------------------------------------------------------
;; Geo distance
;; ---------------------------------------------------------------------------

(defn- deg->rad [d] (* d (/ Math/PI 180.0)))

(defn distance-km
  "Haversine great-circle distance in km between two {:lat :lng} points,
  or nil when either point is malformed."
  [g1 g2]
  (when (and (geo-valid? g1) (geo-valid? g2))
    (let [r 6371.0088
          dlat (deg->rad (- (:lat g2) (:lat g1)))
          dlng (deg->rad (- (:lng g2) (:lng g1)))
          a (+ (* (Math/sin (/ dlat 2)) (Math/sin (/ dlat 2)))
               (* (Math/cos (deg->rad (:lat g1)))
                  (Math/cos (deg->rad (:lat g2)))
                  (Math/sin (/ dlng 2)) (Math/sin (/ dlng 2))))]
      (* 2 r (Math/atan2 (Math/sqrt a) (Math/sqrt (- 1.0 a)))))))

;; ---------------------------------------------------------------------------
;; Validation
;; ---------------------------------------------------------------------------

(defn validate-store
  "Return a validation result for a candidate store record."
  [s]
  (cond
    (not (map? s))                        {:omise/valid? false :omise/error :not-a-map}
    (str/blank? (str (:omise/id s)))      {:omise/valid? false :omise/error :missing-id}
    (not (hours-valid? (:omise/hours s))) {:omise/valid? false :omise/error :malformed-hours}
    (and (:omise/geo s)
         (not (geo-valid? (:omise/geo s)))) {:omise/valid? false :omise/error :malformed-geo}
    (not (contains? #{:active :suspended :closed} (:omise/status s)))
    {:omise/valid? false :omise/error :unknown-status}
    :else {:omise/valid? true}))
