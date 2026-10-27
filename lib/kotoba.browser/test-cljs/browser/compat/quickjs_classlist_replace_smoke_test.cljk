(ns browser.compat.quickjs-classlist-replace-smoke-test
  "Real page-script round-trip proof that `element.classList.replace(oldToken,
  newToken)` -- previously entirely missing (confirmed via a repo-wide grep
  returning zero matches; calling it threw a real `TypeError`) -- now works
  through actual QuickJS WASM, not a JVM stand-in.

  A very common vanilla-JS single-class-swap idiom (e.g.
  `el.classList.replace('loading', 'loaded')`), composed here from the SAME
  `tokens()`/`write()` closures the already-existing `add`/`remove`/`toggle`
  methods already use."
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
     (let [url "https://app.example/classlist-replace-round-trip"
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

(deftest quickjs-real-classlist-replace-swaps-an-existing-token-test
  (async done
    (-> (run-page-and-read-title!
         (str "<main><div id=\"box\" class=\"loading box\">content</div>"
              "<script>"
              "var box = document.getElementById('box');"
              "var returned = box.classList.replace('loading', 'loaded');"
              "document.title = box.getAttribute('class') + ':' + returned;"
              "</script></main>"))
        (.then (fn [title]
                 (println "quickjs real classList.replace swap ->" (pr-str title))
                 (is (= "loaded box:true" title)
                     (str "expected the class attribute to reflect the swapped token in "
                          "place, and replace() to return true, got document.title = "
                          (pr-str title)))
                 (done)))
        (.catch (fn [err]
                  (is false (str "QuickJS WASM engine initialization / page load failed: "
                                 (or (.-message err) err)))
                  (done))))))

(deftest quickjs-real-classlist-replace-absent-token-is-a-safe-no-op-test
  ;; Real spec: an absent oldToken is a no-op that does NOT add newToken,
  ;; and returns false.
  (async done
    (-> (run-page-and-read-title!
         (str "<main><div id=\"box\" class=\"box\">content</div>"
              "<script>"
              "var box = document.getElementById('box');"
              "var returned = box.classList.replace('missing', 'loaded');"
              "document.title = box.getAttribute('class') + ':' + returned;"
              "</script></main>"))
        (.then (fn [title]
                 (println "quickjs real classList.replace absent-token no-op ->" (pr-str title))
                 (is (= "box:false" title)
                     (str "expected the class attribute to stay UNCHANGED (newToken must "
                          "NOT be added) and replace() to return false, got document.title = "
                          (pr-str title)))
                 (done)))
        (.catch (fn [err]
                  (is false (str "QuickJS WASM engine initialization / page load failed: "
                                 (or (.-message err) err)))
                  (done))))))
