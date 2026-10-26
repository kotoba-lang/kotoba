(ns browser.compat.quickjs-dispatchevent-click-activation-smoke-test
  "Real page-script round-trip proof that el.dispatchEvent(new
  MouseEvent('click', ...)) now runs the same real checkbox/radio
  activation behavior as .click() -- previously only .click() got this,
  dispatchEvent() only ever ran registered listeners with no activation
  at all, unlike real Chrome/Firefox (per real HTML5/DOM, activation
  behavior is part of the generic event-dispatch algorithm for a click
  event, independent of the trigger mechanism), confirmed via actual
  QuickJS WASM, not a JVM stand-in."
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
     (let [url "https://app.example/dispatchevent-click-activation-round-trip"
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

(deftest quickjs-real-dispatchevent-click-toggles-checkbox-and-fires-input-change-test
  (async done
    (-> (run-page-and-read-title!
         (str "<main><input id=\"box\" type=\"checkbox\">"
              "<script>"
              "var box = document.getElementById('box');"
              "var events = [];"
              "box.addEventListener('input', function() { events.push('input'); });"
              "box.addEventListener('change', function() { events.push('change'); });"
              "box.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }));"
              "document.title = box.checked + ':' + events.join(',');"
              "</script></main>"))
        (.then (fn [title]
                 (println "quickjs real dispatchEvent click toggle+events ->" (pr-str title))
                 (is (= "true:input,change" title)
                     (str "expected dispatchEvent(click) to toggle checked to true and fire "
                          "input then change, got document.title = " (pr-str title)))
                 (done)))
        (.catch (fn [err]
                  (is false (str "QuickJS WASM engine initialization / page load failed: "
                                 (or (.-message err) err)))
                  (done))))))

(deftest quickjs-real-dispatchevent-click-checks-radio-and-clears-group-siblings-test
  (async done
    (-> (run-page-and-read-title!
         (str "<main>"
              "<input id=\"a\" type=\"radio\" name=\"g\" checked>"
              "<input id=\"b\" type=\"radio\" name=\"g\">"
              "<script>"
              "var a = document.getElementById('a');"
              "var b = document.getElementById('b');"
              "b.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }));"
              "document.title = a.checked + ':' + b.checked;"
              "</script></main>"))
        (.then (fn [title]
                 (println "quickjs real dispatchEvent click radio exclusivity ->" (pr-str title))
                 (is (= "false:true" title)
                     (str "expected dispatchEvent(click) on radio b to check it AND uncheck "
                          "sibling a, got document.title = " (pr-str title)))
                 (done)))
        (.catch (fn [err]
                  (is false (str "QuickJS WASM engine initialization / page load failed: "
                                 (or (.-message err) err)))
                  (done))))))

(deftest quickjs-real-dispatchevent-click-preventdefault-reverts-checked-test
  (async done
    (-> (run-page-and-read-title!
         (str "<main><input id=\"box\" type=\"checkbox\">"
              "<script>"
              "var box = document.getElementById('box');"
              "var events = [];"
              "box.addEventListener('click', function(e) { e.preventDefault(); });"
              "box.addEventListener('input', function() { events.push('input'); });"
              "box.addEventListener('change', function() { events.push('change'); });"
              "box.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }));"
              "document.title = box.checked + ':' + events.join(',');"
              "</script></main>"))
        (.then (fn [title]
                 (println "quickjs real dispatchEvent click preventDefault ->" (pr-str title))
                 (is (= "false:" title)
                     (str "preventDefault() on a dispatchEvent-triggered click must revert "
                          "checked and fire no input/change, got document.title = "
                          (pr-str title)))
                 (done)))
        (.catch (fn [err]
                  (is false (str "QuickJS WASM engine initialization / page load failed: "
                                 (or (.-message err) err)))
                  (done))))))

(deftest quickjs-real-dispatchevent-non-click-event-still-just-dispatches-test
  ;; No-regression check: dispatchEvent() of a non-click event must still
  ;; behave exactly as before -- no activation logic applies to it at all.
  (async done
    (-> (run-page-and-read-title!
         (str "<main><input id=\"box\" type=\"checkbox\">"
              "<script>"
              "var box = document.getElementById('box');"
              "var events = [];"
              "box.addEventListener('custom-thing', function() { events.push('custom-thing'); });"
              "box.dispatchEvent(new Event('custom-thing', { bubbles: true }));"
              "document.title = box.checked + ':' + events.join(',');"
              "</script></main>"))
        (.then (fn [title]
                 (println "quickjs real dispatchEvent non-click no-op on checked ->" (pr-str title))
                 (is (= "false:custom-thing" title)
                     (str "a non-click dispatchEvent must still just dispatch, no activation, "
                          "got document.title = " (pr-str title)))
                 (done)))
        (.catch (fn [err]
                  (is false (str "QuickJS WASM engine initialization / page load failed: "
                                 (or (.-message err) err)))
                  (done))))))
