(ns browser.compat.quickjs-constraint-invalid-range-check-smoke-test
  "Real page-script round-trip proof that `element.matches(':invalid')`/
  `':valid'` -- evaluated through the actual webapi shim string inside real
  QuickJS WASM, not a JVM stand-in -- now honors `type=\"number\"`/`\"range\"`
  `min`/`max` the same way `kotoba-lang/cssom`'s own `:invalid`/`:valid` CSS
  pseudo-class matching and `kotoba-lang/browser`'s real form-submission
  `validation-reason` already do.

  Before this change, `quickjs_wasm.cljc`'s embedded `__kotobaConstraintInvalid`
  had no `min`/`max` range check at all (only `required`/`minlength`/
  `maxlength`), even though the other two, independent copies of this same
  constraint-validation logic were already fixed for exactly this gap in an
  earlier cycle -- so a real page's own in-page script calling
  `input.matches(':invalid')` on an out-of-range `<input type=\"number\"
  min=\"1\" max=\"10\" value=\"15\">` reported `false` (VALID) even though the
  same input painted `:invalid` styling and would have blocked real form
  submission. A new `__kotobaParseNumber` helper plus a `rangeValue`/
  `rangeMin`/`rangeMax` check (mirroring `cssom.core/range-invalid?` and
  `document_input.cljc/validation-reason`'s own shape) closes this third
  copy's gap."
  (:require [cljs.test :refer [deftest is async]]
            [browser.compat.quickjs-runner :as quickjs-runner]
            [browser.session :as session]
            [kotoba.wasm.host :as host]))

(defn- dispose-engine!
  [session]
  (when-let [engine (get-in session [:browser.session/script-engine :script-engine/engine])]
    (when-let [dispose (:quickjs.engine/dispose engine)]
      (dispose engine))))

(defn- canned-fetch-fn
  [pages]
  (fn [{:keys [url]}]
    (if-let [html (get pages url)]
      {:status 200 :headers {} :body html}
      {:status 404 :headers {} :body (str "<main>not found: " url "</main>")})))

(defn- run-page-and-read-title!
  [html]
  (js/Promise.
   (fn [resolve reject]
     (let [url "https://app.example/constraint-invalid-range-check"
           fetch-fn (canned-fetch-fn {url html})
           h (host/recording-host)
           base-session (session/new-session
                         (quickjs-runner/quickjs-session-opts {:host h :fetch-fn fetch-fn}))]
       (-> (session/ensure-script-engine! base-session)
           (.then
            (fn [ready-session]
              (try
                (let [after (session/navigate! ready-session url)
                      title (get-in after [:browser.session/page :browser/title])]
                  (dispose-engine! ready-session)
                  (resolve title))
                (catch :default e
                  (dispose-engine! ready-session)
                  (reject e)))))
           (.catch (fn [err]
                     (dispose-engine! base-session)
                     (reject err))))))))

(deftest quickjs-real-matches-invalid-reports-range-overflow-test
  (async done
    (-> (run-page-and-read-title!
         (str "<main><input id=\"n\" type=\"number\" min=\"1\" max=\"10\" value=\"15\">"
              "<script>"
              "document.title = String(document.querySelector('#n').matches(':invalid'));"
              "</script></main>"))
        (.then (fn [title]
                 (println "quickjs real matches(':invalid') range-overflow (value=15, max=10) ->"
                          (pr-str title))
                 (is (= "true" title)
                     (str "expected a real element.matches(':invalid') to report true for an "
                          "out-of-range value=15 against max=10, got document.title = "
                          (pr-str title)))
                 (done)))
        (.catch (fn [err]
                  (is false (str "QuickJS WASM engine initialization / page load failed: "
                                 (or (.-message err) err)))
                  (done))))))

(deftest quickjs-real-matches-invalid-reports-range-underflow-test
  (async done
    (-> (run-page-and-read-title!
         (str "<main><input id=\"n\" type=\"number\" min=\"1\" max=\"10\" value=\"-3\">"
              "<script>"
              "document.title = String(document.querySelector('#n').matches(':invalid'));"
              "</script></main>"))
        (.then (fn [title]
                 (println "quickjs real matches(':invalid') range-underflow (value=-3, min=1) ->"
                          (pr-str title))
                 (is (= "true" title)
                     (str "expected a real element.matches(':invalid') to report true for an "
                          "out-of-range value=-3 against min=1, got document.title = "
                          (pr-str title)))
                 (done)))
        (.catch (fn [err]
                  (is false (str "QuickJS WASM engine initialization / page load failed: "
                                 (or (.-message err) err)))
                  (done))))))

(deftest quickjs-real-matches-valid-for-in-range-value-test
  (async done
    (-> (run-page-and-read-title!
         (str "<main><input id=\"n\" type=\"number\" min=\"1\" max=\"10\" value=\"5\">"
              "<script>"
              "document.title = String(document.querySelector('#n').matches(':valid'));"
              "</script></main>"))
        (.then (fn [title]
                 (println "quickjs real matches(':valid') in-range (value=5, [1,10]) ->" (pr-str title))
                 (is (= "true" title)
                     (str "expected a real element.matches(':valid') to report true for an "
                          "in-range value=5, got document.title = " (pr-str title)))
                 (done)))
        (.catch (fn [err]
                  (is false (str "QuickJS WASM engine initialization / page load failed: "
                                 (or (.-message err) err)))
                  (done))))))

(deftest quickjs-real-matches-valid-for-malformed-max-is-not-enforced-test
  ;; Regression guard: a non-numeric max must NOT be enforced (matches the
  ;; degrade-don't-guess convention `range-invalid?`/`validation-reason`
  ;; already document for a malformed min/max elsewhere).
  (async done
    (-> (run-page-and-read-title!
         (str "<main><input id=\"n\" type=\"number\" min=\"1\" max=\"abc\" value=\"9999\">"
              "<script>"
              "document.title = String(document.querySelector('#n').matches(':valid'));"
              "</script></main>"))
        (.then (fn [title]
                 (println "quickjs real matches(':valid') malformed max=\"abc\" ->" (pr-str title))
                 (is (= "true" title)
                     (str "expected a malformed max=\"abc\" to NOT be enforced (real "
                          "element.matches(':valid') true), got document.title = " (pr-str title)))
                 (done)))
        (.catch (fn [err]
                  (is false (str "QuickJS WASM engine initialization / page load failed: "
                                 (or (.-message err) err)))
                  (done))))))
