(ns browser.compat.quickjs-location-live-url-smoke-test
  "Real page-script round-trip proof that `location.href`/`.pathname`/
   `.search`/`.hash`/`.host`/`.protocol`/`.origin` now reflect the CURRENT
   document's real URL -- previously `location` was a static object built
   once with `href` fixed at the literal string 'about:blank' forever
   (confirmed via a temporary diagnostic test before touching source:
   `location.href` read 'about:blank' while `document.URL` correctly
   showed the real navigated URL with query string and hash), and every
   other property (`pathname`/`search`/`hash`/`host`/`protocol`/`origin`)
   read `undefined` since none of them existed at all. Also covers
   `location.href = someUrl` (a real, extremely common navigation idiom)
   -- previously a silent no-op plain-property assignment with no
   navigation side effect, now routed through the same `location/assign`
   capability request `.assign()` itself pushes."
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
  [url html]
  (js/Promise.
   (fn [resolve reject]
     (let [fetch-fn (canned-fetch-fn {url html})
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

(deftest quickjs-real-location-href-matches-document-url-test
  (async done
    (-> (run-page-and-read-title!
         "https://app.example/search?q=hello&page=2#results"
         (str "<main></main>"
              "<script>"
              "document.title = String(location.href === document.URL);"
              "</script>"))
        (.then (fn [title]
                 (println "quickjs real location.href === document.URL ->" (pr-str title))
                 (is (= "true" title)
                     (str "location.href must always match the current document's real URL, "
                          "got document.title = " (pr-str title)))
                 (done)))
        (.catch (fn [err]
                  (is false (str "QuickJS WASM engine initialization / page load failed: "
                                 (or (.-message err) err)))
                  (done))))))

(deftest quickjs-real-location-parts-reflect-query-and-hash-test
  (async done
    (-> (run-page-and-read-title!
         "https://app.example/search?q=hello&page=2#results"
         (str "<main></main>"
              "<script>"
              "document.title = location.pathname + '|' + location.search + '|' + location.hash + "
              "'|' + location.host + '|' + location.protocol + '|' + location.origin;"
              "</script>"))
        (.then (fn [title]
                 (println "quickjs real location parts ->" (pr-str title))
                 (is (= "/search|?q=hello&page=2|#results|app.example|https:|https://app.example" title)
                     (str "location's URL-part properties must be parsed from the real current URL, "
                          "got document.title = " (pr-str title)))
                 (done)))
        (.catch (fn [err]
                  (is false (str "QuickJS WASM engine initialization / page load failed: "
                                 (or (.-message err) err)))
                  (done))))))

(deftest quickjs-real-location-href-setter-delegates-to-assign-test
  ;; A real host/recording-host only tracks committed DOM :ops, not the raw
  ;; location/assign capability request this pushes (that's a separate,
  ;; pre-existing, already-working layer in quickjs_execution.cljc, not
  ;; something this fix touches) -- so the most direct, minimal-assumption
  ;; way to verify `location.href = url` now delegates to `.assign(url)`
  ;; (previously a silent no-op plain-property write) is to temporarily
  ;; replace .assign with a spy from within the page script itself.
  (async done
    (-> (run-page-and-read-title!
         "https://app.example/href-setter-round-trip"
         (str "<main></main>"
              "<script>"
              "var assignCalledWith = null;"
              "location.assign = function(url) { assignCalledWith = url; };"
              "location.href = '/other-page';"
              "document.title = String(assignCalledWith);"
              "</script>"))
        (.then (fn [title]
                 (println "quickjs real location.href= setter delegates to .assign() ->" (pr-str title))
                 (is (= "/other-page" title)
                     (str "expected location.href = '/other-page' to call this.assign('/other-page'), "
                          "got document.title = " (pr-str title)))
                 (done)))
        (.catch (fn [err]
                  (is false (str "QuickJS WASM engine initialization / page load failed: "
                                 (or (.-message err) err)))
                  (done))))))
