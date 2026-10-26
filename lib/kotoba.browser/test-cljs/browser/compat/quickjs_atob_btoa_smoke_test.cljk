(ns browser.compat.quickjs-atob-btoa-smoke-test
  "Real page-script round-trip proof that atob()/btoa() -- previously
  entirely missing (a repo-wide grep for atob/btoa returned zero matches
  anywhere) -- now work through actual QuickJS WASM end-to-end."
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
                                                {:url "kotoba://atob-btoa-round-trip"
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

(deftest quickjs-real-btoa-encodes-a-known-string-test
  (async done
    (-> (run-page-and-read-title!
         {:html (str "<script>"
                     "document.title = btoa('hello');"
                     "</script>")})
        (.then (fn [title]
                 (println "quickjs real btoa('hello') ->" (pr-str title))
                 (is (= "aGVsbG8=" title)
                     (str "expected btoa('hello') to encode to the well-known base64 aGVsbG8=, got "
                          (pr-str title)))
                 (done)))
        (.catch (fn [err]
                  (is false (str "QuickJS WASM engine initialization / page load failed: "
                                 (or (.-message err) err)))
                  (done))))))

(deftest quickjs-real-atob-decodes-a-known-string-test
  (async done
    (-> (run-page-and-read-title!
         {:html (str "<script>"
                     "document.title = atob('aGVsbG8=');"
                     "</script>")})
        (.then (fn [title]
                 (println "quickjs real atob('aGVsbG8=') ->" (pr-str title))
                 (is (= "hello" title)
                     (str "expected atob('aGVsbG8=') to decode back to hello, got " (pr-str title)))
                 (done)))
        (.catch (fn [err]
                  (is false (str "QuickJS WASM engine initialization / page load failed: "
                                 (or (.-message err) err)))
                  (done))))))

(deftest quickjs-real-atob-btoa-round-trip-non-multiple-of-3-length-test
  (async done
    (-> (run-page-and-read-title!
         {:html (str "<script>"
                     "document.title = atob(btoa('kotoba browser'));"
                     "</script>")})
        (.then (fn [title]
                 (println "quickjs real atob(btoa('kotoba browser')) ->" (pr-str title))
                 (is (= "kotoba browser" title)
                     (str "expected a real round trip through both real functions to be lossless, got "
                          (pr-str title)))
                 (done)))
        (.catch (fn [err]
                  (is false (str "QuickJS WASM engine initialization / page load failed: "
                                 (or (.-message err) err)))
                  (done))))))

(deftest quickjs-real-btoa-empty-string-test
  (async done
    (-> (run-page-and-read-title!
         {:html (str "<script>"
                     "document.title = JSON.stringify(btoa(''));"
                     "</script>")})
        (.then (fn [title]
                 (println "quickjs real btoa('') ->" (pr-str title))
                 (is (= "\"\"" title)
                     (str "expected btoa('') to be the empty string, got " (pr-str title)))
                 (done)))
        (.catch (fn [err]
                  (is false (str "QuickJS WASM engine initialization / page load failed: "
                                 (or (.-message err) err)))
                  (done))))))

(deftest quickjs-real-btoa-throws-on-non-latin1-character-test
  (async done
    (-> (run-page-and-read-title!
         {:html (str "<script>"
                     "try { btoa('こんにちは'); document.title = 'no-throw'; }"
                     "catch (e) { document.title = 'threw'; }"
                     "</script>")})
        (.then (fn [title]
                 (println "quickjs real btoa() on a non-Latin1 string ->" (pr-str title))
                 (is (= "threw" title)
                     (str "expected btoa() to throw on a character outside the Latin1 range, got "
                          (pr-str title)))
                 (done)))
        (.catch (fn [err]
                  (is false (str "QuickJS WASM engine initialization / page load failed: "
                                 (or (.-message err) err)))
                  (done))))))

(deftest quickjs-real-atob-throws-on-malformed-input-test
  (async done
    (-> (run-page-and-read-title!
         {:html (str "<script>"
                     "try { atob('not valid base64!!'); document.title = 'no-throw'; }"
                     "catch (e) { document.title = 'threw'; }"
                     "</script>")})
        (.then (fn [title]
                 (println "quickjs real atob() on malformed input ->" (pr-str title))
                 (is (= "threw" title)
                     (str "expected atob() to throw on malformed base64 input, got " (pr-str title)))
                 (done)))
        (.catch (fn [err]
                  (is false (str "QuickJS WASM engine initialization / page load failed: "
                                 (or (.-message err) err)))
                  (done))))))
