(ns browser.compat.quickjs-check-validity-smoke-test
  "Real page-script round-trip proof that `element.checkValidity()`/
  `.reportValidity()`/`.validity`/`.willValidate` -- previously entirely
  missing (a repo-wide grep for `checkValidity`/`reportValidity`/
  `ValidityState`/`willValidate` returned zero JS-facing matches) -- now
  work through actual QuickJS WASM end-to-end, reusing the same
  constraint-validation reason logic already used for a real
  `element.matches(':invalid')`/`:valid` pseudo-class match."
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
                                                {:url "kotoba://check-validity-round-trip"
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

(deftest quickjs-real-check-validity-reports-invalid-for-a-blank-required-input-test
  (async done
    (-> (run-page-and-read-title!
         {:html (str "<input id=\"note\" required>"
                     "<script>"
                     "var note = document.getElementById('note');"
                     "document.title = note.checkValidity() + ':' + note.validity.valueMissing + ':' + note.validity.valid;"
                     "</script>")})
        (.then (fn [title]
                 (println "quickjs real checkValidity() on a blank required input ->" (pr-str title))
                 (is (= "false:true:false" title)
                     (str "expected a blank required input to be invalid, with .valueMissing true, got "
                          (pr-str title)))
                 (done)))
        (.catch (fn [err]
                  (is false (str "QuickJS WASM engine initialization / page load failed: "
                                 (or (.-message err) err)))
                  (done))))))

(deftest quickjs-real-check-validity-is-true-for-a-filled-required-input-test
  (async done
    (-> (run-page-and-read-title!
         {:html (str "<input id=\"note\" required value=\"hello\">"
                     "<script>"
                     "var note = document.getElementById('note');"
                     "document.title = note.checkValidity() + ':' + note.validity.valueMissing + ':' + note.validity.valid;"
                     "</script>")})
        (.then (fn [title]
                 (println "quickjs real checkValidity() on a filled required input ->" (pr-str title))
                 (is (= "true:false:true" title)
                     (str "expected a filled required input to be valid, got " (pr-str title)))
                 (done)))
        (.catch (fn [err]
                  (is false (str "QuickJS WASM engine initialization / page load failed: "
                                 (or (.-message err) err)))
                  (done))))))

(deftest quickjs-real-validity-reports-range-overflow-for-an-out-of-range-number-input-test
  (async done
    (-> (run-page-and-read-title!
         {:html (str "<input id=\"note\" type=\"number\" min=\"1\" max=\"10\" value=\"15\">"
                     "<script>"
                     "var note = document.getElementById('note');"
                     "document.title = note.validity.rangeOverflow + ':' + note.validity.valid + ':' + note.checkValidity();"
                     "</script>")})
        (.then (fn [title]
                 (println "quickjs real .validity.rangeOverflow on out-of-range number input ->" (pr-str title))
                 (is (= "true:false:false" title)
                     (str "expected an out-of-range number input to report rangeOverflow and be invalid, got "
                          (pr-str title)))
                 (done)))
        (.catch (fn [err]
                  (is false (str "QuickJS WASM engine initialization / page load failed: "
                                 (or (.-message err) err)))
                  (done))))))

(deftest quickjs-real-will-validate-is-false-for-a-disabled-control-test
  (async done
    (-> (run-page-and-read-title!
         {:html (str "<input id=\"note\" required disabled>"
                     "<script>"
                     "var note = document.getElementById('note');"
                     "document.title = note.willValidate + ':' + note.checkValidity() + ':' + note.validity.valid;"
                     "</script>")})
        (.then (fn [title]
                 (println "quickjs real .willValidate on a disabled required input ->" (pr-str title))
                 (is (= "false:true:true" title)
                     (str "expected a disabled control to never be a validation candidate -- "
                          "checkValidity()/.validity.valid must both report true regardless of its "
                          "own blank required value, got " (pr-str title)))
                 (done)))
        (.catch (fn [err]
                  (is false (str "QuickJS WASM engine initialization / page load failed: "
                                 (or (.-message err) err)))
                  (done))))))

(deftest quickjs-real-report-validity-focuses-the-control-when-invalid-test
  (async done
    (-> (run-page-and-read-title!
         {:html (str "<input id=\"note\" required>"
                     "<script>"
                     "var note = document.getElementById('note');"
                     "var result = note.reportValidity();"
                     "document.title = result + ':' + (document.activeElement === note);"
                     "</script>")})
        (.then (fn [title]
                 (println "quickjs real reportValidity() on a blank required input ->" (pr-str title))
                 (is (= "false:true" title)
                     (str "expected reportValidity() to return false and, as a best-effort substitute "
                          "for native validation-bubble UI, focus the invalid control, got " (pr-str title)))
                 (done)))
        (.catch (fn [err]
                  (is false (str "QuickJS WASM engine initialization / page load failed: "
                                 (or (.-message err) err)))
                  (done))))))
