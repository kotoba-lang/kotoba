(ns browser.compat.quickjs-step-up-down-smoke-test
  "Real page-script round-trip proof that HTMLInputElement.stepUp()/
  .stepDown() -- previously entirely missing (a repo-wide grep for
  `stepUp`/`stepDown` returned zero matches anywhere) -- now work through
  actual QuickJS WASM end-to-end, reusing the same step/min/max attribute
  reading already established by __kotobaStepMismatch."
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
                                                {:url "kotoba://step-up-down-round-trip"
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

(deftest quickjs-real-step-up-increments-by-step-test
  (async done
    (-> (run-page-and-read-title!
         {:html (str "<input id=\"note\" type=\"number\" value=\"5\" step=\"2\">"
                     "<script>"
                     "var note = document.getElementById('note');"
                     "note.stepUp();"
                     "document.title = note.value;"
                     "</script>")})
        (.then (fn [title]
                 (println "quickjs real stepUp() on value=5 step=2 ->" (pr-str title))
                 (is (= "7" title)
                     (str "expected stepUp() to increment value 5 by step 2 to 7, got " (pr-str title)))
                 (done)))
        (.catch (fn [err]
                  (is false (str "QuickJS WASM engine initialization / page load failed: "
                                 (or (.-message err) err)))
                  (done))))))

(deftest quickjs-real-step-down-decrements-by-step-test
  (async done
    (-> (run-page-and-read-title!
         {:html (str "<input id=\"note\" type=\"number\" value=\"5\" step=\"2\">"
                     "<script>"
                     "var note = document.getElementById('note');"
                     "note.stepDown();"
                     "document.title = note.value;"
                     "</script>")})
        (.then (fn [title]
                 (println "quickjs real stepDown() on value=5 step=2 ->" (pr-str title))
                 (is (= "3" title)
                     (str "expected stepDown() to decrement value 5 by step 2 to 3, got " (pr-str title)))
                 (done)))
        (.catch (fn [err]
                  (is false (str "QuickJS WASM engine initialization / page load failed: "
                                 (or (.-message err) err)))
                  (done))))))

(deftest quickjs-real-step-up-clamps-to-max-test
  (async done
    (-> (run-page-and-read-title!
         {:html (str "<input id=\"note\" type=\"number\" value=\"9\" max=\"10\" step=\"2\">"
                     "<script>"
                     "var note = document.getElementById('note');"
                     "note.stepUp();"
                     "document.title = note.value;"
                     "</script>")})
        (.then (fn [title]
                 (println "quickjs real stepUp() clamped to max ->" (pr-str title))
                 (is (= "10" title)
                     (str "expected stepUp() past max=10 to clamp to 10, got " (pr-str title)))
                 (done)))
        (.catch (fn [err]
                  (is false (str "QuickJS WASM engine initialization / page load failed: "
                                 (or (.-message err) err)))
                  (done))))))

(deftest quickjs-real-step-up-with-no-value-starts-from-min-test
  (async done
    (-> (run-page-and-read-title!
         {:html (str "<input id=\"note\" type=\"number\" min=\"0\" step=\"1\">"
                     "<script>"
                     "var note = document.getElementById('note');"
                     "note.stepUp();"
                     "document.title = note.value;"
                     "</script>")})
        (.then (fn [title]
                 (println "quickjs real stepUp() with no value, min=0 ->" (pr-str title))
                 (is (= "1" title)
                     (str "expected stepUp() on a blank control to start from its min (0) and step to 1, "
                          "got " (pr-str title)))
                 (done)))
        (.catch (fn [err]
                  (is false (str "QuickJS WASM engine initialization / page load failed: "
                                 (or (.-message err) err)))
                  (done))))))

(deftest quickjs-real-step-up-with-step-any-is-a-no-op-test
  (async done
    (-> (run-page-and-read-title!
         {:html (str "<input id=\"note\" type=\"number\" value=\"1\" step=\"any\">"
                     "<script>"
                     "var note = document.getElementById('note');"
                     "note.stepUp();"
                     "document.title = note.value;"
                     "</script>")})
        (.then (fn [title]
                 (println "quickjs real stepUp() with step=any ->" (pr-str title))
                 (is (= "1" title)
                     (str "expected stepUp() on a step=\"any\" control to be a no-op (honest scope-cut "
                          "vs. real InvalidStateError, no DOMException type exists in this engine), got "
                          (pr-str title)))
                 (done)))
        (.catch (fn [err]
                  (is false (str "QuickJS WASM engine initialization / page load failed: "
                                 (or (.-message err) err)))
                  (done))))))

(deftest quickjs-real-step-up-with-explicit-multiplier-test
  (async done
    (-> (run-page-and-read-title!
         {:html (str "<input id=\"note\" type=\"number\" value=\"5\" step=\"2\">"
                     "<script>"
                     "var note = document.getElementById('note');"
                     "note.stepUp(3);"
                     "document.title = note.value;"
                     "</script>")})
        (.then (fn [title]
                 (println "quickjs real stepUp(3) on value=5 step=2 ->" (pr-str title))
                 (is (= "11" title)
                     (str "expected stepUp(3) to increment value 5 by 3*step(2)=6 to 11, got " (pr-str title)))
                 (done)))
        (.catch (fn [err]
                  (is false (str "QuickJS WASM engine initialization / page load failed: "
                                 (or (.-message err) err)))
                  (done))))))
