(ns browser.compat.quickjs-click-radio-activation-smoke-test
  "Real page-script round-trip proof that scripted `element.click()` and the
  `.checked =` IDL setter run real checkbox/radio activation semantics --
  previously `.click()` only dispatched a bare `click` event (no
  checked-toggle, no radio-group exclusivity, no input/change events), and
  the `.checked =` setter never cleared sibling radios in the same group --
  both a real, user-visible gap versus the ALREADY-correct real pointer-click
  path in `document_input.cljc`, confirmed via actual QuickJS WASM, not a
  JVM stand-in."
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
  [html]
  (js/Promise.
   (fn [resolve reject]
     (let [url "https://app.example/click-radio-activation-round-trip"
           fetch-fn (canned-fetch-fn {url html})
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

(deftest quickjs-real-checkbox-click-toggles-checked-and-fires-input-change-test
  (async done
    (-> (run-page-and-read-title!
         (str "<main><input id=\"box\" type=\"checkbox\">"
              "<script>"
              "var box = document.getElementById('box');"
              "var events = [];"
              "box.addEventListener('input', function() { events.push('input'); });"
              "box.addEventListener('change', function() { events.push('change'); });"
              "box.click();"
              "document.title = box.checked + ':' + events.join(',');"
              "</script></main>"))
        (.then (fn [title]
                 (println "quickjs real checkbox click toggle+events ->" (pr-str title))
                 (is (= "true:input,change" title)
                     (str "expected click() to toggle checked to true and fire input then "
                          "change, got document.title = " (pr-str title)))
                 (done)))
        (.catch (fn [err]
                  (is false (str "QuickJS WASM engine initialization / page load failed: "
                                 (or (.-message err) err)))
                  (done))))))

(deftest quickjs-real-checkbox-click-twice-toggles-back-off-test
  (async done
    (-> (run-page-and-read-title!
         (str "<main><input id=\"box\" type=\"checkbox\" checked>"
              "<script>"
              "var box = document.getElementById('box');"
              "box.click();"
              "box.click();"
              "document.title = String(box.checked);"
              "</script></main>"))
        (.then (fn [title]
                 (println "quickjs real checkbox double-click ->" (pr-str title))
                 (is (= "true" title)
                     (str "two clicks on an initially-checked checkbox must toggle off "
                          "then back on, got document.title = " (pr-str title)))
                 (done)))
        (.catch (fn [err]
                  (is false (str "QuickJS WASM engine initialization / page load failed: "
                                 (or (.-message err) err)))
                  (done))))))

(deftest quickjs-real-radio-click-checks-target-and-clears-group-siblings-test
  (async done
    (-> (run-page-and-read-title!
         (str "<main>"
              "<input id=\"a\" type=\"radio\" name=\"g\" checked>"
              "<input id=\"b\" type=\"radio\" name=\"g\">"
              "<script>"
              "var a = document.getElementById('a');"
              "var b = document.getElementById('b');"
              "var events = [];"
              "b.addEventListener('input', function() { events.push('input'); });"
              "b.addEventListener('change', function() { events.push('change'); });"
              "b.click();"
              "document.title = a.checked + ':' + b.checked + ':' + events.join(',');"
              "</script></main>"))
        (.then (fn [title]
                 (println "quickjs real radio click exclusivity+events ->" (pr-str title))
                 (is (= "false:true:input,change" title)
                     (str "expected clicking radio b to check it AND uncheck sibling a, "
                          "firing input/change on b, got document.title = " (pr-str title)))
                 (done)))
        (.catch (fn [err]
                  (is false (str "QuickJS WASM engine initialization / page load failed: "
                                 (or (.-message err) err)))
                  (done))))))

(deftest quickjs-real-radio-click-on-already-checked-radio-is-a-no-op-test
  (async done
    (-> (run-page-and-read-title!
         (str "<main>"
              "<input id=\"a\" type=\"radio\" name=\"g\" checked>"
              "<script>"
              "var a = document.getElementById('a');"
              "var events = [];"
              "a.addEventListener('input', function() { events.push('input'); });"
              "a.addEventListener('change', function() { events.push('change'); });"
              "a.click();"
              "document.title = a.checked + ':' + events.length;"
              "</script></main>"))
        (.then (fn [title]
                 (println "quickjs real radio click already-checked no-op ->" (pr-str title))
                 (is (= "true:0" title)
                     (str "clicking an already-checked radio must stay checked and fire NO "
                          "input/change (no state change), got document.title = " (pr-str title)))
                 (done)))
        (.catch (fn [err]
                  (is false (str "QuickJS WASM engine initialization / page load failed: "
                                 (or (.-message err) err)))
                  (done))))))

(deftest quickjs-real-radio-checked-setter-clears-group-siblings-test
  (async done
    (-> (run-page-and-read-title!
         (str "<main>"
              "<input id=\"a\" type=\"radio\" name=\"g\" checked>"
              "<input id=\"b\" type=\"radio\" name=\"g\">"
              "<script>"
              "var a = document.getElementById('a');"
              "var b = document.getElementById('b');"
              "b.checked = true;"
              "document.title = a.checked + ':' + b.checked;"
              "</script></main>"))
        (.then (fn [title]
                 (println "quickjs real radio .checked= setter exclusivity ->" (pr-str title))
                 (is (= "false:true" title)
                     (str "setting b.checked = true must clear sibling a's checked state too, "
                          "matching real browser behavior, got document.title = " (pr-str title)))
                 (done)))
        (.catch (fn [err]
                  (is false (str "QuickJS WASM engine initialization / page load failed: "
                                 (or (.-message err) err)))
                  (done))))))

(deftest quickjs-real-disabled-checkbox-click-does-not-toggle-checked-test
  (async done
    (-> (run-page-and-read-title!
         (str "<main><input id=\"box\" type=\"checkbox\" disabled>"
              "<script>"
              "var box = document.getElementById('box');"
              "box.click();"
              "document.title = String(box.checked);"
              "</script></main>"))
        (.then (fn [title]
                 (println "quickjs real disabled checkbox click no-op ->" (pr-str title))
                 (is (= "false" title)
                     (str "click() on a disabled checkbox must not toggle checked, "
                          "got document.title = " (pr-str title)))
                 (done)))
        (.catch (fn [err]
                  (is false (str "QuickJS WASM engine initialization / page load failed: "
                                 (or (.-message err) err)))
                  (done))))))

(deftest quickjs-real-checkbox-click-dispatches-click-before-input-and-change-test
  ;; Real Chrome/Firefox order: checked flips synchronously as part of
  ;; pre-click activation, click fires NEXT, and only afterward do
  ;; input/change fire -- previously this fired input/change BEFORE click.
  (async done
    (-> (run-page-and-read-title!
         (str "<main><input id=\"box\" type=\"checkbox\">"
              "<script>"
              "var box = document.getElementById('box');"
              "var events = [];"
              "box.addEventListener('click', function() { events.push('click'); });"
              "box.addEventListener('input', function() { events.push('input'); });"
              "box.addEventListener('change', function() { events.push('change'); });"
              "box.click();"
              "document.title = events.join(',');"
              "</script></main>"))
        (.then (fn [title]
                 (println "quickjs real checkbox click order ->" (pr-str title))
                 (is (= "click,input,change" title)
                     (str "click must fire before input, which must fire before change, "
                          "got document.title = " (pr-str title)))
                 (done)))
        (.catch (fn [err]
                  (is false (str "QuickJS WASM engine initialization / page load failed: "
                                 (or (.-message err) err)))
                  (done))))))


(deftest quickjs-real-checkbox-click-preventdefault-reverts-checked-and-suppresses-events-test
  ;; Real "canceled activation steps": a click listener calling
  ;; preventDefault() reverts the tentative checked flip and fires NEITHER
  ;; input nor change -- previously this engine always kept the flip and
  ;; always fired both regardless of preventDefault().
  (async done
    (-> (run-page-and-read-title!
         (str "<main><input id=\"box\" type=\"checkbox\">"
              "<script>"
              "var box = document.getElementById('box');"
              "var events = [];"
              "box.addEventListener('click', function(e) { e.preventDefault(); });"
              "box.addEventListener('input', function() { events.push('input'); });"
              "box.addEventListener('change', function() { events.push('change'); });"
              "box.click();"
              "document.title = box.checked + ':' + events.join(',');"
              "</script></main>"))
        (.then (fn [title]
                 (println "quickjs real checkbox click preventDefault ->" (pr-str title))
                 (is (= "false:" title)
                     (str "preventDefault() must revert checked to false and fire no "
                          "input/change, got document.title = " (pr-str title)))
                 (done)))
        (.catch (fn [err]
                  (is false (str "QuickJS WASM engine initialization / page load failed: "
                                 (or (.-message err) err)))
                  (done))))))

(deftest quickjs-real-radio-click-preventdefault-restores-previous-checked-sibling-test
  (async done
    (-> (run-page-and-read-title!
         (str "<main>"
              "<input id=\"a\" type=\"radio\" name=\"g\" checked>"
              "<input id=\"b\" type=\"radio\" name=\"g\">"
              "<script>"
              "var a = document.getElementById('a');"
              "var b = document.getElementById('b');"
              "var events = [];"
              "b.addEventListener('click', function(e) { e.preventDefault(); });"
              "b.addEventListener('input', function() { events.push('input'); });"
              "b.addEventListener('change', function() { events.push('change'); });"
              "b.click();"
              "document.title = a.checked + ':' + b.checked + ':' + events.join(',');"
              "</script></main>"))
        (.then (fn [title]
                 (println "quickjs real radio click preventDefault ->" (pr-str title))
                 (is (= "true:false:" title)
                     (str "preventDefault() must restore the previously-checked sibling "
                          "and fire no input/change, got document.title = " (pr-str title)))
                 (done)))
        (.catch (fn [err]
                  (is false (str "QuickJS WASM engine initialization / page load failed: "
                                 (or (.-message err) err)))
                  (done))))))

(deftest quickjs-real-radio-checked-setter-does-not-clear-sibling-in-a-different-form-test
  ;; Real spec: same-named radios are only a mutually-exclusive group
  ;; when they share the same OWNER FORM -- previously this shim
  ;; compared the raw form= attribute STRING directly (String(null) for
  ;; both, the common nested-in-a-<form> case with no explicit form=
  ;; attribute at all), so two same-named radios in DIFFERENT <form>
  ;; elements were wrongly merged into one group.
  (async done
    (-> (run-page-and-read-title!
         (str "<main>"
              "<form><input id=\"a\" type=\"radio\" name=\"g\" checked></form>"
              "<form><input id=\"b\" type=\"radio\" name=\"g\"></form>"
              "<script>"
              "var a = document.getElementById('a');"
              "var b = document.getElementById('b');"
              "b.checked = true;"
              "document.title = a.checked + ':' + b.checked;"
              "</script></main>"))
        (.then (fn [title]
                 (println "quickjs real radio cross-form independence ->" (pr-str title))
                 (is (= "true:true" title)
                     (str "setting b.checked = true must NOT clear sibling a's checked "
                          "state -- a and b are in DIFFERENT forms, so they are independent "
                          "groups, got document.title = " (pr-str title)))
                 (done)))
        (.catch (fn [err]
                  (is false (str "QuickJS WASM engine initialization / page load failed: "
                                 (or (.-message err) err)))
                  (done))))))

(deftest quickjs-real-nameless-radios-are-independent-not-a-mutually-exclusive-group-test
  ;; Real spec: a radio with NO name is its own singleton group --
  ;; previously String(undefined name) collapsed to the literal string
  ;; "null" for every nameless radio, so unrelated nameless radios
  ;; anywhere on the page wrongly cleared each other's checkedness.
  (async done
    (-> (run-page-and-read-title!
         (str "<main>"
              "<input id=\"a\" type=\"radio\" checked>"
              "<input id=\"b\" type=\"radio\">"
              "<script>"
              "var a = document.getElementById('a');"
              "var b = document.getElementById('b');"
              "b.checked = true;"
              "document.title = a.checked + ':' + b.checked;"
              "</script></main>"))
        (.then (fn [title]
                 (println "quickjs real nameless radio independence ->" (pr-str title))
                 (is (= "true:true" title)
                     (str "setting b.checked = true must NOT clear sibling a's checked "
                          "state -- neither radio has a name, so each is its own "
                          "independent group, got document.title = " (pr-str title)))
                 (done)))
        (.catch (fn [err]
                  (is false (str "QuickJS WASM engine initialization / page load failed: "
                                 (or (.-message err) err)))
                  (done))))))


