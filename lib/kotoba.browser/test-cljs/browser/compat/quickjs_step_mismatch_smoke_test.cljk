(ns browser.compat.quickjs-step-mismatch-smoke-test
  "Real page-script round-trip proof that real HTML5 `step` attribute
  constraint validation (`stepMismatch`) -- previously an honest,
  documented scope-cut everywhere (`stepMismatch: false` hardcoded in
  quickjs_wasm.cljc's own `__kotobaValidityState`, no check at all in
  `cssom.core/constraint-invalid?` or `browser.document-input/
  validation-reason`) -- now blocks a real `<input type=\"number\"
  step=\"2\" value=\"3\">` from matching `:valid`/reporting
  `checkValidity() === true`, evaluated through the actual webapi shim
  string inside real QuickJS WASM, not a JVM stand-in."
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
     (let [url "https://app.example/step-mismatch"
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

(deftest quickjs-real-step-mismatch-reports-invalid-test
  (async done
    (-> (run-page-and-read-title!
         (str "<main><input id=\"n\" type=\"number\" step=\"2\" value=\"3\">"
              "<script>"
              "var n = document.querySelector('#n');"
              "document.title = n.matches(':invalid') + ':' + n.checkValidity() + ':' + n.validity.stepMismatch;"
              "</script></main>"))
        (.then (fn [title]
                 (println "quickjs real matches(':invalid')/checkValidity()/.validity.stepMismatch, step mismatch ->"
                          (pr-str title))
                 (is (= "true:false:true" title)
                     (str "expected a step-mismatched value to report :invalid=true, checkValidity()=false, "
                          "validity.stepMismatch=true, got " (pr-str title)))
                 (done)))
        (.catch (fn [err]
                  (is false (str "QuickJS WASM engine initialization / page load failed: "
                                 (or (.-message err) err)))
                  (done))))))

(deftest quickjs-real-step-match-reports-valid-test
  (async done
    (-> (run-page-and-read-title!
         (str "<main><input id=\"n\" type=\"number\" step=\"2\" value=\"4\">"
              "<script>"
              "document.title = String(document.querySelector('#n').matches(':valid'));"
              "</script></main>"))
        (.then (fn [title]
                 (println "quickjs real matches(':valid') step match ->" (pr-str title))
                 (is (= "true" title)
                     (str "expected a step-matching value to report :valid=true, got " (pr-str title)))
                 (done)))
        (.catch (fn [err]
                  (is false (str "QuickJS WASM engine initialization / page load failed: "
                                 (or (.-message err) err)))
                  (done))))))

(deftest quickjs-real-default-step-rejects-a-fractional-value-test
  ;; A genuinely common surprise, matching real browsers: with no step
  ;; attribute at all, the default step is 1, so a fractional value is
  ;; real HTML5 INVALID.
  (async done
    (-> (run-page-and-read-title!
         (str "<main><input id=\"n\" type=\"number\" value=\"3.5\">"
              "<script>"
              "document.title = String(document.querySelector('#n').matches(':invalid'));"
              "</script></main>"))
        (.then (fn [title]
                 (println "quickjs real matches(':invalid') default step, fractional value ->" (pr-str title))
                 (is (= "true" title)
                     (str "expected a fractional value with no step attribute to report :invalid=true "
                          "(default step is 1), got " (pr-str title)))
                 (done)))
        (.catch (fn [err]
                  (is false (str "QuickJS WASM engine initialization / page load failed: "
                                 (or (.-message err) err)))
                  (done))))))

(deftest quickjs-real-step-any-disables-the-check-test
  (async done
    (-> (run-page-and-read-title!
         (str "<main><input id=\"n\" type=\"number\" step=\"any\" value=\"3.5\">"
              "<script>"
              "document.title = String(document.querySelector('#n').matches(':valid'));"
              "</script></main>"))
        (.then (fn [title]
                 (println "quickjs real matches(':valid') step=any ->" (pr-str title))
                 (is (= "true" title)
                     (str "expected step=\"any\" to disable the step check entirely, got " (pr-str title)))
                 (done)))
        (.catch (fn [err]
                  (is false (str "QuickJS WASM engine initialization / page load failed: "
                                 (or (.-message err) err)))
                  (done))))))
