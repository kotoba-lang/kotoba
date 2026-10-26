(ns browser.compat.quickjs-url-search-params-set-smoke-test
  "Real page-script round-trip proof that URLSearchParams.prototype.set()
  -- previously implemented as `this.delete(name); this.append(name,
  value);`, which removes EVERY pair named `name` and re-appends a fresh
  one at the end -- now overwrites the FIRST matching pair's value in
  place and preserves its position relative to other keys, matching real
  spec behavior, through actual QuickJS WASM end-to-end."
  (:require [cljs.test :refer [deftest is async]]
            [browser.compat.quickjs-runner :as quickjs-runner]
            [browser.session :as session]
            [kotoba.wasm.host :as host]))

(defn- dispose-engine!
  [session]
  (when-let [engine (get-in session [:browser.session/script-engine :script-engine/engine])]
    (when-let [dispose (:quickjs.engine/dispose engine)]
      (dispose engine))))

(defn- run-page-and-read-title!
  [{:keys [html]}]
  (js/Promise.
   (fn [resolve reject]
     (let [h (host/recording-host)
           base-session (session/new-session (quickjs-runner/quickjs-session-opts {:host h}))]
       (-> (session/ensure-script-engine! base-session)
           (.then
            (fn [ready-session]
              (try
                (let [after (session/load-html! ready-session
                                                {:url "kotoba://url-search-params-set-round-trip"
                                                 :html html})
                      title (get-in after [:browser.session/page :browser/title])]
                  (dispose-engine! after)
                  (resolve title))
                (catch :default e
                  (dispose-engine! ready-session)
                  (reject e)))))
           (.catch (fn [err]
                     (dispose-engine! base-session)
                     (reject err))))))))

(deftest quickjs-real-url-search-params-set-preserves-first-occurrence-position-test
  (async done
    (-> (run-page-and-read-title!
         {:html (str "<script>"
                     "var p = new URLSearchParams('a=1&b=2&a=3');"
                     "p.set('a', '9');"
                     "document.title = p.toString();"
                     "</script>")})
        (.then (fn [title]
                 (println "quickjs real URLSearchParams.set() on a multi-value key ->" (pr-str title))
                 (is (= "a=9&b=2" title)
                     (str "expected set() to overwrite the FIRST 'a' pair in place and drop the "
                          "second, preserving 'b's position (real browsers produce a=9&b=2, the "
                          "previous delete-then-append implementation produced b=2&a=9), "
                          "got " (pr-str title)))
                 (done)))
        (.catch (fn [err]
                  (is false (str "QuickJS WASM engine initialization / page load failed: "
                                 (or (.-message err) err)))
                  (done))))))

(deftest quickjs-real-url-search-params-set-on-a-new-key-appends-at-the-end-test
  (async done
    (-> (run-page-and-read-title!
         {:html (str "<script>"
                     "var p = new URLSearchParams('a=1&b=2');"
                     "p.set('c', '9');"
                     "document.title = p.toString();"
                     "</script>")})
        (.then (fn [title]
                 (println "quickjs real URLSearchParams.set() on a brand-new key ->" (pr-str title))
                 (is (= "a=1&b=2&c=9" title)
                     (str "expected set() on a name with no existing pair to append at the end "
                          "same as before, got " (pr-str title)))
                 (done)))
        (.catch (fn [err]
                  (is false (str "QuickJS WASM engine initialization / page load failed: "
                                 (or (.-message err) err)))
                  (done))))))

(deftest quickjs-real-url-search-params-set-via-url-searchparams-live-view-test
  (async done
    (-> (run-page-and-read-title!
         {:html (str "<script>"
                     "var u = new URL('https://example.com/?a=1&b=2&a=3');"
                     "u.searchParams.set('a', '9');"
                     "document.title = u.searchParams.toString();"
                     "</script>")})
        (.then (fn [title]
                 (println "quickjs real URL.searchParams.set() ->" (pr-str title))
                 (is (= "a=9&b=2" title)
                     (str "expected URL.prototype.searchParams (a real URLSearchParams instance) "
                          "to exhibit the same fixed ordering behavior, got " (pr-str title)))
                 (done)))
        (.catch (fn [err]
                  (is false (str "QuickJS WASM engine initialization / page load failed: "
                                 (or (.-message err) err)))
                  (done))))))
