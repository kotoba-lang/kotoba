(ns kotodama.verify.run-maturity
  "Execute maturity gates from verify/maturity.edn.

  By default this runs required and local GPU gates. Use --include-local-model
  to also run gemma4:e4b through the local Ollama adapter."
  (:require [clojure.edn :as edn]
            [clojure.java.io :as io]
            [clojure.pprint :as pprint]
            [clojure.string :as str]
            [kotodama.verify.maturity :as maturity]))

(defn- read-maturity []
  (edn/read-string (slurp (io/file "verify/maturity.edn"))))

(defn- shell-command [command]
  (let [os (System/getProperty "os.name")]
    (if (str/includes? (str/lower-case os) "windows")
      ["cmd.exe" "/c" command]
      ["sh" "-lc" command])))

(defn- gate-cwd [gate]
  (io/file (or (:cwd gate) ".")))

(defn- include-gate? [opts gate]
  (case (:kind gate)
    :required true
    :required-local-gpu (not (:skip-local-gpu opts))
    :required-local-model (:include-local-model opts)
    false))

(defn- parse-opts [args]
  {:include-local-model (some #{"--include-local-model"} args)
   :skip-local-gpu (some #{"--skip-local-gpu"} args)
   :write-report (some #{"--write-report"} args)})

(defn- tail-lines [lines n]
  (let [v (vec lines)
        c (count v)]
    (subvec v (max 0 (- c n)) c)))

(defn- read-process-output! [process lines]
  (future
    (with-open [reader (io/reader (.getInputStream process))]
      (doseq [line (line-seq reader)]
        (println line)
        (swap! lines conj line)))))

(defn- run-gate! [gate]
  (let [cwd (gate-cwd gate)
        command (:command gate)
        started (System/nanoTime)
        lines (atom [])
        process (-> (ProcessBuilder. ^java.util.List (shell-command command))
                    (.directory cwd)
                    (.redirectErrorStream true)
                    (.start))
        output-reader (read-process-output! process lines)
        exit (.waitFor process)
        _ @output-reader
        elapsed-ms (long (/ (- (System/nanoTime) started) 1000000))]
    (when-not (zero? exit)
      (throw (ex-info "maturity gate failed"
                      {:gate (:id gate)
                       :command command
                       :cwd (.getPath cwd)
                       :exit exit
                       :elapsed-ms elapsed-ms
                       :output-tail (tail-lines @lines 80)})))
    {:gate (:id gate)
     :elapsed-ms elapsed-ms
     :output-tail (tail-lines @lines 20)}))

(defn -main [& args]
  (let [opts (parse-opts args)
        spec (read-maturity)
        gates (filter #(include-gate? opts %) (:gates spec))
        started-at (java.time.Instant/now)
        results (atom [])]
    (maturity/-main)
    (doseq [gate gates]
      (println "running" (name (:id gate)) "::" (:command gate))
      (flush)
      (let [result (run-gate! gate)]
        (swap! results conj result)
        (prn result)))
    (let [report {:kotodama/maturity-run :ok
                  :kotodama/started-at (str started-at)
                  :kotodama/finished-at (str (java.time.Instant/now))
                  :kotodama/scope (:scope spec)
                  :kotodama/gates (mapv :id gates)
                  :kotodama/results @results
                  :kotodama/include-local-model? (boolean (:include-local-model opts))
                  :kotodama/known-gaps (mapv :id (:known-gaps spec))}]
      (when (:write-report opts)
        (.mkdirs (io/file "verify/out"))
        (spit (io/file "verify/out/maturity-last.edn")
              (with-out-str (pprint/pprint report))))
      (prn report)
      (shutdown-agents))))
