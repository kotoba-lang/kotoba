(ns browser.compat.quickjs-local-storage-length-key-clear-smoke-test
  "Real page-script round-trip proof that localStorage.length/.key(n)/
  .clear() -- previously entirely missing (only getItem/setItem/
  removeItem existed on the shim) -- now work through actual QuickJS
  WASM end-to-end, reusing the already-real __kotobaStorageSnapshot the
  engine already installs before each script evaluates."
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
                                                {:url "kotoba://local-storage-length-key-clear-round-trip"
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

(deftest quickjs-real-local-storage-length-and-key-after-two-writes-test
  (async done
    (-> (run-page-and-read-title!
         {:html (str "<script>"
                     "localStorage.setItem('alpha', '1');"
                     "localStorage.setItem('beta', '2');"
                     "</script>"
                     "<script>"
                     "document.title = localStorage.length + ':' + localStorage.key(0) + ':' + "
                     "localStorage.key(1) + ':' + localStorage.key(2);"
                     "</script>")})
        (.then (fn [title]
                 (println "quickjs real localStorage.length/.key() after two writes ->" (pr-str title))
                 (is (= "2:alpha:beta:null" title)
                     (str "expected length=2 and key(0)/key(1) to return the two real keys in sorted "
                          "order, key(2) (out of bounds) to return null, got " (pr-str title)))
                 (done)))
        (.catch (fn [err]
                  (is false (str "QuickJS WASM engine initialization / page load failed: "
                                 (or (.-message err) err)))
                  (done))))))

(deftest quickjs-real-local-storage-length-is-zero-when-empty-test
  (async done
    (-> (run-page-and-read-title!
         {:html (str "<script>"
                     "document.title = localStorage.length + ':' + localStorage.key(0);"
                     "</script>")})
        (.then (fn [title]
                 (println "quickjs real localStorage.length on an empty store ->" (pr-str title))
                 (is (= "0:null" title)
                     (str "expected a real empty localStorage to report length 0 and key(0) === null, "
                          "got " (pr-str title)))
                 (done)))
        (.catch (fn [err]
                  (is false (str "QuickJS WASM engine initialization / page load failed: "
                                 (or (.-message err) err)))
                  (done))))))

(deftest quickjs-real-local-storage-clear-removes-every-real-key-test
  (async done
    (-> (run-page-and-read-title!
         {:html (str "<script>"
                     "localStorage.setItem('alpha', '1');"
                     "localStorage.setItem('beta', '2');"
                     "</script>"
                     "<script>"
                     "localStorage.clear();"
                     "</script>"
                     "<script>"
                     "document.title = localStorage.length + ':' + localStorage.getItem('alpha') + ':' + "
                     "localStorage.getItem('beta');"
                     "</script>")})
        (.then (fn [title]
                 (println "quickjs real localStorage.clear() then re-read ->" (pr-str title))
                 (is (= "0:null:null" title)
                     (str "expected clear() to remove every real key set earlier on the same page, "
                          "got " (pr-str title)))
                 (done)))
        (.catch (fn [err]
                  (is false (str "QuickJS WASM engine initialization / page load failed: "
                                 (or (.-message err) err)))
                  (done))))))
