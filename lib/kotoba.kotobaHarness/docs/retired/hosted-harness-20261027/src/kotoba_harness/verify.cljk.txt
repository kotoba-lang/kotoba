(ns kotoba-harness.verify
  "Verification uses kotoba only: `kotoba -M check` on the emitted module, then
  the module plus the project's fixed checks compiled to wasm32-browser and
  run through amu's instantiateKotoba. `main` returns the failure count."
  (:require [clojure.string :as str]))
(def fs (js/require "node:fs")) (def path (js/require "node:path")) (def cp (js/require "node:child_process"))

(defn- run [bin args]
  (let [r (.spawnSync cp bin (clj->js args) #js {:encoding "utf8" :timeout 120000})]
    {:status (.-status r) :out (str (.-stdout r)) :err (str (.-stderr r))}))

(defn verify!
  "SOURCE is the emitted module; CHECKED the function ids whose fixed checks run."
  [{:keys [kotoba host-runner fuel]} project dir source checked]
  (let [started (.now js/performance)
        module (.join path dir (:module-file project)) vfile (.join path dir "verify.kotoba")
        wasm (.join path dir "verify.wasm") policy (.join path dir "policy.edn")
        verify-src (str "(ns verify (:export [main]))\n" (str/join "\n" (rest (str/split source #"\n" -1))) "\n"
                        (:check project)
                        "(defn main [] :i64 (+ " (:preserved-check project) " "
                        (str/join " " (map #(get-in project [:checks %]) (sort checked))) "))\n")]
    (.mkdirSync fs (.dirname path module) #js {:recursive true})
    (.writeFileSync fs module source) (.writeFileSync fs vfile verify-src)
    (.writeFileSync fs policy (str "{:budgets {:fuel " fuel "}}"))
    (let [check (run kotoba ["-M" "check" module])
          compile (when (zero? (:status check)) (run kotoba ["-M" "compile" vfile "--target" "wasm32-browser" "--policy" policy "--output" wasm]))
          exec (when (and compile (zero? (:status compile))) (run (.-execPath js/process) [host-runner wasm]))
          result (when exec (try (js->clj (.parse js/JSON (last (str/split-lines (:out exec)))) :keywordize-keys true) (catch :default _ nil)))]
      {:passed (= "0" (:main result)) :checked (vec (sort checked))
       :kotoba-check (zero? (:status check)) :compiled (boolean (and compile (zero? (:status compile))))
       :failures (:main result) :trap (:trap result) :wasm-sha256 (:sha256 result)
       :verify-ms (- (.now js/performance) started)})))
