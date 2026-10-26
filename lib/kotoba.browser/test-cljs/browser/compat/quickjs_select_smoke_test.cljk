(ns browser.compat.quickjs-select-smoke-test
  "Real page-script round-trip proof that `HTMLInputElement`/
  `HTMLTextAreaElement.select()` -- previously entirely missing (a
  repo-wide grep for a `select:` method on the generic element wrapper
  returned nothing, only the unrelated `<select>` tag/option-list
  machinery) -- now works through actual QuickJS WASM end-to-end,
  reusing the already-real `setSelectionRange`."
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
                                                {:url "kotoba://select-round-trip"
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

(deftest quickjs-real-input-select-selects-all-of-its-own-text-test
  (async done
    (-> (run-page-and-read-title!
         {:html (str "<input id=\"note\" value=\"hello world\">"
                     "<script>"
                     "var note = document.getElementById('note');"
                     "note.select();"
                     "document.title = note.selectionStart + ':' + note.selectionEnd;"
                     "</script>")})
        (.then (fn [title]
                 (println "quickjs real input.select() ->" (pr-str title))
                 (is (= "0:11" title)
                     (str "expected select() to select the whole 11-character value (indices 0 to "
                          "11), got " (pr-str title)))
                 (done)))
        (.catch (fn [err]
                  (is false (str "QuickJS WASM engine initialization / page load failed: "
                                 (or (.-message err) err)))
                  (done))))))

(deftest quickjs-real-textarea-select-selects-all-of-its-own-text-test
  (async done
    (-> (run-page-and-read-title!
         {:html (str "<textarea id=\"note\">hi</textarea>"
                     "<script>"
                     "var note = document.getElementById('note');"
                     "note.select();"
                     "document.title = note.selectionStart + ':' + note.selectionEnd;"
                     "</script>")})
        (.then (fn [title]
                 (println "quickjs real textarea.select() ->" (pr-str title))
                 (is (= "0:2" title)
                     (str "expected select() to select the whole 2-character textarea value, got "
                          (pr-str title)))
                 (done)))
        (.catch (fn [err]
                  (is false (str "QuickJS WASM engine initialization / page load failed: "
                                 (or (.-message err) err)))
                  (done))))))

(deftest quickjs-real-set-selection-range-reaches-the-real-document-attrs-test
  ;; The other tests in this file only check the JS-FACING .selectionStart/
  ;; .selectionEnd getters after select()/setSelectionRange() -- which the
  ;; bug this test guards did NOT break, since the getter read the very
  ;; (private, non-attribute) field the setter wrote, self-consistently.
  ;; The real bug was that the REAL document's own :selection-start/
  ;; :selection-end attrs never updated at all -- getAttribute('selection-
  ;; start') genuinely reads through __kotobaAttr (the real attrs map,
  ;; already proven correct for every OTHER attribute in this shim), so
  ;; this is a real, executable proof that setSelectionRange now reaches
  ;; the real document, not just the JS-facing property round-trip.
  (async done
    (-> (run-page-and-read-title!
         {:html (str "<input id=\"note\" value=\"hello world\">"
                     "<script>"
                     "var note = document.getElementById('note');"
                     "note.setSelectionRange(2, 7);"
                     "document.title = note.getAttribute('selection-start') + ':' + "
                     "note.getAttribute('selection-end');"
                     "</script>")})
        (.then (fn [title]
                 (println "quickjs real setSelectionRange -> real document attrs:" (pr-str title))
                 (is (= "2:7" title)
                     (str "expected setSelectionRange(2, 7) to actually write the real "
                          "document's own selection-start/selection-end attrs, got "
                          (pr-str title) " (nil:nil would mean the bug is back)"))
                 (done)))
        (.catch (fn [err]
                  (is false (str "QuickJS WASM engine initialization / page load failed: "
                                 (or (.-message err) err)))
                  (done))))))

(deftest quickjs-real-selection-getters-clamp-after-a-shorter-value-is-set-test
  ;; The JS-FACING .selectionStart/.selectionEnd GETTERS themselves
  ;; (distinct from the real-document-attrs proof above) previously read
  ;; the raw selection-start/selection-end attrs with no clamp against
  ;; the CURRENT value's own length. set value(value) has no spec-
  ;; mandated selection-reset, so selecting a range then setting a
  ;; SHORTER value left these getters reporting offsets exceeding the
  ;; new value's own length -- the literal HTMLInputElement DOM contract
  ;; every real browser clamps to [0, value.length], and the actual API
  ;; surface a page script (or the browser-use AI-agent adapter) reads
  ;; to reason about cursor/selection position.
  (async done
    (-> (run-page-and-read-title!
         {:html (str "<input id=\"note\" value=\"hello world\">"
                     "<script>"
                     "var note = document.getElementById('note');"
                     "note.setSelectionRange(6, 11);"
                     "note.value = 'hi';"
                     "document.title = note.selectionStart + ':' + note.selectionEnd + "
                     "':' + JSON.stringify(note.value.slice(note.selectionStart, note.selectionEnd));"
                     "</script>")})
        (.then (fn [title]
                 (println "quickjs real selectionStart/End after a shorter value is set:" (pr-str title))
                 (is (= "2:2:\"\"" title)
                     (str "expected selectionStart/selectionEnd to clamp to the new 2-character "
                          "value's own length (not the stale 6:11 from before the value change), "
                          "got " (pr-str title)))
                 (done)))
        (.catch (fn [err]
                  (is false (str "QuickJS WASM engine initialization / page load failed: "
                                 (or (.-message err) err)))
                  (done))))))

(deftest quickjs-real-select-on-an-empty-input-selects-nothing-not-a-crash-test
  (async done
    (-> (run-page-and-read-title!
         {:html (str "<input id=\"note\">"
                     "<script>"
                     "var note = document.getElementById('note');"
                     "note.select();"
                     "document.title = note.selectionStart + ':' + note.selectionEnd;"
                     "</script>")})
        (.then (fn [title]
                 (println "quickjs real select() on an empty input ->" (pr-str title))
                 (is (= "0:0" title)
                     (str "expected select() on an empty input to select an empty range, not "
                          "crash, got " (pr-str title)))
                 (done)))
        (.catch (fn [err]
                  (is false (str "QuickJS WASM engine initialization / page load failed: "
                                 (or (.-message err) err)))
                  (done))))))
