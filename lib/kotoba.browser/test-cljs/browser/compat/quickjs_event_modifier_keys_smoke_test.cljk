(ns browser.compat.quickjs-event-modifier-keys-smoke-test
  "Real page-script round-trip proof that KeyboardEvent/MouseEvent modifier
  keys (shiftKey/ctrlKey/altKey/metaKey) -- previously silently dropped both
  by the two constructors (only key/code/repeat and button/clientX/clientY
  were copied from the init dict) and by the outbound __kotobaEventPayload
  builder used by dispatchEvent -- now work through actual QuickJS WASM
  end-to-end."
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
                                                {:url "kotoba://event-modifier-keys-round-trip"
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

(deftest quickjs-real-keyboard-event-modifier-keys-default-to-false-test
  (async done
    (-> (run-page-and-read-title!
         {:html (str "<script>"
                     "var e = new KeyboardEvent('keydown', {key: 'a'});"
                     "document.title = e.shiftKey + ':' + e.ctrlKey + ':' + e.altKey + ':' + e.metaKey;"
                     "</script>")})
        (.then (fn [title]
                 (println "quickjs real KeyboardEvent modifier defaults (none given) ->" (pr-str title))
                 (is (= "false:false:false:false" title)
                     (str "expected a KeyboardEvent with no modifier keys in its init dict to default "
                          "all four to real booleans (false), got " (pr-str title)))
                 (done)))
        (.catch (fn [err]
                  (is false (str "QuickJS WASM engine initialization / page load failed: "
                                 (or (.-message err) err)))
                  (done))))))

(deftest quickjs-real-keyboard-event-modifier-keys-read-back-when-set-test
  (async done
    (-> (run-page-and-read-title!
         {:html (str "<script>"
                     "var e = new KeyboardEvent('keydown', {key: 'a', shiftKey: true, ctrlKey: true});"
                     "document.title = e.shiftKey + ':' + e.ctrlKey + ':' + e.altKey + ':' + e.metaKey;"
                     "</script>")})
        (.then (fn [title]
                 (println "quickjs real KeyboardEvent modifier keys (shift+ctrl given) ->" (pr-str title))
                 (is (= "true:true:false:false" title)
                     (str "expected a KeyboardEvent constructed with shiftKey/ctrlKey true to read them "
                          "back true and the other two false, got " (pr-str title)))
                 (done)))
        (.catch (fn [err]
                  (is false (str "QuickJS WASM engine initialization / page load failed: "
                                 (or (.-message err) err)))
                  (done))))))

(deftest quickjs-real-mouse-event-modifier-keys-default-to-false-test
  (async done
    (-> (run-page-and-read-title!
         {:html (str "<script>"
                     "var e = new MouseEvent('click', {button: 0});"
                     "document.title = e.shiftKey + ':' + e.ctrlKey + ':' + e.altKey + ':' + e.metaKey;"
                     "</script>")})
        (.then (fn [title]
                 (println "quickjs real MouseEvent modifier defaults (none given) ->" (pr-str title))
                 (is (= "false:false:false:false" title)
                     (str "expected a MouseEvent with no modifier keys in its init dict to default all "
                          "four to real booleans (false), got " (pr-str title)))
                 (done)))
        (.catch (fn [err]
                  (is false (str "QuickJS WASM engine initialization / page load failed: "
                                 (or (.-message err) err)))
                  (done))))))

(deftest quickjs-real-dispatch-event-carries-modifier-keys-to-a-listener-test
  (async done
    (-> (run-page-and-read-title!
         {:html (str "<div id=\"target\"></div>"
                     "<script>"
                     "var target = document.getElementById('target');"
                     "var seen = null;"
                     "target.addEventListener('click', function(e) { seen = e.altKey + ':' + e.metaKey; });"
                     "target.dispatchEvent(new MouseEvent('click', {altKey: true, metaKey: true}));"
                     "document.title = seen;"
                     "</script>")})
        (.then (fn [title]
                 (println "quickjs real dispatchEvent modifier-key round-trip to a listener ->" (pr-str title))
                 (is (= "true:true" title)
                     (str "expected a listener receiving a dispatched MouseEvent to see its own "
                          "altKey/metaKey flags, got " (pr-str title)))
                 (done)))
        (.catch (fn [err]
                  (is false (str "QuickJS WASM engine initialization / page load failed: "
                                 (or (.-message err) err)))
                  (done))))))
