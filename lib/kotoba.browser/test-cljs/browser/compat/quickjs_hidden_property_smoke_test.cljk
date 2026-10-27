(ns browser.compat.quickjs-hidden-property-smoke-test
  "Real page-script round-trip proof that `element.hidden` -- previously
  entirely missing as a JS-facing property (confirmed via a repo-wide grep
  returning zero `get hidden`/`set hidden` matches; `el.hidden` read
  `undefined` and `el.hidden = true` was a silent no-op) -- now works through
  actual QuickJS WASM, mirroring the already-existing `disabled`/`required`
  boolean-attribute-reflecting getter/setter shape."
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
     (let [url "https://app.example/hidden-property-round-trip"
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

(deftest quickjs-real-hidden-getter-reflects-the-hidden-attribute-test
  (async done
    (-> (run-page-and-read-title!
         (str "<main><div id=\"box\" hidden>content</div>"
              "<script>"
              "var box = document.getElementById('box');"
              "document.title = String(box.hidden);"
              "</script></main>"))
        (.then (fn [title]
                 (println "quickjs real hidden getter ->" (pr-str title))
                 (is (= "true" title)
                     (str "expected box.hidden to read true for an element with the "
                          "hidden attribute present, got document.title = " (pr-str title)))
                 (done)))
        (.catch (fn [err]
                  (is false (str "QuickJS WASM engine initialization / page load failed: "
                                 (or (.-message err) err)))
                  (done))))))

(deftest quickjs-real-hidden-setter-true-adds-the-hidden-attribute-test
  (async done
    (-> (run-page-and-read-title!
         (str "<main><div id=\"box\">content</div>"
              "<script>"
              "var box = document.getElementById('box');"
              "box.hidden = true;"
              "document.title = box.getAttribute('hidden') + ':' + box.hidden;"
              "</script></main>"))
        (.then (fn [title]
                 (println "quickjs real hidden setter (true) ->" (pr-str title))
                 (is (= "true:true" title)
                     (str "expected setting box.hidden = true to add the hidden attribute "
                          "and box.hidden to read back true, got document.title = "
                          (pr-str title)))
                 (done)))
        (.catch (fn [err]
                  (is false (str "QuickJS WASM engine initialization / page load failed: "
                                 (or (.-message err) err)))
                  (done))))))

(deftest quickjs-real-hidden-setter-false-removes-the-hidden-attribute-test
  (async done
    (-> (run-page-and-read-title!
         (str "<main><div id=\"box\" hidden>content</div>"
              "<script>"
              "var box = document.getElementById('box');"
              "box.hidden = false;"
              "document.title = box.getAttribute('hidden') + ':' + box.hidden;"
              "</script></main>"))
        (.then (fn [title]
                 (println "quickjs real hidden setter (false) ->" (pr-str title))
                 (is (= "null:false" title)
                     (str "expected setting box.hidden = false to remove the hidden "
                          "attribute and box.hidden to read back false, got "
                          "document.title = " (pr-str title)))
                 (done)))
        (.catch (fn [err]
                  (is false (str "QuickJS WASM engine initialization / page load failed: "
                                 (or (.-message err) err)))
                  (done))))))
