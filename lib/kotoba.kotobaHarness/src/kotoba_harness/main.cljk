(ns kotoba-harness.main
  "CLI: nbb -cp src -m kotoba-harness.main <project.edn> <validate|known|wrong|jev> [out-dir]"
  (:require [clojure.edn :as edn] [clojure.string :as str]
            [kotoba-harness.catalog :as c] [kotoba-harness.search :as search]
            [kotoba-harness.jev :as jev] [kotoba-harness.verify :as v]))
(def fs (js/require "node:fs")) (def path (js/require "node:path")) (def crypto (js/require "node:crypto"))
(defn sha [s] (.digest (.update (.createHash crypto "sha256") s) "hex"))
(defn env [k] (let [x (aget (.-env js/process) k)] (when-not (str/blank? x) x)))

(defn config []
  {:kotoba (or (env "KOTOBA_BIN") "kotoba")
   :host-runner (.resolve path (or (env "KOTOBA_HARNESS_HOME") ".") "bin/run-wasm.mjs")
   :fuel 10000000})

(defn usage-sum [audit k] (reduce + 0 (keep #(get-in % [:usage k]) audit)))

(defn run-project! [project method out-root]
  (let [program (c/compile-program (:program project)) cfg (config)
        dir (.mkdtempSync fs (.join path out-root (str (:id project) "-" method "-")))
        started (.now js/performance) audit (atom []) attempts (atom [])
        verify! (fn [checked bodies]
                  (let [source (c/splice program (:baseline project) bodies)]
                    (js/Promise.resolve (assoc (v/verify! cfg project dir source checked) :source source))))]
    (-> (case method
          "jev" (search/run! program (jev/decide-fn (env "OPENROUTER_API_KEY"))
                             (fn [bodies] (verify! (keys bodies) bodies)) {:escalate? (not= "0" (env "KOTOBA_HARNESS_ESCALATE"))} audit attempts)
          ("known" "wrong") (let [bodies (get project (keyword method))]
                              (.then (verify! (keys (:checks project)) bodies) (fn [r] {:bodies bodies :verification r}))))
        (.then (fn [r] (assoc r :status (if (get-in r [:verification :passed]) "verified" "rejected"))))
        (.catch (fn [e] {:status "refused" :error (pr-str (or (dissoc (c/refusal e) :answer) (.-message e)))
                         :refused-answer (:answer (c/refusal e))}))
        (.then (fn [r]
                 (let [receipt (merge {:format "kotoba-harness.receipt/v1" :project (:id project) :title (:title project)
                                       :method method :escalate (not= "0" (env "KOTOBA_HARNESS_ESCALATE")) :date (.toISOString (js/Date.)) :cases (:cases project)
                                       :program-sha256 (sha (pr-str (:program project))) :check-sha256 (sha (:check project))
                                       :baseline-sha256 (sha (:baseline project))}
                                      (update r :verification dissoc :source)
                                      {:source (get-in r [:verification :source])
                                       :wall-seconds (/ (- (.now js/performance) started) 1000)
                                       :decisions @audit :attempts (mapv #(update % :verification dissoc :source) @attempts)
                                       :input-tokens (usage-sum @audit :input_tokens) :output-tokens (usage-sum @audit :output_tokens)
                                       :api-usd (usage-sum @audit :cost)})]
                   (.writeFileSync fs (.join path dir "receipt.json") (.stringify js/JSON (clj->js receipt) nil 2))
                   receipt))))))

(defn validate
  "Offline: program shape, catalog, stage dependencies, checks per function and
  baseline splicing of the known and wrong bodies. Needs neither kotoba nor a model."
  [project]
  (let [program (c/compile-program (:program project)) ids (set (map :id (:functions program)))]
    (when-not (= ids (set (keys (:checks project))) (set (keys (:known project))) (set (keys (:wrong project))))
      (c/refuse! :project-checks {:functions (sort ids)}))
    (doseq [which [:known :wrong]] (c/splice program (:baseline project) (get project which)))
    {:project (:id project) :status "valid" :functions (sort ids) :stages (:stage-order program)}))

(defn -main [project-file method & [out]]
  (let [project (edn/read-string (.readFileSync fs project-file "utf8"))
        out (or out "runs")]
    (if (= "validate" method)
      (try (println (.stringify js/JSON (clj->js (validate project))))
           (catch :default e (println (pr-str (or (c/refusal e) (.-message e)))) (set! (.-exitCode js/process) 1)))
    (do (.mkdirSync fs out #js {:recursive true})
    (-> (run-project! project method out)
        (.then (fn [r]
                 (println (.stringify js/JSON (clj->js (select-keys r [:project :method :status :wall-seconds :api-usd :input-tokens :output-tokens :error]))))
                 (println (.stringify js/JSON (clj->js {:decisions (count (filter :choice (:decisions r)))
                                                        :escalations (count (filter #(= :stop-escalation (:event %)) (:decisions r)))
                                                        :attempts (count (:attempts r)) :failures (get-in r [:verification :failures])})))
                 (when (:source r) (println (:source r)))
                 (when-not (= "verified" (:status r)) (set! (.-exitCode js/process) 1)))))))))
