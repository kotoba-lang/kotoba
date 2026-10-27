(ns browser.compat.quickjs-stop-propagation-smoke-test
  "Real page-script round-trip proof that Event.stopPropagation() only stops
  propagation to ANCESTOR nodes and does NOT skip other listeners already
  registered on the SAME target, and that stopImmediatePropagation() (which
  previously did not exist at all) additionally skips those same-target
  listeners too -- confirmed via actual QuickJS WASM, not a JVM stand-in."
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
     (let [url "https://app.example/stop-propagation-round-trip"
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

(deftest quickjs-real-stop-propagation-does-not-skip-same-target-listeners-test
  (async done
    (-> (run-page-and-read-title!
         (str "<main><div id=\"box\">content</div>"
              "<script>"
              "var box = document.getElementById('box');"
              "var events = [];"
              "box.addEventListener('click', function(e) { events.push('A'); e.stopPropagation(); });"
              "box.addEventListener('click', function() { events.push('B'); });"
              "box.dispatchEvent(new Event('click', { bubbles: true }));"
              "document.title = events.join(',');"
              "</script></main>"))
        (.then (fn [title]
                 (println "quickjs real stopPropagation same-target listeners ->" (pr-str title))
                 (is (= "A,B" title)
                     (str "stopPropagation() must NOT skip other listeners already "
                          "registered on the SAME target, got document.title = " (pr-str title)))
                 (done)))
        (.catch (fn [err]
                  (is false (str "QuickJS WASM engine initialization / page load failed: "
                                 (or (.-message err) err)))
                  (done))))))

(deftest quickjs-real-stop-propagation-still-stops-bubbling-to-ancestors-test
  (async done
    (-> (run-page-and-read-title!
         (str "<main><div id=\"parent\"><div id=\"child\">content</div></div>"
              "<script>"
              "var parent = document.getElementById('parent');"
              "var child = document.getElementById('child');"
              "var events = [];"
              "child.addEventListener('click', function(e) { events.push('child'); e.stopPropagation(); });"
              "parent.addEventListener('click', function() { events.push('parent'); });"
              "child.dispatchEvent(new Event('click', { bubbles: true }));"
              "document.title = events.join(',');"
              "</script></main>"))
        (.then (fn [title]
                 (println "quickjs real stopPropagation ancestor bubbling ->" (pr-str title))
                 (is (= "child" title)
                     (str "stopPropagation() must still stop the event from reaching an "
                          "ancestor's own listener, got document.title = " (pr-str title)))
                 (done)))
        (.catch (fn [err]
                  (is false (str "QuickJS WASM engine initialization / page load failed: "
                                 (or (.-message err) err)))
                  (done))))))

(deftest quickjs-real-stop-immediate-propagation-skips-same-target-listeners-test
  (async done
    (-> (run-page-and-read-title!
         (str "<main><div id=\"box\">content</div>"
              "<script>"
              "var box = document.getElementById('box');"
              "var events = [];"
              "box.addEventListener('click', function(e) { events.push('A'); e.stopImmediatePropagation(); });"
              "box.addEventListener('click', function() { events.push('B'); });"
              "box.dispatchEvent(new Event('click', { bubbles: true }));"
              "document.title = events.join(',');"
              "</script></main>"))
        (.then (fn [title]
                 (println "quickjs real stopImmediatePropagation same-target listeners ->" (pr-str title))
                 (is (= "A" title)
                     (str "stopImmediatePropagation() must skip other listeners on the SAME "
                          "target, got document.title = " (pr-str title)))
                 (done)))
        (.catch (fn [err]
                  (is false (str "QuickJS WASM engine initialization / page load failed: "
                                 (or (.-message err) err)))
                  (done))))))

(deftest quickjs-real-stop-immediate-propagation-also-stops-bubbling-test
  (async done
    (-> (run-page-and-read-title!
         (str "<main><div id=\"parent\"><div id=\"child\">content</div></div>"
              "<script>"
              "var parent = document.getElementById('parent');"
              "var child = document.getElementById('child');"
              "var events = [];"
              "child.addEventListener('click', function(e) { events.push('child'); e.stopImmediatePropagation(); });"
              "parent.addEventListener('click', function() { events.push('parent'); });"
              "child.dispatchEvent(new Event('click', { bubbles: true }));"
              "document.title = events.join(',');"
              "</script></main>"))
        (.then (fn [title]
                 (println "quickjs real stopImmediatePropagation ancestor bubbling ->" (pr-str title))
                 (is (= "child" title)
                     (str "stopImmediatePropagation() must also stop bubbling to an ancestor, "
                          "got document.title = " (pr-str title)))
                 (done)))
        (.catch (fn [err]
                  (is false (str "QuickJS WASM engine initialization / page load failed: "
                                 (or (.-message err) err)))
                  (done))))))
