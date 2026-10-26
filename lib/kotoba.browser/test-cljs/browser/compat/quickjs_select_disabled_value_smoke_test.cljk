(ns browser.compat.quickjs-select-disabled-value-smoke-test
  "Real page-script round-trip proof that a `<select>`'s `.value` now
   correctly reflects an explicitly `selected` option even when that
   option is `disabled` -- previously `__kotobaSelectValue` only
   returned early for a selected candidate when it was ALSO enabled, so
   a select whose ONLY selected option was disabled (the extremely
   common `<option value=\"x\" disabled selected>` placeholder-with-a-
   real-value idiom) fell through to the empty-string default instead
   of that option's own value. Confirmed via a temporary CLJS/QuickJS
   smoke test before touching source, and cross-checked against REAL
   Chrome directly (`document.createElement('select')` + `.innerHTML` +
   `.value`) for every scenario below, since a naive 'disabled never
   matters for selectedness' read of the spec is WRONG: the no-explicit-
   selected DEFAULT correctly skips disabled options (unaffected by this
   fix, already correct before it), and an all-disabled select with
   nothing explicitly selected correctly selects nothing at all."
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
     (let [url "https://app.example/select-disabled-value-round-trip"
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

(deftest quickjs-real-select-value-reflects-a-disabled-but-explicitly-selected-option-test
  (async done
    (-> (run-page-and-read-title!
         (str "<main><select id=\"s\">"
              "<option value=\"x\" disabled selected>X</option>"
              "<option value=\"y\">Y</option>"
              "</select></main>"
              "<script>"
              "document.title = document.getElementById('s').value;"
              "</script>"))
        (.then (fn [title]
                 (println "quickjs real select.value (disabled+selected) ->" (pr-str title))
                 (is (= "x" title)
                     (str "expected the disabled-but-explicitly-selected option's own value, "
                          "matching real Chrome, got document.title = " (pr-str title)))
                 (done)))
        (.catch (fn [err]
                  (is false (str "QuickJS WASM engine initialization / page load failed: "
                                 (or (.-message err) err)))
                  (done))))))

(deftest quickjs-real-select-value-with-no-explicit-selection-skips-a-disabled-first-option-test
  (async done
    (-> (run-page-and-read-title!
         (str "<main><select id=\"s\">"
              "<option value=\"x\" disabled>X</option>"
              "<option value=\"y\">Y</option>"
              "</select></main>"
              "<script>"
              "document.title = document.getElementById('s').value;"
              "</script>"))
        (.then (fn [title]
                 (println "quickjs real select.value (no explicit, disabled first) ->" (pr-str title))
                 (is (= "y" title)
                     (str "expected the default selection to skip the disabled first option and "
                          "land on the next, enabled one, matching real Chrome, got "
                          "document.title = " (pr-str title)))
                 (done)))
        (.catch (fn [err]
                  (is false (str "QuickJS WASM engine initialization / page load failed: "
                                 (or (.-message err) err)))
                  (done))))))

(deftest quickjs-real-select-value-with-every-option-disabled-selects-nothing-test
  (async done
    (-> (run-page-and-read-title!
         (str "<main><select id=\"s\">"
              "<option value=\"x\" disabled>X</option>"
              "<option value=\"y\" disabled>Y</option>"
              "</select></main>"
              "<script>"
              "document.title = JSON.stringify(document.getElementById('s').value);"
              "</script>"))
        (.then (fn [title]
                 (println "quickjs real select.value (all disabled, none selected) ->" (pr-str title))
                 (is (= "\"\"" title)
                     (str "expected an all-disabled select with nothing explicitly selected to "
                          "select nothing at all (matching real Chrome's selectedIndex -1), not "
                          "fall back to the first option regardless, got document.title = "
                          (pr-str title)))
                 (done)))
        (.catch (fn [err]
                  (is false (str "QuickJS WASM engine initialization / page load failed: "
                                 (or (.-message err) err)))
                  (done))))))

(deftest quickjs-real-select-value-explicit-selected-disabled-wins-even-when-not-first-test
  (async done
    (-> (run-page-and-read-title!
         (str "<main><select id=\"s\">"
              "<option value=\"a\">A</option>"
              "<option value=\"x\" disabled selected>X</option>"
              "<option value=\"y\">Y</option>"
              "</select></main>"
              "<script>"
              "document.title = document.getElementById('s').value;"
              "</script>"))
        (.then (fn [title]
                 (println "quickjs real select.value (disabled+selected, not first) ->" (pr-str title))
                 (is (= "x" title)
                     (str "expected the explicitly-selected disabled option's value regardless of "
                          "its position, matching real Chrome, got document.title = " (pr-str title)))
                 (done)))
        (.catch (fn [err]
                  (is false (str "QuickJS WASM engine initialization / page load failed: "
                                 (or (.-message err) err)))
                  (done))))))
