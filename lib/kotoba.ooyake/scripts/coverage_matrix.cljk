(ns coverage-matrix
  (:require [kotoba.lang.edn :as edn]
            [clojure.java.io :as io]
            [kotoba.lang.text :as str]
            [ooyake.coverage :as coverage]))

(def registry-dir
  (io/file "registry"))

(defn registry-files
  []
  (->> (file-seq registry-dir)
       (filter #(.isFile %))
       (filter #(re-matches #"gov-units.*\.edn" (.getName %)))
       (sort-by #(.getName %))))

(defn load-units
  []
  (->> (registry-files)
       (mapcat (fn [f]
                 (:units (edn/read-string (slurp f)))))
       (filter :gov.unit/id)
       (map (juxt :gov.unit/id identity))
       (into {})
       (vals)
       vec))

(defn bar
  [n total]
  (apply str (repeat (Math/round (double (* 28 (/ n (max 1 total)))))
                     "█")))

(defn -main
  [& _]
  (let [units (load-units)
        by-country (coverage/coverage-by-country units)
        countries (sort (keys by-country))
        total (count countries)
        cat-counts (coverage/category-coverage units)
        completeness (sort-by first > (map (fn [[iso cats]] [(count cats) iso]) by-country))
        avg (/ (reduce + (map first completeness))
               (double (max 1 total)))]
    (println (str "ooyake CLJ coverage matrix — " total " country units × "
                  (count (coverage/categories)) " functional categories"))
    (println "  source: ooyake.coverage CLJC classifier")
    (println "  counts stable id suffixes + explicit COFOG + conservative multi-portfolio name signals")
    (println)
    (println (str "  GLOBAL category coverage (countries with ≥1 such body / " total " countries):"))
    (doseq [[category n] (sort-by (comp - val) cat-counts)]
      (let [missing (->> countries
                         (remove #(contains? (get by-country %) category))
                         (take 6)
                         (map str/upper))]
        (println (format "      %-15s %3d  %-28s  gaps: %s"
                         (name category)
                         n
                         (bar n total)
                         (str/join " " missing)))))
    (println)
    (println (format "  per-country completeness: avg %.1f/%d categories"
                     avg
                     (count (coverage/categories))))
    (println (str "    most complete: "
                  (str/join ", " (map (fn [[n iso]] (str (str/upper iso) "(" n ")"))
                                      (take 8 completeness)))))
    (println (str "    least complete: "
                  (str/join ", " (map (fn [[n iso]] (str (str/upper iso) "(" n ")"))
                                      (take-last 8 completeness)))))))

(when (= *file* (System/getProperty "babashka.file"))
  (-main))
