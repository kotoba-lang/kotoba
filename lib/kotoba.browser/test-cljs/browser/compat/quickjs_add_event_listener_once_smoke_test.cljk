(ns browser.compat.quickjs-add-event-listener-once-smoke-test
  "Real page-script round-trip proof that addEventListener's `once` option
  actually self-unregisters the listener after its first invocation --
  previously accepted (webapi-surface declares addEventListener supported
  with no caveat) but completely ignored across all three
  addEventListener implementations (element, document, window), so a
  {once:true} handler fired on every subsequent event forever instead of
  exactly once, confirmed via actual QuickJS WASM end-to-end."
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
     (let [url "https://app.example/add-event-listener-once-round-trip"
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

(deftest quickjs-real-once-listener-fires-exactly-once-on-an-element-test
  (async done
    (-> (run-page-and-read-title!
         (str "<main><div id=\"x\">old</div>"
              "<script>"
              "var count = 0;"
              "var target = document.getElementById('x');"
              "target.addEventListener('click', function() { count++; }, {once: true});"
              "target.click();"
              "target.click();"
              "target.click();"
              "document.title = 'count=' + count;"
              "</script></main>"))
        (.then (fn [title]
                 (println "quickjs real element once-listener across 3 clicks ->" (pr-str title))
                 (is (= "count=1" title)
                     (str "expected a {once:true} listener to fire exactly once across 3 real "
                          "clicks, not every time, got document.title = " (pr-str title)))
                 (done)))
        (.catch (fn [err]
                  (is false (str "QuickJS WASM engine initialization / page load failed: "
                                 (or (.-message err) err)))
                  (done))))))

(deftest quickjs-real-once-listener-can-be-removed-before-it-fires-by-original-reference-test
  (async done
    (-> (run-page-and-read-title!
         (str "<main><div id=\"x\">old</div>"
              "<script>"
              "var count = 0;"
              "function handler() { count++; }"
              "var target = document.getElementById('x');"
              "target.addEventListener('click', handler, {once: true});"
              "target.removeEventListener('click', handler);"
              "target.click();"
              "document.title = 'count=' + count;"
              "</script></main>"))
        (.then (fn [title]
                 (println "quickjs real once-listener removed before firing ->" (pr-str title))
                 (is (= "count=0" title)
                     (str "expected removeEventListener(type, ORIGINAL handler reference) to "
                          "successfully remove a not-yet-fired {once:true} listener, got "
                          "document.title = " (pr-str title)))
                 (done)))
        (.catch (fn [err]
                  (is false (str "QuickJS WASM engine initialization / page load failed: "
                                 (or (.-message err) err)))
                  (done))))))

(deftest quickjs-real-once-listener-does-not-affect-other-listeners-on-the-same-target-test
  (async done
    (-> (run-page-and-read-title!
         (str "<main><div id=\"x\">old</div>"
              "<script>"
              "var order = [];"
              "var target = document.getElementById('x');"
              "target.addEventListener('click', function() { order.push('normal'); });"
              "target.addEventListener('click', function() { order.push('once'); }, {once: true});"
              "target.click();"
              "target.click();"
              "document.title = order.join(',');"
              "</script></main>"))
        (.then (fn [title]
                 (println "quickjs real once + normal listeners on the same target ->" (pr-str title))
                 (is (= "normal,once,normal" title)
                     (str "expected the once-listener to fire only on the FIRST click while the "
                          "normal listener keeps firing on both, got document.title = "
                          (pr-str title)))
                 (done)))
        (.catch (fn [err]
                  (is false (str "QuickJS WASM engine initialization / page load failed: "
                                 (or (.-message err) err)))
                  (done))))))

(deftest quickjs-real-once-listener-on-window-fires-exactly-once-test
  (async done
    (-> (run-page-and-read-title!
         (str "<main><script>"
              "var count = 0;"
              "window.addEventListener('resize', function() { count++; }, {once: true});"
              "window.dispatchEvent(new Event('resize'));"
              "window.dispatchEvent(new Event('resize'));"
              "document.title = 'count=' + count;"
              "</script></main>"))
        (.then (fn [title]
                 (println "quickjs real window once-listener across 2 real dispatches ->" (pr-str title))
                 (is (= "count=1" title)
                     (str "expected a {once:true} window listener to fire exactly once, mirroring "
                          "the element-level fix, got document.title = " (pr-str title)))
                 (done)))
        (.catch (fn [err]
                  (is false (str "QuickJS WASM engine initialization / page load failed: "
                                 (or (.-message err) err)))
                  (done))))))
