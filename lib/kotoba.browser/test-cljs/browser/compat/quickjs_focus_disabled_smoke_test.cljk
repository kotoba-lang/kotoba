(ns browser.compat.quickjs-focus-disabled-smoke-test
  "Real page-script round-trip proof that element.focus() -- previously
  entirely ignoring the disabled attribute, deferred across 18+ prior
  scoping passes as the safest trivial close-out -- is now correctly a
  no-op on a disabled form control, matching every other disabled-gated
  behavior in this same file (checkValidity/:disabled pseudo-class/etc.,
  all already reusing the same __kotobaDisabledControl helper)."
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
                                                {:url "kotoba://focus-disabled-round-trip"
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

(deftest quickjs-real-focus-is-a-no-op-on-a-disabled-control-test
  (async done
    (-> (run-page-and-read-title!
         {:html (str "<input id=\"note\" disabled>"
                     "<script>"
                     "var note = document.getElementById('note');"
                     "note.focus();"
                     "document.title = String(document.activeElement === note);"
                     "</script>")})
        (.then (fn [title]
                 (println "quickjs real focus() on a disabled input, document.activeElement === note ->"
                          (pr-str title))
                 (is (= "false" title)
                     (str "expected focus() on a disabled control to be a no-op -- "
                          "document.activeElement must NOT become the disabled control, got "
                          (pr-str title)))
                 (done)))
        (.catch (fn [err]
                  (is false (str "QuickJS WASM engine initialization / page load failed: "
                                 (or (.-message err) err)))
                  (done))))))

(deftest quickjs-real-focus-still-works-on-an-enabled-control-test
  (async done
    (-> (run-page-and-read-title!
         {:html (str "<input id=\"note\">"
                     "<script>"
                     "var note = document.getElementById('note');"
                     "note.focus();"
                     "document.title = String(document.activeElement === note);"
                     "</script>")})
        (.then (fn [title]
                 (println "quickjs real focus() on an enabled input, document.activeElement === note ->"
                          (pr-str title))
                 (is (= "true" title)
                     (str "expected focus() on a real, ENABLED control to still work, got "
                          (pr-str title)))
                 (done)))
        (.catch (fn [err]
                  (is false (str "QuickJS WASM engine initialization / page load failed: "
                                 (or (.-message err) err)))
                  (done))))))
