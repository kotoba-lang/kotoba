;; metrics.cljc — in-process metrics collector (cljc port of metrics.py, ADR clj/bb repo
;; rule). Counters / gauges / histograms in memory, exported in Prometheus text format.
;; Per ADR-2605215200 §monitoring.
;;
;; The python used a threading.Lock around three module dicts; here a single atom holding
;; {:counters {} :gauges {} :histograms {}} gives the same atomicity for free (`swap!` is
;; lock-free and consistent), so concurrent `inc!` from many threads loses no counts.
;;
;; Signature note (deviation from python, founder-sanctioned approximation): the python
;; `counter(n).inc()` / `gauge(n).set()` method style becomes `(inc! (counter n))` /
;; `(gauge-set! (gauge n))`, and the `with metrics.timer(n):` context-manager becomes the
;; `(with-timer n & body)` macro. Same names/semantics otherwise.
(ns etzhayyim-sdk.metrics
  (:require [kotoba.lang.text :as str]))

(defonce ^:private state (atom {:counters {} :gauges {} :histograms {}}))

;; ─── Handles (≈ python _Counter / _Gauge) ────────────────────────────

(defrecord Counter [name])
(defrecord Gauge   [name])

(defn counter ^Counter [name] (->Counter name))
(defn gauge   ^Gauge   [name] (->Gauge name))

;; ─── Mutators ────────────────────────────────────────────────────────

(defprotocol Incrementable
  (inc! [this] [this n] "Increment the counter/gauge by n (default 1 / 1.0)."))

(extend-protocol Incrementable
  Counter
  (inc!
    ([c] (inc! c 1))
    ([c n] (swap! state update-in [:counters (:name c)] (fnil + 0) n) nil))
  Gauge
  (inc!
    ([g] (inc! g 1.0))
    ([g n] (swap! state update-in [:gauges (:name g)] (fnil + 0.0) n) nil)))

(defn gauge-set!
  "Set a gauge to *value* (python gauge.set())."
  [^Gauge g value]
  (swap! state assoc-in [:gauges (:name g)] value)
  nil)

(defn observe
  "Add *value* to histogram *name*. Bounded to the last 1000 samples (python parity)."
  [name value]
  (swap! state update-in [:histograms name]
         (fn [vs] (let [vs (conj (or vs []) value)]
                    (if (> (count vs) 1000) (subvec vs (- (count vs) 1000)) vs))))
  nil)

(defn timer*
  "Time the 0-arg thunk *f*, record elapsed SECONDS as a histogram on *name*, return f's
  value. Functional core of the `with-timer` macro."
  [name f]
  (let [start (System/nanoTime)]
    (try (f)
         (finally (observe name (/ (- (System/nanoTime) start) 1e9))))))

(defmacro with-timer
  "Context-manager analogue: time the body, record as a histogram (seconds) on *name*."
  [name & body]
  `(timer* ~name (fn [] ~@body)))

(defn reset!
  "Clear all metrics (test-only, python metrics.reset())."
  []
  ;; fully-qualified: this fn shadows clojure.core/reset! in this ns.
  (clojure.core/reset! state {:counters {} :gauges {} :histograms {}})
  nil)

;; ─── Prometheus export ───────────────────────────────────────────────

(defn- metric-name [name] (str/replace name "." "_"))

(defn export-prometheus
  "Export current metrics in Prometheus text format (byte-shape parity with python:
  counters then gauges then histograms, each block name-sorted; percentile indices use the
  same integer math `len//2`, `int(len*0.95)`, `int(len*0.99)`). Always ends in a newline."
  []
  (let [{:keys [counters gauges histograms]} @state
        lines (transient [])]
    (doseq [[name value] (sort-by key counters)]
      (let [m (metric-name name)]
        (conj! lines (str "# TYPE " m " counter"))
        (conj! lines (str m " " value))))
    (doseq [[name value] (sort-by key gauges)]
      (let [m (metric-name name)]
        (conj! lines (str "# TYPE " m " gauge"))
        (conj! lines (str m " " value))))
    (doseq [[name values] (sort-by key histograms)]
      (let [m (metric-name name)
            cnt (count values)
            total (reduce + 0.0 values)]
        (conj! lines (str "# TYPE " m " histogram"))
        (conj! lines (str m "_count " cnt))
        (conj! lines (str m "_sum " total))
        (when (seq values)
          (let [sv (vec (sort values))
                n (count sv)]
            (conj! lines (str m "_p50 " (nth sv (quot n 2))))
            (conj! lines (str m "_p95 " (nth sv (int (* n 0.95)))))
            (conj! lines (str m "_p99 " (nth sv (int (* n 0.99)))))))))
    (str (str/join "\n" (persistent! lines)) "\n")))
