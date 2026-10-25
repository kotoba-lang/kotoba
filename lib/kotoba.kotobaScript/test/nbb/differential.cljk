(ns test.nbb.differential
  "Integration test: supply pinned kotoba-kir, kotoba-hir, kotoba-wasm,
  org-nist-sha2 and text source roots on the nbb classpath. No dependency skip."
  (:require [cljs.test :refer [deftest is run-tests]]
            [kotoba.script :as script]
            [kotoba.kir :as kir]
            [kotoba.wasm.core :as wasm]
            ["node:fs" :as fs]
            ["node:os" :as os]
            ["node:path" :as path]
            ["node:child_process" :as cp]))

(defn module-for [body]
  {:format :kotoba.kir/v3 :entry 'main :exports ['main] :effects #{}
   :functions [{:name 'main :params [] :body body}]})

(defn outcome [f]
  (try {:status "ok" :value (str (f))}
       (catch :default _ {:status "trap"})))

(defn execute-js [module fuel]
  (let [dir (fs/mkdtempSync (path/join (os/tmpdir) "kotoba-diff-"))
        file (path/join dir "fixture.mjs")]
    (try
      (fs/writeFileSync file
        (str (script/emit module {:fuel fuel})
             "\nlet out;try{out={status:'ok',value:String(instantiateKotoba().main())};}"
             "catch(e){out={status:'trap'};}console.log(JSON.stringify(out));"))
      (let [r (cp/spawnSync js/process.execPath #js [file]
                           #js {:encoding "utf8" :timeout 10000})]
        (when-not (= 0 (.-status r))
          (throw (ex-info "JS harness failed" {:stderr (.-stderr r) :status (.-status r)})))
        (js->clj (js/JSON.parse (.-stdout r)) :keywordize-keys true))
      (finally (fs/rmSync dir #js {:recursive true :force true})))))

(defn execute-wasm [module fuel]
  ;; Admission/validation/instantiation failures must fail the test, not pass
  ;; as a language trap. Only the guest invocation is inside outcome.
  (let [bytes (wasm/emit module :wasm32-kotoba-v1 {:fuel fuel})
        compiled (js/WebAssembly.Module. bytes)
        instance (js/WebAssembly.Instance. compiled #js {})]
    (outcome #(.main (.-exports instance)))))

(deftest scalar-and-fuel-three-way
  (doseq [[body expected] [['(+ 20 22) "42"]
                         [(list '+ (js/BigInt "9223372036854775807") 1)
                          "-9223372036854775808"]
                         ['(quot -7 3) "-2"]
                         ['(if (= 1 1) 42 (quot 1 0)) "42"]
                         ['(quot 1 0) nil]
                         [(list 'quot (js/BigInt "-9223372036854775808") -1) nil]]]
    (let [module (module-for body)
          want (if expected {:status "ok" :value expected} {:status "trap"})]
      (is (= want (outcome #(kir/execute module 'main [] {:fuel 8}))))
      (is (= want (execute-wasm module 8)))
      (is (= want (execute-js module 8)))))
  (let [module {:format :kotoba.kir/v3 :entry 'main :exports ['main] :effects #{}
                :functions [{:name 'step :params ['n]
                             :body '(if (= n 0) 42 (step (- n 1)))}
                            {:name 'main :params [] :body '(step 2)}]}]
    (doseq [[fuel want] [[3 {:status "trap"}] [4 {:status "ok" :value "42"}]]]
      (is (= want (outcome #(kir/execute module 'main [] {:fuel fuel}))))
      (is (= want (execute-wasm module fuel)))
      (is (= want (execute-js module fuel))))))

(defmethod cljs.test/report [:cljs.test/default :end-run-tests] [m]
  (when-not (cljs.test/successful? m) (set! (.-exitCode js/process) 1)))
(run-tests 'test.nbb.differential)
