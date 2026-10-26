(ns browser.compat.quickjs-type-mismatch-smoke-test
  "Real page-script round-trip proof that real HTML5 `type=\"email\"`/
  `\"url\"` format checking (`typeMismatch`) -- previously an honest,
  documented scope-cut everywhere (`typeMismatch: false` hardcoded in
  quickjs_wasm.cljc's own `__kotobaValidityState`, no check at all in
  `__kotobaConstraintInvalid`, `cssom.core/constraint-invalid?`, or
  `browser.document-input/validation-reason`) -- now blocks a real,
  malformed `<input type=\"email\">`/`type=\"url\">` value from matching
  `:valid`/reporting `checkValidity() === true`, evaluated through the
  actual webapi shim string inside real QuickJS WASM, not a JVM
  stand-in."
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
     (let [url "https://app.example/type-mismatch"
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

(deftest quickjs-real-malformed-email-reports-type-mismatch-test
  (async done
    (-> (run-page-and-read-title!
         (str "<main><input id=\"n\" type=\"email\" value=\"not-an-email\">"
              "<script>"
              "var n = document.querySelector('#n');"
              "document.title = n.matches(':invalid') + ':' + n.checkValidity() + ':' + n.validity.typeMismatch;"
              "</script></main>"))
        (.then (fn [title]
                 (println "quickjs real matches(':invalid')/checkValidity()/.validity.typeMismatch, malformed email ->"
                          (pr-str title))
                 (is (= "true:false:true" title)
                     (str "expected a malformed email to report :invalid=true, checkValidity()=false, "
                          "validity.typeMismatch=true, got " (pr-str title)))
                 (done)))
        (.catch (fn [err]
                  (is false (str "QuickJS WASM engine initialization / page load failed: "
                                 (or (.-message err) err)))
                  (done))))))

(deftest quickjs-real-well-formed-email-reports-valid-test
  (async done
    (-> (run-page-and-read-title!
         (str "<main><input id=\"n\" type=\"email\" value=\"user@example.com\">"
              "<script>"
              "document.title = String(document.querySelector('#n').matches(':valid'));"
              "</script></main>"))
        (.then (fn [title]
                 (println "quickjs real matches(':valid') well-formed email ->" (pr-str title))
                 (is (= "true" title)
                     (str "expected a well-formed email to report :valid=true, got " (pr-str title)))
                 (done)))
        (.catch (fn [err]
                  (is false (str "QuickJS WASM engine initialization / page load failed: "
                                 (or (.-message err) err)))
                  (done))))))

(deftest quickjs-real-malformed-url-reports-type-mismatch-test
  (async done
    (-> (run-page-and-read-title!
         (str "<main><input id=\"n\" type=\"url\" value=\"not a url\">"
              "<script>"
              "document.title = String(document.querySelector('#n').matches(':invalid'));"
              "</script></main>"))
        (.then (fn [title]
                 (println "quickjs real matches(':invalid') malformed url ->" (pr-str title))
                 (is (= "true" title)
                     (str "expected a malformed url to report :invalid=true, got " (pr-str title)))
                 (done)))
        (.catch (fn [err]
                  (is false (str "QuickJS WASM engine initialization / page load failed: "
                                 (or (.-message err) err)))
                  (done))))))

(deftest quickjs-real-blank-email-does-not-report-type-mismatch-test
  ;; typeMismatch is not required's concern -- a blank, non-required
  ;; email input must still report :valid.
  (async done
    (-> (run-page-and-read-title!
         (str "<main><input id=\"n\" type=\"email\" value=\"\">"
              "<script>"
              "document.title = String(document.querySelector('#n').matches(':valid'));"
              "</script></main>"))
        (.then (fn [title]
                 (println "quickjs real matches(':valid') blank email ->" (pr-str title))
                 (is (= "true" title)
                     (str "expected a blank email input to report :valid=true, got " (pr-str title)))
                 (done)))
        (.catch (fn [err]
                  (is false (str "QuickJS WASM engine initialization / page load failed: "
                                 (or (.-message err) err)))
                  (done))))))
