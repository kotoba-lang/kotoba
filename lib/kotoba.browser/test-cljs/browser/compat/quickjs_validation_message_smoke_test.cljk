(ns browser.compat.quickjs-validation-message-smoke-test
  "Real page-script round-trip proof that `element.validationMessage` --
  previously entirely missing (a repo-wide grep for `validationMessage`
  returned zero matches anywhere) -- now works through actual QuickJS WASM
  end-to-end, reusing the same 8-reason constraint-validation logic already
  computed for `.validity`/`checkValidity()`."
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
                                                {:url "kotoba://validation-message-round-trip"
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

(deftest quickjs-real-validation-message-is-blank-for-a-valid-control-test
  (async done
    (-> (run-page-and-read-title!
         {:html (str "<input id=\"note\" required value=\"hello\">"
                     "<script>"
                     "var note = document.getElementById('note');"
                     "document.title = JSON.stringify(note.validationMessage);"
                     "</script>")})
        (.then (fn [title]
                 (println "quickjs real .validationMessage on a filled required input ->" (pr-str title))
                 (is (= "\"\"" title)
                     (str "expected a valid control's validationMessage to be the empty string, got "
                          (pr-str title)))
                 (done)))
        (.catch (fn [err]
                  (is false (str "QuickJS WASM engine initialization / page load failed: "
                                 (or (.-message err) err)))
                  (done))))))

(deftest quickjs-real-validation-message-reports-value-missing-test
  (async done
    (-> (run-page-and-read-title!
         {:html (str "<input id=\"note\" required>"
                     "<script>"
                     "var note = document.getElementById('note');"
                     "document.title = note.validationMessage;"
                     "</script>")})
        (.then (fn [title]
                 (println "quickjs real .validationMessage on a blank required input ->" (pr-str title))
                 (is (= "Please fill out this field." title)
                     (str "expected a blank required input's validationMessage to describe the missing "
                          "value, got " (pr-str title)))
                 (done)))
        (.catch (fn [err]
                  (is false (str "QuickJS WASM engine initialization / page load failed: "
                                 (or (.-message err) err)))
                  (done))))))

(deftest quickjs-real-validation-message-reports-type-mismatch-for-email-test
  (async done
    (-> (run-page-and-read-title!
         {:html (str "<input id=\"note\" type=\"email\" value=\"not-an-email\">"
                     "<script>"
                     "var note = document.getElementById('note');"
                     "document.title = note.validationMessage;"
                     "</script>")})
        (.then (fn [title]
                 (println "quickjs real .validationMessage on an invalid email input ->" (pr-str title))
                 (is (= "Please enter a valid email address." title)
                     (str "expected an invalid email input's validationMessage to name the email format, "
                          "got " (pr-str title)))
                 (done)))
        (.catch (fn [err]
                  (is false (str "QuickJS WASM engine initialization / page load failed: "
                                 (or (.-message err) err)))
                  (done))))))

(deftest quickjs-real-validation-message-is-blank-for-a-disabled-control-test
  (async done
    (-> (run-page-and-read-title!
         {:html (str "<input id=\"note\" required disabled>"
                     "<script>"
                     "var note = document.getElementById('note');"
                     "document.title = JSON.stringify(note.validationMessage);"
                     "</script>")})
        (.then (fn [title]
                 (println "quickjs real .validationMessage on a disabled required input ->" (pr-str title))
                 (is (= "\"\"" title)
                     (str "expected a disabled control (never a validation candidate) to have a blank "
                          "validationMessage regardless of its own blank required value, got "
                          (pr-str title)))
                 (done)))
        (.catch (fn [err]
                  (is false (str "QuickJS WASM engine initialization / page load failed: "
                                 (or (.-message err) err)))
                  (done))))))
