(ns browser.compat.quickjs-focus-blur-events-smoke-test
  "Real page-script round-trip proof that element.focus()/.blur() now
  dispatch real focus/blur events -- previously neither method ever
  called __kotobaDispatch at all (only the host mutate request and
  __kotobaSnapshot.focus were updated), unlike the ALREADY-correct real
  pointer-click focus path in document_input.cljc, confirmed via actual
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
     (let [url "https://app.example/focus-blur-events-round-trip"
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

(deftest quickjs-real-focus-fires-focus-event-test
  (async done
    (-> (run-page-and-read-title!
         (str "<main><input id=\"box\">"
              "<script>"
              "var box = document.getElementById('box');"
              "var events = [];"
              "box.addEventListener('focus', function() { events.push('focus'); });"
              "box.focus();"
              "document.title = events.join(',');"
              "</script></main>"))
        (.then (fn [title]
                 (println "quickjs real focus() fires focus event ->" (pr-str title))
                 (is (= "focus" title)
                     (str "focus() must fire a real focus event, got document.title = "
                          (pr-str title)))
                 (done)))
        (.catch (fn [err]
                  (is false (str "QuickJS WASM engine initialization / page load failed: "
                                 (or (.-message err) err)))
                  (done))))))

(deftest quickjs-real-blur-fires-blur-event-test
  (async done
    (-> (run-page-and-read-title!
         (str "<main><input id=\"box\">"
              "<script>"
              "var box = document.getElementById('box');"
              "var events = [];"
              "box.addEventListener('blur', function() { events.push('blur'); });"
              "box.focus();"
              "box.blur();"
              "document.title = events.join(',');"
              "</script></main>"))
        (.then (fn [title]
                 (println "quickjs real blur() fires blur event ->" (pr-str title))
                 (is (= "blur" title)
                     (str "blur() must fire a real blur event, got document.title = "
                          (pr-str title)))
                 (done)))
        (.catch (fn [err]
                  (is false (str "QuickJS WASM engine initialization / page load failed: "
                                 (or (.-message err) err)))
                  (done))))))

(deftest quickjs-real-focus-moving-between-elements-blurs-the-previous-one-test
  (async done
    (-> (run-page-and-read-title!
         (str "<main><input id=\"a\"><input id=\"b\">"
              "<script>"
              "var a = document.getElementById('a');"
              "var b = document.getElementById('b');"
              "var events = [];"
              "a.addEventListener('blur', function() { events.push('a-blur'); });"
              "b.addEventListener('focus', function() { events.push('b-focus'); });"
              "a.focus();"
              "b.focus();"
              "document.title = events.join(',');"
              "</script></main>"))
        (.then (fn [title]
                 (println "quickjs real focus moves and blurs previous ->" (pr-str title))
                 (is (= "a-blur,b-focus" title)
                     (str "focusing b must first blur the previously-focused a, got "
                          "document.title = " (pr-str title)))
                 (done)))
        (.catch (fn [err]
                  (is false (str "QuickJS WASM engine initialization / page load failed: "
                                 (or (.-message err) err)))
                  (done))))))

(deftest quickjs-real-focus-on-already-focused-element-is-a-no-op-test
  (async done
    (-> (run-page-and-read-title!
         (str "<main><input id=\"box\">"
              "<script>"
              "var box = document.getElementById('box');"
              "var events = [];"
              "box.addEventListener('focus', function() { events.push('focus'); });"
              "box.focus();"
              "box.focus();"
              "document.title = events.length + '';"
              "</script></main>"))
        (.then (fn [title]
                 (println "quickjs real focus on already-focused no-op ->" (pr-str title))
                 (is (= "1" title)
                     (str "focusing an already-focused element must not re-fire focus, got "
                          "document.title = " (pr-str title)))
                 (done)))
        (.catch (fn [err]
                  (is false (str "QuickJS WASM engine initialization / page load failed: "
                                 (or (.-message err) err)))
                  (done))))))

(deftest quickjs-real-blur-on-a-non-focused-element-is-a-no-op-test
  (async done
    (-> (run-page-and-read-title!
         (str "<main><input id=\"box\">"
              "<script>"
              "var box = document.getElementById('box');"
              "var events = [];"
              "box.addEventListener('blur', function() { events.push('blur'); });"
              "box.blur();"
              "document.title = events.length + '';"
              "</script></main>"))
        (.then (fn [title]
                 (println "quickjs real blur on non-focused no-op ->" (pr-str title))
                 (is (= "0" title)
                     (str "blur() on an element that was never focused must fire no blur "
                          "event, got document.title = " (pr-str title)))
                 (done)))
        (.catch (fn [err]
                  (is false (str "QuickJS WASM engine initialization / page load failed: "
                                 (or (.-message err) err)))
                  (done))))))
