(ns kotoba.backend-qualification-test
  (:require [clojure.edn :as edn]
            [clojure.java.io :as io]
            [clojure.test :refer [deftest is testing]]
            [kotoba.compiler.core :as compiler]
            [kotoba.compiler.ir :as compiler-ir]
            [kotoba.launcher :as launcher]
            [kotoba.qualification-reference-oracle :as oracle]
            [kotoba.runtime :as runtime]
            [kotoba.wasm-exec :as wasm-exec]))

(def qualification-path
  "../kotoba-lang/lang/qualification/q3-backend-parity.edn")
(def adversarial-path
  "../kotoba-lang/lang/qualification/q6-adversarial.edn")

(defn qualification []
  (edn/read-string (slurp (io/file qualification-path))))

(defn adversarial []
  (edn/read-string (slurp (io/file adversarial-path))))

(defn kotoba-result [source]
  (let [forms (runtime/read-forms source :kotoba)
        artifact (runtime/wasm-binary forms)]
    (when-not (:kotoba.wasm/ok? artifact)
      (throw (ex-info "kotoba reference backend rejected source"
                      {:problems (:kotoba.wasm/problems artifact)})))
    {:result (wasm-exec/run-main (:kotoba.wasm/binary artifact) [])
     :effects #{}}))

(defn compiler-result [source]
  (let [artifact (compiler/compile-source source :wasm32-kotoba-v1 {:allow #{}})]
    {:result (compiler-ir/execute (:kir artifact) 'main [])
     :effects (get-in artifact [:hir :effects])}))

(defn rejects? [f source]
  (try
    (f source)
    false
    (catch Exception _ true)))

(deftest q3-positive-result-and-effect-parity
  (doseq [{:keys [id source result effects]} (:positive (qualification))]
    (testing (name id)
      (let [reference (kotoba-result source)
            compiled (compiler-result source)]
        (is (= {:result result :effects effects} reference))
        (is (= reference compiled))))))

(deftest q3-negative-acceptance-parity
  (doseq [{:keys [id source]} (:negative (qualification))]
    (testing (name id)
      (is (rejects? kotoba-result source) "kotoba must fail closed")
      (is (rejects? compiler-result source) "compiler must fail closed"))))

(defn materialize-adversarial-source [case]
  (or (:source case)
      (str (:source-prefix case)
           (apply str (repeat (:repeat-count case) (:repeat case)))
           (:source-suffix case)
           (apply str (repeat (:repeat-count case) ")")))))

(deftest q6-historical-and-almost-valid-corpus-fails-closed
  (let [corpus (adversarial)]
    (doseq [case (concat (:historical-regressions corpus)
                         (:almost-valid corpus))]
      (testing (name (:id case))
        (let [source (materialize-adversarial-source case)]
          (is (rejects? kotoba-result source) "kotoba must reject adversarial input")
          (is (rejects? compiler-result source) "compiler must reject adversarial input"))))))

(deftest q6-repeated-compilation-is-byte-reproducible
  (doseq [{:keys [id source]} (:positive (qualification))]
    (testing (name id)
      (let [kotoba-a (runtime/wasm-binary (runtime/read-forms source :kotoba))
            kotoba-b (runtime/wasm-binary (runtime/read-forms source :kotoba))
            compiler-a (compiler/compile-source source :wasm32-kotoba-v1 {:allow #{}})
            compiler-b (compiler/compile-source source :wasm32-kotoba-v1 {:allow #{}})]
        (is (= (vec (:kotoba.wasm/binary kotoba-a))
               (vec (:kotoba.wasm/binary kotoba-b))))
        (is (= (vec (:bytes compiler-a)) (vec (:bytes compiler-b))))))))

(deftest q8-pure-domain-port-shadows-cljc-oracle-on-both-compilers
  (let [source (slurp "src/qualification_reference.kotoba")
        expected (oracle/bounded-risk-score 12 3)]
    (is (= 40 expected))
    (is (= expected (:result (kotoba-result source))))
    (is (= expected (:result (compiler-result source))))))

(deftest q8-capability-port-is-real-and-denial-prevents-the-effect
  (let [forms (runtime/read-file "src/q8_capability_port.kotoba" :kotoba)
        compile-policy {:kotoba.policy/capabilities #{:graph/kotoba}}
        checked (runtime/check (launcher/safe-analyzer-fact-classification)
                               {:source "q8-capability-port.kotoba"}
                               forms compile-policy)
        wasm (runtime/wasm-binary forms compile-policy)
        allowed-store (atom [])
        allowed (wasm-exec/instantiate
                 (:kotoba.wasm/binary wasm)
                 (wasm-exec/kgraph-host-functions allowed-store compile-policy)
                 compile-policy)
        denied-store (atom [])
        denied (wasm-exec/instantiate
                (:kotoba.wasm/binary wasm)
                (wasm-exec/kgraph-host-functions denied-store {}) {})]
    (is (:kotoba.runtime/ok? checked))
    (is (:kotoba.wasm/ok? wasm))
    (is (zero? (wasm-exec/call-main allowed)))
    (is (= [[1 :name "Aoi"]] @allowed-store))
    (is (thrown? Exception (wasm-exec/call-main denied)))
    (is (empty? @denied-store))))

(defn -main [& _]
  (let [{:keys [fail error] :as result}
        (clojure.test/run-tests 'kotoba.backend-qualification-test)]
    (println (pr-str (assoc result :qualification :q3)))
    (when (pos? (+ fail error))
      (throw (ex-info "Q3 backend qualification failed" result)))))
