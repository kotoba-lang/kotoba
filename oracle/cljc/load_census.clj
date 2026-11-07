;; Require each namespace named in a file and print one EDN row per namespace.
;; Usage: clojure.main oracle/cljc/load_census.clj TARGETS-FILE
;; A dated oracle measurement only. It is not a gate and never a fallback.
(require '[clojure.string :as str])

(defn- chain [^Throwable t]
  (take-while some? (iterate #(.getCause ^Throwable %) t)))

(defn- describe [^Throwable t]
  (let [causes (chain t)
        root ^Throwable (last causes)
        location (last (keep (fn [e]
                               (when (instance? clojure.lang.Compiler$CompilerException e)
                                 (str (.-source ^clojure.lang.Compiler$CompilerException e)
                                      ":" (.-line ^clojure.lang.Compiler$CompilerException e))))
                             causes))
        message (str (.getMessage root))]
    {:loc location
     :cls (.getName (class root))
     :msg (subs message 0 (min 160 (count message)))}))

(doseq [target (str/split-lines (slurp (first *command-line-args*)))]
  (let [result (future (try (require (symbol target)) :ok (catch Throwable t (describe t))))]
    (println (pr-str [target (deref result 60000 :timeout)]))
    (flush)))

(shutdown-agents)
(System/exit 0)
