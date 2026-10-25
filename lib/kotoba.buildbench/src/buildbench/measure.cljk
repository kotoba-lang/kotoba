(ns buildbench.measure
  "Interleaved, budgeted, validated sampling.

  Three properties matter more than the sample count:

  1. **Interleaving.** Lanes rotate, so a host that gets busier partway
     through inflates every lane rather than the one that happened to run
     last. On a machine that is never fully quiet this is what keeps the
     *ratios* meaningful even when the absolute numbers are not.

  2. **Validation outside the timed region.** The artifact is checked after
     the clock stops, so checking never counts as build time — and a lane
     whose artifact does not answer correctly is reported as `:invalid`
     rather than as a fast build.

  3. **A budget that is recorded, not hidden.** A slow lane stops after its
     wall budget with however many samples it got. `n` is always reported,
     so `perfgate` can refuse it for `:insufficient-samples` instead of a
     thin lane quietly ranking against a thick one."
  (:require ["node:child_process" :as cp]
            ["node:fs" :as fs]
            ["node:os" :as os]
            ["node:path" :as path]
            [buildbench.host :as host]
            [buildbench.lanes :as lanes]
            [buildbench.workload :as workload]
            [clojure.string :as str]))

(defn- rm-rf [p] (fs/rmSync p #js {:recursive true :force true}))

(defn- run-once
  "One process-cold build. Returns {:ms .. :status .. :error ..}."
  [lane dir expected]
  (let [out (path/join dir (:output lane))
        _ (rm-rf out)
        [cmd argv] ((:argv lane) dir out)
        t0 (js/performance.now)
        r (cp/spawnSync cmd (clj->js argv) #js {:encoding "utf8" :cwd dir})
        ms (- (js/performance.now) t0)]
    (cond
      (not (zero? (or (.-status r) 1)))
      {:status :failed
       :error (str cmd " exited " (.-status r) ": "
                   (str/trim (subs (str (.-stderr r) (.-stdout r)) 0 400)))}

      :else
      (if-let [bad ((:validate lane) out dir expected)]
        {:status :invalid :error bad :ms ms}
        {:status :ok :ms ms
         :bytes (when-not (:output-dir? lane)
                  (try (.-size (fs/statSync out)) (catch :default _ nil)))}))))

(defn- warmup! [lane dir expected n]
  (dotimes [_ n] (run-once lane dir expected)))

(defn measure-scale
  "Measure every available lane at one workload size.

  `budget-ms` bounds each lane's total sampling time. `runs` is the target
  sample count; the recorded `n` is what was actually taken."
  [{:keys [k runs budget-ms warmups work-root lanes]}]
  (let [expected (workload/expected-answer k)
        dir (path/join work-root (str "k" k))]
    (rm-rf dir)
    (fs/mkdirSync dir #js {:recursive true})
    (doseq [[_ {:keys [filename source]}] workload/emitters]
      (fs/writeFileSync (path/join dir filename) (source k)))
    (let [source-lines (into {} (for [[lang {:keys [filename]}] workload/emitters]
                                  [lang (count (str/split-lines
                                                (fs/readFileSync (path/join dir filename) "utf8")))]))
          available (filterv :available? lanes)
          ;; warm each lane once so no lane pays a cold page-cache cost the
          ;; others do not; failures here are ignored on purpose, the real
          ;; run records them.
          _ (doseq [lane available] (warmup! lane dir expected warmups))
          state (atom (into {} (for [l available] [(:id l) {:samples [] :spent 0}])))
          deadline-hit (atom #{})]
      ;; rotating order: round r starts at lane r, so lane position varies.
      (doseq [r (range runs)]
        (let [n (count available)
              order (map #(nth available (mod (+ % r) n)) (range n))]
          (doseq [lane order]
            (let [st (get @state (:id lane))]
              (when (and (< (:spent st) budget-ms)
                         (not (contains? @deadline-hit (:id lane))))
                (let [res (run-once lane dir expected)]
                  (swap! state update (:id lane)
                         (fn [s]
                           (-> s
                               (update :samples conj res)
                               (update :spent + (or (:ms res) 0)))))
                  (when (>= (+ (:spent st) (or (:ms res) 0)) budget-ms)
                    (swap! deadline-hit conj (:id lane)))))))))
      {:k k
       :expectedAnswer expected
       :sourceLines source-lines
       :load1Before (host/load1)
       :lanes
       (into {}
             (for [lane lanes]
               [(:id lane)
                (if-not (:available? lane)
                  {:status "unavailable"
                   :reason (or (:probeError lane)
                               (str "no " (name (:id lane)) " toolchain on this host"))}
                  (let [rs (:samples (get @state (:id lane)))
                        oks (filterv #(= :ok (:status %)) rs)
                        bad (first (remove #(= :ok (:status %)) rs))]
                    (cond
                      (empty? rs)
                      {:status "not-run" :reason "budget exhausted before first sample"}

                      (seq bad)
                      {:status (name (:status bad))
                       :error (:error bad)
                       :samplesAttempted (count rs)
                       :note "reported as a failed lane, not as a fast build"}

                      :else
                      {:status "measured"
                       :n (count oks)
                       :requestedRuns runs
                       :budgetExhausted (contains? @deadline-hit (:id lane))
                       :samplesMilliseconds (mapv #(js/Number (.toFixed (:ms %) 3)) oks)
                       :artifactBytes (:bytes (first oks))})))]))
       :load1After (host/load1)})))
