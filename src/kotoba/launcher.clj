(ns kotoba.launcher
  "Rust-free launcher for the CLJC Kotoba CLI authority.

  This is intentionally small: command semantics live in `kotoba.cli` from
  kotoba-lang/kotoba-lang. Host-specific launchers call into that namespace and
  render the returned data."
  (:require [clojure.data.json :as json]
            [clojure.edn :as edn]
            [clojure.java.io :as io]
            [kotoba.cli :as cli]))

(defn result->exit [result]
  (if (:kotoba.cli/ok? result) 0 1))

(defn json-requested? [argv]
  (boolean (some #{"--json"} argv)))

(defn render-result
  ([result] (render-result result false))
  ([result json-output?]
   (if json-output?
     (json/write-str result :key-fn (fn [k]
                                      (if (keyword? k)
                                        (subs (str k) 1)
                                        (str k))))
     (pr-str result))))

(defn dispatch
  "Dispatch argv through the CLJC authority and return a result map."
  [argv]
  (let [contract (-> "lang/cli.edn"
                     io/resource
                     slurp
                     edn/read-string)]
    (cli/dispatch contract (vec argv))))

(defn -main [& argv]
  (let [result (dispatch argv)]
    (println (render-result result (json-requested? argv)))
    (System/exit (result->exit result))))
