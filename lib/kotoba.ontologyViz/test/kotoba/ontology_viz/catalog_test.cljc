(ns kotoba.ontology-viz.catalog-test
  "Pure `.cljc` test verifying `kotoba.ontologyViz` registration in the
  repository's `lib/catalog.edn` without touching any `.cljk` test files."
  (:require [clojure.edn :as edn]
            [clojure.test :refer [deftest is testing]]
            #?(:cljs ["fs" :as fs])))

(defn- read-catalog []
  (let [candidates ["../../lib/catalog.edn" "lib/catalog.edn"]
        content (some (fn [p]
                        #?(:clj (let [f (java.io.File. ^String p)]
                                  (when (.exists f) (slurp f)))
                           :cljs (when (fs/existsSync p)
                                   (fs/readFileSync p "utf8"))))
                      candidates)]
    (when content
      (edn/read-string content))))

(deftest catalog-registration-test
  (let [catalog (read-catalog)]
    (testing "lib/catalog.edn exists and registers kotoba.ontologyViz cleanly"
      (is (map? catalog) "lib/catalog.edn must be readable")
      (is (= 1 (:kotoba.library-catalog/version catalog)))
      (let [pkgs (:packages catalog)
            entry (first (filter #(= "kotoba.ontologyViz" (:id %)) pkgs))
            ov-aliases (set (:aliases entry))
            other-aliases (set (mapcat :aliases (remove #(= "kotoba.ontologyViz" (:id %)) pkgs)))]
        (is (some? entry) "kotoba.ontologyViz must be present in lib/catalog.edn")
        (is (= :library (:kind entry)))
        (is (= "lib/kotoba.ontologyViz" (:path entry)))
        (is (= ["src"] (:source-paths entry)))
        (is (= #{"kotoba-lang/ontology-viz" "io.github.kotoba-lang/ontology-viz"} ov-aliases))
        (is (empty? (filter ov-aliases other-aliases))
            "kotoba.ontologyViz aliases must not collide with any other catalog package")
        (is (some #(= 'kotoba.ontology-viz %) (:entry-namespaces entry)))
        (is (some #(= 'kotoba.ontology-viz.dag-cbor %) (:entry-namespaces entry)))))))
