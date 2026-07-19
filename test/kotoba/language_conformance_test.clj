(ns kotoba.language-conformance-test
  (:require [clojure.edn :as edn]
            [clojure.java.io :as io]
            [clojure.test :refer [deftest is testing]]
            [kotoba.runtime :as runtime]
            [kotoba.wasm-exec :as wasm-exec]))

(defn- authority-resource [relative]
  (or (some-> (System/getenv "KOTOBA_LANG_AUTHORITY_ROOT")
              (io/file "lang" "conformance" relative)
              (#(when (.isFile %) %)))
      (io/resource (str "lang/conformance/" relative))
      (throw (ex-info "language conformance resource is missing" {:relative relative}))))

(defn- authority-language-resource [relative]
  (or (some-> (System/getenv "KOTOBA_LANG_AUTHORITY_ROOT")
              (io/file "lang" relative)
              (#(when (.isFile %) %)))
      (io/resource (str "lang/" relative))
      (throw (ex-info "language authority resource is missing" {:relative relative}))))

(defn- compile-source [source]
  (let [forms (runtime/read-forms source :kotoba)
        wasm (runtime/wasm-binary forms)]
    (is (:kotoba.wasm/ok? wasm) (str (:kotoba.wasm/problems wasm)))
    wasm))

(defn- compile-run-case [source function args]
  (let [entry (symbol function)
        renamed '__kotoba_conformance_entry
        forms (runtime/read-forms source :kotoba)
        renamed-forms (mapv (fn [form]
                              (if (and (seq? form) (= 'defn (first form))
                                       (= entry (second form)))
                                (cons 'defn (cons renamed (nnext form)))
                                form))
                            forms)
        wrapped (conj renamed-forms
                      (list 'defn 'main [] (apply list renamed args)))
        wasm (runtime/wasm-binary wrapped)]
    (is (:kotoba.wasm/ok? wasm) (str (:kotoba.wasm/problems wasm)))
    wasm))

(defn- manifest-cases [manifest]
  (cond
    (map? manifest) (:cases manifest)
    (vector? manifest)
    (some->> manifest
             (some :kotoba.lang.conformance/cases)
             edn/read-string)
    :else nil))

(defn- run-case [{:keys [id kind entry prelude function args expr expect source-paths]}]
  (when (and (contains? expect :kotoba) (not source-paths))
    (testing (name id)
      (let [source (case kind
                     :run (str (when prelude
                                 (str (slurp (authority-language-resource prelude)) "\n"))
                               (slurp (authority-resource entry)))
                     :compile-expr (str "(defn main [] " expr ")"))
            wasm (if (= kind :run)
                   (compile-run-case source (or function "main") (or args []))
                   (compile-source source))]
        (when (:kotoba.wasm/ok? wasm)
          (is (= (:kotoba expect)
                 (wasm-exec/run-main (:kotoba.wasm/binary wasm) []))))))))

(deftest authority-positive-cases-run-on-primary-wasm
  (let [manifest (edn/read-string (slurp (authority-resource "manifest.edn")))
        cases (manifest-cases manifest)]
    (is (seq cases) "authority manifest must expose non-vacuous conformance cases")
    (doseq [case cases
            :when (#{:run :compile-expr} (:kind case))]
      (run-case case))))
