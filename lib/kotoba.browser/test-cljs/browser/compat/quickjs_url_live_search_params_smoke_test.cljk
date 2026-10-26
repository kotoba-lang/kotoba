(ns browser.compat.quickjs-url-live-search-params-smoke-test
  "Real page-script round-trip proof that URL.prototype.searchParams is a
  LIVE view -- previously href/search/searchParams were three independent
  plain data properties, each captured once at construction and never
  reconciled again: url.searchParams.set(...)/append(...)/delete(...)
  left url.href/url.search silently stale, and assigning url.search never
  touched url.searchParams at all, silently breaking the extremely common
  `url.searchParams.append(...); fetch(url)` idiom. Now genuinely live
  through actual QuickJS WASM end-to-end."
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
                                                {:url "kotoba://url-live-search-params-round-trip"
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

(deftest quickjs-real-url-search-params-mutation-reflects-into-href-and-search-test
  (async done
    (-> (run-page-and-read-title!
         {:html (str "<script>"
                     "var u = new URL('https://example.com/path?a=1');"
                     "u.searchParams.set('b', '2');"
                     "document.title = u.href + '|' + u.search;"
                     "</script>")})
        (.then (fn [title]
                 (println "quickjs real url.searchParams.set() -> href/search ->" (pr-str title))
                 (is (= "https://example.com/path?a=1&b=2|?a=1&b=2" title)
                     (str "expected mutating searchParams to re-serialize into BOTH href and "
                          "search (previously both stayed stuck at the construction-time value), "
                          "got " (pr-str title)))
                 (done)))
        (.catch (fn [err]
                  (is false (str "QuickJS WASM engine initialization / page load failed: "
                                 (or (.-message err) err)))
                  (done))))))

(deftest quickjs-real-url-search-assignment-reflects-into-search-params-and-href-test
  (async done
    (-> (run-page-and-read-title!
         {:html (str "<script>"
                     "var u = new URL('https://example.com/path?a=1');"
                     "u.search = '?x=9';"
                     "document.title = u.searchParams.get('x') + '|' + u.href;"
                     "</script>")})
        (.then (fn [title]
                 (println "quickjs real url.search= -> searchParams/href ->" (pr-str title))
                 (is (= "9|https://example.com/path?x=9" title)
                     (str "expected assigning url.search to re-parse into searchParams AND "
                          "update href (previously searchParams and href both stayed stuck at "
                          "the OLD query), got " (pr-str title)))
                 (done)))
        (.catch (fn [err]
                  (is false (str "QuickJS WASM engine initialization / page load failed: "
                                 (or (.-message err) err)))
                  (done))))))

(deftest quickjs-real-url-search-params-delete-to-empty-clears-search-with-no-trailing-question-mark-test
  (async done
    (-> (run-page-and-read-title!
         {:html (str "<script>"
                     "var u = new URL('https://example.com/path?a=1');"
                     "u.searchParams.delete('a');"
                     "document.title = JSON.stringify(u.search) + '|' + u.href;"
                     "</script>")})
        (.then (fn [title]
                 (println "quickjs real url.searchParams.delete() to empty ->" (pr-str title))
                 (is (= "\"\"|https://example.com/path" title)
                     (str "expected deleting the only param to leave search as an empty string "
                          "(not a bare '?') and href with no trailing '?', got " (pr-str title)))
                 (done)))
        (.catch (fn [err]
                  (is false (str "QuickJS WASM engine initialization / page load failed: "
                                 (or (.-message err) err)))
                  (done))))))

(deftest quickjs-real-url-href-assignment-fully-reparses-every-field-test
  (async done
    (-> (run-page-and-read-title!
         {:html (str "<script>"
                     "var u = new URL('https://example.com/path?a=1');"
                     "u.href = 'https://other.example.com/newpath?z=5#frag';"
                     "document.title = u.protocol + '|' + u.host + '|' + u.pathname + '|' + "
                     "u.search + '|' + u.hash + '|' + u.searchParams.get('z');"
                     "</script>")})
        (.then (fn [title]
                 (println "quickjs real url.href= full reparse ->" (pr-str title))
                 (is (= "https:|other.example.com|/newpath|?z=5|#frag|5" title)
                     (str "expected assigning url.href to fully re-parse protocol/host/pathname/"
                          "search/hash/searchParams, mirroring the constructor -- required so "
                          "url.href= (which worked, narrowly, before this change) doesn't regress "
                          "into a silent no-op now that href is an accessor, got " (pr-str title)))
                 (done)))
        (.catch (fn [err]
                  (is false (str "QuickJS WASM engine initialization / page load failed: "
                                 (or (.-message err) err)))
                  (done))))))
