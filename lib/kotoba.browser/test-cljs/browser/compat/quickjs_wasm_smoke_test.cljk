(ns browser.compat.quickjs-wasm-smoke-test
  "Proof-of-life smoke test for the QuickJS/QuickJS-NG WASM guest integration.

  This is the only test in the repo that actually loads the
  quickjs-emscripten-core + @jitl/quickjs-singlefile-cjs-release-sync WASM
  module and evaluates real JavaScript source through it. Everything else in
  `browser.compat.quickjs*` is exercised only against the `:invoke nil` JVM
  engine (see `browser.compat.quickjs-wasm`'s `:clj` branch), which never
  actually runs a line of JS. Run via `npm run test:cljs` (shadow-cljs
  `:node-test` target, executed under Node)."
  (:require [cljs.test :refer [deftest is async]]
            [browser.compat.quickjs-execution :as execution]
            [browser.compat.quickjs-wasm :as quickjs-wasm]))

(deftest quickjs-real-js-evaluation-test
  (async done
    (-> (quickjs-wasm/engine!)
        (.then (fn [engine]
                 (try
                   (let [response (execution/invoke-engine
                                   engine
                                   {:quickjs/call :js/evaluate
                                    :source "2 + 2"
                                    :url "kotoba://quickjs/smoke.js"})]
                     (println "quickjs-wasm smoke: real JS eval of `2 + 2` ->"
                              (pr-str (:result response))
                              (str "(" (type (:result response)) ")"))
                     (is (nil? (:error response))
                         (str "expected no eval error, got: " (pr-str response)))
                     (is (= 4 (:result response))
                         (str "expected real JS evaluation of `2 + 2` to yield 4, got: "
                              (pr-str (:result response))))
                     (is (number? (:result response))
                         "result must be a real number, not a stub/placeholder"))
                   (finally
                     ((:quickjs.engine/dispose engine) engine)
                     (done)))))
        (.catch (fn [err]
                  (is false (str "QuickJS WASM engine initialization failed: "
                                 (or (.-message err) err)))
                  (done))))))

(deftest quickjs-context-reuse-test
  ;; The engine descriptor advertises `:quickjs.wasm/context :reusable` — a
  ;; single VM/runtime is meant to survive across multiple `:js/evaluate`
  ;; invocations (see `ensure-context!`/ `context-atom` in
  ;; `browser.compat.quickjs-wasm`). Verify that's really true: a global set
  ;; in one eval call must still be visible in the next.
  (async done
    (-> (quickjs-wasm/engine!)
        (.then (fn [engine]
                 (try
                   (let [first-response (execution/invoke-engine
                                         engine
                                         {:quickjs/call :js/evaluate
                                          :source "globalThis.__smokeCounter = 41; 'seeded'"
                                          :url "kotoba://quickjs/smoke-seed.js"})
                         second-response (execution/invoke-engine
                                          engine
                                          {:quickjs/call :js/evaluate
                                           :source "globalThis.__smokeCounter + 1"
                                           :url "kotoba://quickjs/smoke-read.js"})]
                     (is (nil? (:error first-response))
                         (str "seed eval failed: " (pr-str first-response)))
                     (is (nil? (:error second-response))
                         (str "reuse eval failed: " (pr-str second-response)))
                     (is (= 42 (:result second-response))
                         (str "expected context to persist `__smokeCounter` across calls, got: "
                              (pr-str second-response))))
                   (finally
                     ((:quickjs.engine/dispose engine) engine)
                     (done)))))
        (.catch (fn [err]
                  (is false (str "QuickJS WASM engine initialization failed: "
                                 (or (.-message err) err)))
                  (done))))))
