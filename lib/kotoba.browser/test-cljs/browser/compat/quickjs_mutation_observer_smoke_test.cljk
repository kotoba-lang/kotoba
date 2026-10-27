(ns browser.compat.quickjs-mutation-observer-smoke-test
  "Real page-script round-trip proof that `MutationObserver.observe()`
  called twice on the SAME node from the SAME observer replaces that
  target's registration, matching the real DOM spec, instead of
  duplicating it.

  Previously `observe()` unconditionally pushed a new `{nodeId, options}`
  entry into the observer's own internal `targets` list with no check for
  an existing entry on the same node -- a real, common defensive/re-init
  pattern (a component calling its own `observe()` setup again, even with
  identical options) meant `__kotobaQueueMutation`'s dispatch loop
  iterated over TWO entries for one real DOM mutation, delivering
  duplicate `MutationRecord`s to the observer's single callback for a
  single real change."
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
     (let [url "https://app.example/mutation-observer-round-trip"
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

(deftest quickjs-real-mutation-observer-observing-same-target-twice-does-not-duplicate-records-test
  (async done
    (-> (run-page-and-read-title!
         (str "<main><div id=\"x\">old</div>"
              "<script>"
              "var mo = new MutationObserver(function() {});"
              "var target = document.getElementById('x');"
              "mo.observe(target, {attributes: true});"
              "mo.observe(target, {attributes: true});"
              "target.setAttribute('data-x', '1');"
              "var records = mo.takeRecords();"
              "document.title = 'records=' + records.length;"
              "</script></main>"))
        (.then (fn [title]
                 (println "quickjs real MutationObserver duplicate-observe ->" (pr-str title))
                 (is (= "records=1" title)
                     (str "expected observing the same target twice to be a no-op "
                          "(the second call replaces the first registration, not adds "
                          "a second one), so a single real mutation should deliver "
                          "exactly ONE record, got document.title = " (pr-str title)))
                 (done)))
        (.catch (fn [err]
                  (is false (str "QuickJS WASM engine initialization / page load failed: "
                                 (or (.-message err) err)))
                  (done))))))

(deftest quickjs-real-mutation-observer-two-distinct-targets-each-deliver-their-own-record-test
  (async done
    (-> (run-page-and-read-title!
         (str "<main><div id=\"x\">old</div><div id=\"y\">old</div>"
              "<script>"
              "var mo = new MutationObserver(function() {});"
              "var x = document.getElementById('x');"
              "var y = document.getElementById('y');"
              "mo.observe(x, {attributes: true});"
              "mo.observe(y, {attributes: true});"
              "x.setAttribute('data-x', '1');"
              "y.setAttribute('data-y', '1');"
              "var records = mo.takeRecords();"
              "document.title = 'records=' + records.length;"
              "</script></main>"))
        (.then (fn [title]
                 (println "quickjs real MutationObserver two distinct targets ->" (pr-str title))
                 (is (= "records=2" title)
                     (str "expected two REAL, distinct targets to each independently "
                          "deliver their own record -- the fix must not over-correct "
                          "into deduplicating unrelated nodes, got document.title = "
                          (pr-str title)))
                 (done)))
        (.catch (fn [err]
                  (is false (str "QuickJS WASM engine initialization / page load failed: "
                                 (or (.-message err) err)))
                  (done))))))

(deftest quickjs-real-mutation-observer-reobserving-replaces-options-not-merges-test
  (async done
    (-> (run-page-and-read-title!
         (str "<main><div id=\"x\">old</div>"
              "<script>"
              "var mo = new MutationObserver(function() {});"
              "var target = document.getElementById('x');"
              "mo.observe(target, {attributes: true});"
              "mo.observe(target, {childList: true});"
              "target.setAttribute('data-x', '1');"
              "var child = document.createElement('span');"
              "target.appendChild(child);"
              "var records = mo.takeRecords();"
              "var types = [];"
              "for (var i = 0; i < records.length; i++) { types.push(records[i].type); }"
              "document.title = 'records=' + records.length + '|types=' + types.join(',');"
              "</script></main>"))
        (.then (fn [title]
                 (println "quickjs real MutationObserver re-observe replaces options ->" (pr-str title))
                 (is (= "records=1|types=childList" title)
                     (str "expected the second observe() call's options to REPLACE the "
                          "first (not merge with it) -- since the re-registration only "
                          "asked for childList, the attribute mutation must no longer be "
                          "observed at all, only the childList one, got document.title = "
                          (pr-str title)))
                 (done)))
        (.catch (fn [err]
                  (is false (str "QuickJS WASM engine initialization / page load failed: "
                                 (or (.-message err) err)))
                  (done))))))

(deftest quickjs-real-mutation-observer-attribute-filter-restricts-notifications-test
  (async done
    (-> (run-page-and-read-title!
         (str "<main><div id=\"x\">old</div>"
              "<script>"
              "var mo = new MutationObserver(function() {});"
              "var target = document.getElementById('x');"
              "mo.observe(target, {attributes: true, attributeFilter: ['data-state']});"
              "target.setAttribute('class', 'ignored');"
              "target.setAttribute('data-state', 'active');"
              "target.setAttribute('style', 'color: red');"
              "var records = mo.takeRecords();"
              "var names = [];"
              "for (var i = 0; i < records.length; i++) { names.push(records[i].attributeName); }"
              "document.title = 'records=' + records.length + '|names=' + names.join(',');"
              "</script></main>"))
        (.then (fn [title]
                 (println "quickjs real MutationObserver attributeFilter ->" (pr-str title))
                 (is (= "records=1|names=data-state" title)
                     (str "expected attributeFilter: ['data-state'] to restrict notifications "
                          "to ONLY data-state changes -- class and style must be silently "
                          "dropped, matching real spec, got document.title = " (pr-str title)))
                 (done)))
        (.catch (fn [err]
                  (is false (str "QuickJS WASM engine initialization / page load failed: "
                                 (or (.-message err) err)))
                  (done))))))

(deftest quickjs-real-mutation-observer-attribute-filter-without-explicit-attributes-still-observes-test
  (async done
    (-> (run-page-and-read-title!
         (str "<main><div id=\"x\">old</div>"
              "<script>"
              "var mo = new MutationObserver(function() {});"
              "var target = document.getElementById('x');"
              "mo.observe(target, {attributeFilter: ['data-x']});"
              "target.setAttribute('data-x', '1');"
              "var records = mo.takeRecords();"
              "document.title = 'records=' + records.length;"
              "</script></main>"))
        (.then (fn [title]
                 (println "quickjs real MutationObserver attributeFilter with no explicit attributes ->" (pr-str title))
                 (is (= "records=1" title)
                     (str "expected observe(el, {attributeFilter: [...]}) with NO explicit "
                          "attributes: true to still implicitly observe attributes (matching "
                          "real spec's implicit-attributes-true rule), not silently observe "
                          "nothing at all, got document.title = " (pr-str title)))
                 (done)))
        (.catch (fn [err]
                  (is false (str "QuickJS WASM engine initialization / page load failed: "
                                 (or (.-message err) err)))
                  (done))))))
