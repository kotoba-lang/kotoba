(ns kotoba.live.beat
  "Beat grid — the master clock everything else syncs to.

  BPM -> seconds per beat -> bar/phrase phase. Deterministic so multiple
  clients can render the same show in lock-step from a shared `(bpm t0)`.
  No I/O — a grid is a plain map; [[tick]] is a pure function returning the
  advanced grid plus the events it crossed (functional analogue of the
  original mutable `BeatGrid::tick` + `drain_events`).

  A *phase* is a map:
  `{:time seconds :beat n :bar n :phrase n :beat-frac 0..1 :bar-frac 0..1}`.
  `:time` is wall-clock seconds since show start (`t0`). `:beat` increments by
  1 per quarter-note. `:bar` = `:beats-per-bar` beats (4 by default).
  `:phrase` = `:bars-per-phrase` bars (8 by default — Western pop / J-pop song
  convention, drop on phrase 0).

  A *beat event* is `{:type (:eighth :beat :bar :phrase) :time seconds ...}`
  with an index key matching the type (`:eighth-index` / `:beat-index` /
  `:bar-index` / `:phrase-index`)."
  (:require [kotoba.live.mathx :as mathx]))

(defn beat-seconds
  "Seconds per beat at `bpm`."
  [bpm]
  (/ 60.0 bpm))

(defn phase-at
  "The full phase (`:time :beat :bar :phrase :beat-frac :bar-frac`) at time
  `t` seconds on `grid`."
  [{:keys [bpm beats-per-bar bars-per-phrase]} t]
  (let [spb (beat-seconds bpm)
        total-beats-f (max 0.0 (/ t spb))
        beat (long total-beats-f)
        beat-frac (- total-beats-f beat)
        bar (quot beat beats-per-bar)
        beat-in-bar (mod beat beats-per-bar)
        bar-frac (/ (+ beat-in-bar beat-frac) (double beats-per-bar))
        phrase (quot bar bars-per-phrase)]
    {:time t :beat beat :bar bar :phrase phrase :beat-frac beat-frac :bar-frac bar-frac}))

(defn new-grid
  "Construct a beat grid. `opts`: `:beats-per-bar` (default 4),
  `:bars-per-phrase` (default 8), `:swing` in [-0.5, 0.5] (default 0.0)."
  [bpm & {:keys [beats-per-bar bars-per-phrase swing]
          :or {beats-per-bar 4 bars-per-phrase 8 swing 0.0}}]
  {:pre [(pos? bpm) (pos? beats-per-bar) (pos? bars-per-phrase)]}
  (let [g {:bpm bpm
           :beats-per-bar beats-per-bar
           :bars-per-phrase bars-per-phrase
           :swing (max -0.5 (min 0.5 swing))
           :t 0.0}]
    (assoc g :last (phase-at g 0.0))))

(defn phase
  "The grid's current phase."
  [grid]
  (phase-at grid (:t grid)))

(defn- eighth-events [grid prev-time next-t]
  (let [spb (beat-seconds (:bpm grid))
        eighth (* spb 0.5)
        swing (:swing grid)]
    (loop [e-idx (inc (long (mathx/floor (/ prev-time eighth))))
           acc []]
      (let [base (* e-idx eighth)
            t-e (if (and (pos? e-idx) (odd? e-idx))
                  (+ base (* swing eighth))
                  base)]
        (cond
          (> t-e next-t) acc
          (<= t-e prev-time) (recur (inc e-idx) acc)
          :else (recur (inc e-idx) (conj acc {:type :eighth :time t-e :eighth-index e-idx})))))))

(defn tick
  "Advance `grid` by `dt` seconds (a no-op for `dt <= 0`). Returns
  `[grid' events]` — `events` are the grid lines crossed during this step, in
  order (eighths, then beats, then bars, then phrases)."
  [grid dt]
  (if (<= dt 0)
    [grid []]
    (let [prev (:last grid)
          next-t (+ (:t grid) dt)
          next (phase-at grid next-t)
          spb (beat-seconds (:bpm grid))
          beats-per-bar (:beats-per-bar grid)
          bars-per-phrase (:bars-per-phrase grid)
          eighths (eighth-events grid (:time prev) next-t)
          beat-events (when (> (:beat next) (:beat prev))
                        (for [b (range (inc (:beat prev)) (inc (:beat next)))]
                          {:type :beat :time (* b spb) :beat-index b}))
          bar-events (when (> (:bar next) (:bar prev))
                       (for [b (range (inc (:bar prev)) (inc (:bar next)))]
                         {:type :bar :time (* b beats-per-bar spb) :bar-index b}))
          phrase-events (when (> (:phrase next) (:phrase prev))
                          (for [p (range (inc (:phrase prev)) (inc (:phrase next)))]
                            {:type :phrase :time (* p bars-per-phrase beats-per-bar spb) :phrase-index p}))]
      [(assoc grid :t next-t :last next)
       (vec (concat eighths beat-events bar-events phrase-events))])))

(defn rewind
  "Reset `grid` to `t=0`. BPM/meter/swing retained."
  [grid]
  (assoc grid :t 0.0 :last (phase-at grid 0.0)))
