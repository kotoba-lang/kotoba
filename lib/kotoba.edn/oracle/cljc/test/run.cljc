(ns edn-oracle-run
  "Oracle case runner for the kotoba.lang.edn twin. See json-oracle-run
  for the output contract (one line per case plus a fixed-order summary;
  values print solely on failure).

  Usage (from the directory holding this file):
    bb -cp <oracle-src>:<this-dir> run.cljc
    nbb -cp <oracle-src>:<this-dir> run.cljc
    basilisp run -p <oracle-src> -p <this-dir> run.cljc"
  (:require [kotoba.lang.edn :as e]
            [edn-oracle-cases :as cases]
            [clojure.string :as str])
  #?(:lpy (:import sys)))

(defn- char-code [ch]
  #?(:lpy (ord (str ch))
     :clj (int (.charAt (str ch) 0))
     :cljs (.charCodeAt (str ch) 0)))

(defn- outcome [c]
  (try
    (let [got (case (:op c)
                :read-string (if (contains? c :opts)
                               (e/read-string (:opts c) (:in c))
                               (e/read-string (:in c)))
                :read-all (if (contains? c :opts)
                            (e/read-all (:opts c) (:in c))
                            (e/read-all (:in c)))
                :write-string (e/write-string (:in c))
                :escape-controls (e/escape-controls (:in c)))]
      (cond
        (:expect-codes c)
        (let [codes (mapv char-code (str got))]
          {:pass (= codes (:expect-codes c)) :got codes :want (:expect-codes c)})
        (contains? c :error)
        {:pass false :got got :want-error (:error c)}
        :else
        {:pass (= got (:expect c)) :got got :want (:expect c)}))
    (catch #?(:lpy python/Exception :clj Exception :cljs :default) e
      (if-let [want (:error c)]
        {:pass (str/includes? (str (ex-message e)) want)
         :got (str "ERROR: " (ex-message e)) :want-error want}
        {:pass false :got (str "ERROR: " (ex-message e)) :want (:expect c)}))))

(defn -main [& _]
  (let [all (concat cases/cases cases/must-fail-cases)
        results (mapv (fn [c]
                        (let [r (outcome c)
                              pass? (if (:must-fail c) (not (:pass r)) (:pass r))]
                          (assoc c :result (assoc r :pass pass?))))
                      all)
        fails (filterv (comp not :pass :result) results)]
    (doseq [r results]
      (println (str (:id r) (if (:pass (:result r)) " ok" " FAIL"))))
    (doseq [f fails]
      (println "GOT:" (pr-str (:got (:result f)))
               "WANT:" (pr-str (select-keys f [:expect :expect-codes :error]))))
    (println "cases:" (count results) "pass:" (- (count results) (count fails))
             "fail:" (mapv :id fails))
    (let [code (if (seq fails) 1 0)]
      #?(:lpy (.exit sys code)
         :clj (System/exit code)
         :cljs (.exit js/process code)))))

(-main)
