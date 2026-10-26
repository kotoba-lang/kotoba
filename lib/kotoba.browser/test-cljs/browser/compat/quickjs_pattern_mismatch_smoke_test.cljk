(ns browser.compat.quickjs-pattern-mismatch-smoke-test
  "Real page-script round-trip proof that a real HTML5 `pattern` attribute
  -- previously an honest, documented scope-cut everywhere (`patternMismatch:
  false` hardcoded in quickjs_wasm.cljc's own `__kotobaValidityState`, no
  check at all in `__kotobaConstraintInvalid`, `cssom.core/constraint-
  invalid?`, or `browser.document-input/validation-reason`) -- now blocks
  a real, common author pattern like `<input pattern=\"[0-9]+\">` from
  matching `:valid`/reporting `checkValidity() === true` when its value
  doesn't fully match, evaluated through the actual webapi shim string
  inside real QuickJS WASM, not a JVM stand-in."
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
     (let [url "https://app.example/pattern-mismatch"
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

(deftest quickjs-real-matches-invalid-reports-pattern-mismatch-test
  (async done
    (-> (run-page-and-read-title!
         (str "<main><input id=\"n\" pattern=\"[0-9]+\" value=\"abc\">"
              "<script>"
              "var n = document.querySelector('#n');"
              "document.title = n.matches(':invalid') + ':' + n.checkValidity() + ':' + n.validity.patternMismatch;"
              "</script></main>"))
        (.then (fn [title]
                 (println "quickjs real matches(':invalid')/checkValidity()/.validity.patternMismatch, mismatched pattern ->"
                          (pr-str title))
                 (is (= "true:false:true" title)
                     (str "expected a pattern-mismatched value to report :invalid=true, "
                          "checkValidity()=false, validity.patternMismatch=true, got "
                          (pr-str title)))
                 (done)))
        (.catch (fn [err]
                  (is false (str "QuickJS WASM engine initialization / page load failed: "
                                 (or (.-message err) err)))
                  (done))))))

(deftest quickjs-real-matches-valid-for-a-value-matching-its-pattern-test
  (async done
    (-> (run-page-and-read-title!
         (str "<main><input id=\"n\" pattern=\"[0-9]+\" value=\"123\">"
              "<script>"
              "document.title = String(document.querySelector('#n').matches(':valid'));"
              "</script></main>"))
        (.then (fn [title]
                 (println "quickjs real matches(':valid') matching pattern ->" (pr-str title))
                 (is (= "true" title)
                     (str "expected a value matching its own pattern to report :valid=true, got "
                          (pr-str title)))
                 (done)))
        (.catch (fn [err]
                  (is false (str "QuickJS WASM engine initialization / page load failed: "
                                 (or (.-message err) err)))
                  (done))))))

(deftest quickjs-real-malformed-pattern-is-not-enforced-test
  ;; Regression guard: an illegal regex must NOT be enforced (degrades to
  ;; valid), matching this codebase's own degrade-don't-guess convention
  ;; for a malformed min/max/minlength/maxlength elsewhere -- not a crash.
  (async done
    (-> (run-page-and-read-title!
         (str "<main><input id=\"n\" pattern=\"[\" value=\"abc\">"
              "<script>"
              "document.title = String(document.querySelector('#n').matches(':valid'));"
              "</script></main>"))
        (.then (fn [title]
                 (println "quickjs real matches(':valid') malformed pattern=\"[\" ->" (pr-str title))
                 (is (= "true" title)
                     (str "expected a malformed pattern to NOT be enforced (real "
                          "element.matches(':valid') true), got document.title = " (pr-str title)))
                 (done)))
        (.catch (fn [err]
                  (is false (str "QuickJS WASM engine initialization / page load failed: "
                                 (or (.-message err) err)))
                  (done))))))

(deftest quickjs-real-pattern-on-a-textarea-has-no-effect-test
  ;; Real HTML5: `pattern` is only ever valid on text/search/url/tel/
  ;; email/password <input>s, never <textarea> -- confirmed this engine
  ;; doesn't misapply it there just because an untyped <textarea> also
  ;; resolves the same internal "text" type default an untyped <input>
  ;; does.
  (async done
    (-> (run-page-and-read-title!
         (str "<main><textarea id=\"n\" pattern=\"[0-9]+\">abc</textarea>"
              "<script>"
              "document.title = String(document.querySelector('#n').matches(':valid'));"
              "</script></main>"))
        (.then (fn [title]
                 (println "quickjs real matches(':valid') pattern on a textarea ->" (pr-str title))
                 (is (= "true" title)
                     (str "expected pattern on a <textarea> to have no effect at all, got "
                          (pr-str title)))
                 (done)))
        (.catch (fn [err]
                  (is false (str "QuickJS WASM engine initialization / page load failed: "
                                 (or (.-message err) err)))
                  (done))))))
