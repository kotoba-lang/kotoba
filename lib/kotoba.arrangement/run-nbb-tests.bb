#!/usr/bin/env kbb
;; Runs this repo's test suite through nbb (Node Babashka -- a SCI-interpreted
;; ClojureScript environment, no build step) as a genuine 3rd platform tier
;; alongside JVM (`kbb -M:test`) and self-hosted cljs (`npm run
;; test:cljs`). Auto-discovers every `*_test.cljc` under test/ (same
;; -test$-suffix convention shadow-cljs.edn's `:ns-regexp "-test$"` already
;; assumes) and resolves the classpath from `kbb -Spath`, filtered to
;; directories only (jars are JVM-only; nbb can't load them) -- the same
;; approach gen-shadow-cljs-edn.bb already uses for the cljs build, so nbb
;; tests against the exact pinned deps.edn dependencies too, not a
;; hand-duplicated list that can drift.
;;
;; Exit code is wired through cljs.test's :end-run-tests report hook (NOT a
;; naive "parse the printed summary text" heuristic) -- `nbb`'s own process
;; only exits non-zero if this namespace explicitly calls `js/process.exit`,
;; since a failed `is` assertion is just printed output, not a thrown
;; exception; without this hook every CI failure here would silently report
;; success.
(require '[babashka.fs :as fs]
         '[babashka.process :as p]
         '[clojure.java.shell :refer [sh]]
         '[clojure.string :as str])

(defn- classpath []
  (let [cp (-> (sh "kbb" "-Spath") :out str/trim)]
    (->> (str/split cp #":")
         (remove str/blank?)
         (filter #(.isDirectory (java.io.File. %)))
         (cons "test")
         (str/join ":"))))

(defn- path->ns [p]
  (-> (str p)
      (str/replace #"\\" "/")
      (str/replace #"^test/" "")
      (str/replace #"\.cljc?$" "")
      (str/replace "_" "-")
      (str/replace "/" ".")))

(defn- test-namespaces []
  (->> (fs/glob "test" "**/*_test.cljc")
       (map path->ns)
       sort))

(defn -main []
  (let [nss (test-namespaces)]
    (when (empty? nss)
      (println "run-nbb-tests: no *_test.cljc files found under test/")
      (System/exit 1))
    (let [entry-file "out-nbb-entry.cljs"
          requires (str/join " " (map #(str "[" % "]") nss))
          run-args (str/join " " (map #(str "'" %) nss))
          entry (format
                 "(ns nbb-test-entry (:require [cljs.test :as t] %s))
(defmethod t/report [:cljs.test/default :end-run-tests] [m]
  (js/process.exit (if (t/successful? m) 0 1)))
(t/run-tests %s)"
                 requires run-args)]
      (fs/create-dirs "out")
      (spit (str "out/" entry-file) entry)
      (println "nbb classpath:" (classpath))
      (println "test namespaces:" nss)
      (let [{:keys [exit]} @(p/process ["npx" "kbb" "--backend" "sci" "-cp" (str (classpath) ":out") (str "out/" entry-file)]
                                        {:inherit true})]
        (System/exit exit)))))

(-main)
