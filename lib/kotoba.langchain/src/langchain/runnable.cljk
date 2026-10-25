(ns langchain.runnable
  "LCEL-style Runnable abstraction in portable Clojure.

  Everything composable in langchain-clj is a Runnable: plain
  functions, maps (parallel), chat models, prompts, compiled graphs.
  In Clojure LCEL mostly collapses into function composition — this
  namespace adds the protocol so models/graphs can participate, plus
  the combinators (pipe, parallel, assign, branch, retry, fallbacks)
  and a simple pull-based `stream`.

  No threads, no core.async: WASM hosts are assumed single-threaded,
  so `parallel` is sequential execution with parallel *semantics*
  (independent branches over the same input).")

(defprotocol IRunnable
  (-invoke [this input opts]
    "Runs the runnable. opts is a map (e.g. {:config …}).")
  (-stream [this input opts]
    "Returns a (possibly lazy) sequence of chunks. Default: one chunk."))

(defn invoke
  ([r input] (invoke r input {}))
  ([r input opts] (-invoke r input opts)))

(defn stream
  ([r input] (stream r input {}))
  ([r input opts] (-stream r input opts)))

(defn batch
  ([r inputs] (batch r inputs {}))
  ([r inputs opts] (mapv #(-invoke r % opts) inputs)))

;; Plain functions and maps participate directly.
;;
;; Three branches because nbb/SCI cannot analyze cljs concrete map types
;; (cljs.core/PersistentArrayMap etc.) in extend-protocol, which made this
;; whole namespace -- and langchain.model on top of it -- unloadable under
;; nbb. The nbb branch extends Keyword plus :default with a manual
;; map/function dispatch instead; a `function` extension would be wrong
;; there because cljs maps are IFn and would dispatch to it. Record
;; implementations (RSequence etc.) still take precedence over :default.
;; Verified equivalent for the types the :clj/:cljs branches extend
;; (fn, keyword, array-map, hash-map). The :org.babashka/nbb feature must
;; stay listed before :cljs -- nbb sets both, first match wins.
#?(:org.babashka/nbb
   (extend-protocol IRunnable
     cljs.core/Keyword
     (-invoke [k input _opts] (get input k))
     (-stream [k input opts] [(-invoke k input opts)])
     :default
     (-invoke [x input opts]
       (if (map? x)
         (reduce-kv (fn [out k r] (assoc out k (-invoke r input opts))) {} x)
         (x input)))
     (-stream [x input opts] [(-invoke x input opts)]))

   :clj
   (extend-protocol IRunnable
     clojure.lang.Fn
     (-invoke [f input _opts] (f input))
     (-stream [f input opts] [(-invoke f input opts)])

     clojure.lang.Keyword
     (-invoke [k input _opts] (get input k))
     (-stream [k input opts] [(-invoke k input opts)])

     clojure.lang.IPersistentMap
     (-invoke [m input opts]
       (reduce-kv (fn [out k r] (assoc out k (-invoke r input opts))) {} m))
     (-stream [m input opts] [(-invoke m input opts)]))

   :cljs
   (extend-protocol IRunnable
     function
     (-invoke [f input _opts] (f input))
     (-stream [f input opts] [(-invoke f input opts)])

     cljs.core/Keyword
     (-invoke [k input _opts] (get input k))
     (-stream [k input opts] [(-invoke k input opts)])

     cljs.core/PersistentArrayMap
     (-invoke [m input opts]
       (reduce-kv (fn [out k r] (assoc out k (-invoke r input opts))) {} m))
     (-stream [m input opts] [(-invoke m input opts)])))

#?(:org.babashka/nbb nil ;; maps covered by the :default extension above
   :cljs
   (extend-protocol IRunnable
     cljs.core/PersistentHashMap
     (-invoke [m input opts]
       (reduce-kv (fn [out k r] (assoc out k (-invoke r input opts))) {} m))
     (-stream [m input opts] [(-invoke m input opts)])))

(defrecord RSequence [steps]
  IRunnable
  (-invoke [_ input opts]
    (reduce (fn [acc step] (-invoke step acc opts)) input steps))
  (-stream [this input opts]
    ;; stream the last step over the result of the prefix
    (let [prefix (butlast steps)
          last-step (last steps)
          mid (reduce (fn [acc step] (-invoke step acc opts)) input prefix)]
      (-stream last-step mid opts))))

(defn pipe
  "Sequential composition: ((pipe a b c) x) = (c (b (a x)))."
  [& steps]
  (->RSequence (vec steps)))

(defn parallel
  "Map of runnables run over the same input → map of results."
  [m]
  m)

(defn assign
  "Runs each runnable in m over the input map and merges the results in."
  [m]
  (fn [input]
    (merge input (invoke m input))))

(defn pick
  "Selects keys from a map output."
  [ks]
  (fn [input] (select-keys input ks)))

(defrecord RBranch [branches default]
  IRunnable
  (-invoke [_ input opts]
    (loop [bs branches]
      (if-let [[pred r] (first bs)]
        (if (pred input)
          (-invoke r input opts)
          (recur (rest bs)))
        (-invoke default input opts))))
  (-stream [this input opts] [(-invoke this input opts)]))

(defn branch
  "(branch [pred1 r1] [pred2 r2] default) — first matching predicate wins."
  [& args]
  (->RBranch (vec (butlast args)) (last args)))

(defrecord RRetry [r max-attempts retry?]
  IRunnable
  (-invoke [_ input opts]
    (loop [attempt 1]
      (let [result (try
                     {:ok (-invoke r input opts)}
                     (catch #?(:clj Exception :cljs :default) e
                       {:error e}))]
        (cond
          (contains? result :ok) (:ok result)
          (and (< attempt max-attempts) (retry? (:error result))) (recur (inc attempt))
          :else (throw (:error result))))))
  (-stream [this input opts] [(-invoke this input opts)]))

(defn with-retry
  "Retries on exception up to :max-attempts (default 3).
  :retry? predicate on the exception (default: always)."
  [r & [{:keys [max-attempts retry?] :or {max-attempts 3 retry? (constantly true)}}]]
  (->RRetry r max-attempts retry?))

(defrecord RFallbacks [r fallbacks]
  IRunnable
  (-invoke [_ input opts]
    (loop [candidates (cons r fallbacks)]
      (let [[c & more] candidates
            result (try {:ok (-invoke c input opts)}
                        (catch #?(:clj Exception :cljs :default) e
                          {:error e}))]
        (cond
          (contains? result :ok) (:ok result)
          (seq more) (recur more)
          :else (throw (:error result))))))
  (-stream [this input opts] [(-invoke this input opts)]))

(defn with-fallbacks
  "Tries r, then each fallback in order."
  [r & fallbacks]
  (->RFallbacks r (vec fallbacks)))
