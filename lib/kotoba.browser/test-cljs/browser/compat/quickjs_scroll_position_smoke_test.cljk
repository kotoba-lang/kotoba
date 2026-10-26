(ns browser.compat.quickjs-scroll-position-smoke-test
  "Real page-script round-trip proof that `element.scrollTop`/`scrollLeft`
  -- previously entirely missing from the webapi shim, confirmed via a
  repo-wide grep returning zero matches -- now work through actual QuickJS
  WASM, not a JVM stand-in.

  This closes a gap between two ALREADY-shipped halves of the same
  feature: `browser.document-input`'s real wheel-event handling already
  writes the exact same `scroll-top`/`scroll-left` node attrs on every
  real wheel event, and `cssom.layout` already reads them back to clip/
  offset scrollable content at paint time -- only this JS-facing read/
  write surface was missing, so a script had no way to read the current
  scroll position or programmatically scroll (e.g. auto-scroll-to-bottom
  patterns common in chat/log UIs)."
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
     (let [url "https://app.example/scroll-position-round-trip"
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

(deftest quickjs-real-scroll-top-left-default-to-zero-test
  (async done
    (-> (run-page-and-read-title!
         (str "<main><div id=\"box\">content</div>"
              "<script>"
              "var box = document.getElementById('box');"
              "document.title = box.scrollTop + ':' + box.scrollLeft;"
              "</script></main>"))
        (.then (fn [title]
                 (println "quickjs real scrollTop/scrollLeft default ->" (pr-str title))
                 (is (= "0:0" title)
                     (str "expected a fresh element with no prior scroll state to report "
                          "0:0, got document.title = " (pr-str title)))
                 (done)))
        (.catch (fn [err]
                  (is false (str "QuickJS WASM engine initialization / page load failed: "
                                 (or (.-message err) err)))
                  (done))))))

(deftest quickjs-real-scroll-top-left-set-then-read-back-test
  (async done
    (-> (run-page-and-read-title!
         (str "<main><div id=\"box\">content</div>"
              "<script>"
              "var box = document.getElementById('box');"
              "box.scrollTop = 42;"
              "box.scrollLeft = 17;"
              "document.title = box.scrollTop + ':' + box.scrollLeft;"
              "</script></main>"))
        (.then (fn [title]
                 (println "quickjs real scrollTop/scrollLeft set-then-read-back ->" (pr-str title))
                 (is (= "42:17" title)
                     (str "expected setting scrollTop/scrollLeft to genuinely persist and "
                          "read back the same values, got document.title = " (pr-str title)))
                 (done)))
        (.catch (fn [err]
                  (is false (str "QuickJS WASM engine initialization / page load failed: "
                                 (or (.-message err) err)))
                  (done))))))

(deftest quickjs-real-scroll-top-clamps-a-negative-value-to-zero-test
  (async done
    (-> (run-page-and-read-title!
         (str "<main><div id=\"box\">content</div>"
              "<script>"
              "var box = document.getElementById('box');"
              "box.scrollTop = -10;"
              "document.title = String(box.scrollTop);"
              "</script></main>"))
        (.then (fn [title]
                 (println "quickjs real scrollTop negative clamp ->" (pr-str title))
                 (is (= "0" title)
                     (str "expected a negative scrollTop assignment to clamp to 0 (real "
                          "scrollTop is never negative), got document.title = " (pr-str title)))
                 (done)))
        (.catch (fn [err]
                  (is false (str "QuickJS WASM engine initialization / page load failed: "
                                 (or (.-message err) err)))
                  (done))))))
