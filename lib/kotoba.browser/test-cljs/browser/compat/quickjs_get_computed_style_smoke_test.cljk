(ns browser.compat.quickjs-get-computed-style-smoke-test
  "Real page-script round-trip proof that `getComputedStyle(el)` --
  previously entirely missing (a repo-wide grep for `getComputedStyle`
  returned zero matches; calling it threw a real `TypeError`) -- now
  works through actual QuickJS WASM end-to-end, reusing the SAME
  cascade-computed `:style/<prop>` attr lookups `element.style` already
  performs, so a PURE stylesheet rule (no inline override at all) is
  correctly reflected -- unlike `element.style`, which only reflects an
  element's own inline declaration.

  Uses `browser.session/load-html!`, NOT `navigate!`/a `:fetch-fn` page --
  `:css` is a fully separate argument from `:html` (see
  `browser.session/load-html!`'s own docstring), and `navigate!`'s
  fetch-fn-driven path has no way to supply a `:css` string at all, so a
  `<style>` tag embedded in that path's HTML would be silently inert."
  (:require [cljs.test :refer [deftest is async]]
            [browser.compat.quickjs-runner :as quickjs-runner]
            [browser.session :as session]
            [kotoba.wasm.host :as host]))

(defn- dispose-engine!
  [session]
  (when-let [engine (get-in session [:browser.session/script-engine :script-engine/engine])]
    (when-let [dispose (:quickjs.engine/dispose engine)]
      (dispose engine))))

(defn- run-styled-page-and-read-title!
  [{:keys [html css]}]
  (js/Promise.
   (fn [resolve reject]
     (let [h (host/recording-host)
           base-session (session/new-session (quickjs-runner/quickjs-session-opts {:host h}))]
       (-> (session/ensure-script-engine! base-session)
           (.then
            (fn [ready-session]
              (try
                (let [after (session/load-html! ready-session
                                                {:url "kotoba://get-computed-style-round-trip"
                                                 :html html
                                                 :css css})
                      title (get-in after [:browser.session/page :browser/title])]
                  (dispose-engine! after)
                  (resolve title))
                (catch :default e
                  (dispose-engine! ready-session)
                  (reject e)))))
           (.catch (fn [err]
                     (dispose-engine! base-session)
                     (reject err))))))))

(deftest quickjs-real-get-computed-style-reflects-a-pure-stylesheet-rule-with-no-inline-override-test
  (async done
    (-> (run-styled-page-and-read-title!
         {:css ".note { color: blue; font-weight: bold }"
          :html (str "<main><p id=\"note\" class=\"note\">Hello</p></main>"
                     "<script>"
                     "var note = document.getElementById('note');"
                     "var computed = getComputedStyle(note);"
                     "document.title = computed.color + ':' + computed.fontWeight + ':' + computed.getPropertyValue('font-weight');"
                     "</script>")})
        (.then (fn [title]
                 (println "quickjs real getComputedStyle() with no inline override ->" (pr-str title))
                 (is (= "blue:bold:bold" title)
                     (str "expected getComputedStyle to reflect the pure stylesheet rule (no inline "
                          "override at all), both via bare property access and getPropertyValue(), "
                          "got document.title = " (pr-str title)))
                 (done)))
        (.catch (fn [err]
                  (is false (str "QuickJS WASM engine initialization / page load failed: "
                                 (or (.-message err) err)))
                  (done))))))

(deftest quickjs-real-get-computed-style-is-genuinely-read-only-test
  ;; The returned Proxy has NO `set` trap at all, unlike element.style's
  ;; own writable Proxy -- an assignment attempt falls through to the
  ;; JS-default behavior (silently setting an inert own-property on the
  ;; Proxy's empty backing `{}` target), but the `get` trap NEVER
  ;; consults that backing object -- it always re-derives fresh from the
  ;; real node's own cascade-computed :style/<prop> attr. So the
  ;; assignment doesn't just fail to reach the real element (the minimum
  ;; bar for "read-only"); re-reading the SAME computed-style object
  ;; afterwards still reports the untouched original value too.
  (async done
    (-> (run-styled-page-and-read-title!
         {:css ".note { color: blue }"
          :html (str "<main><p id=\"note\" class=\"note\">Hello</p></main>"
                     "<script>"
                     "var note = document.getElementById('note');"
                     "var computed = getComputedStyle(note);"
                     "computed.color = 'red';"
                     "document.title = computed.color + ':' + note.style.color + ':' + note.getAttribute('style');"
                     "</script>")})
        (.then (fn [title]
                 (println "quickjs real getComputedStyle() assignment attempt ->" (pr-str title))
                 (is (= "blue:blue:null" title)
                     (str "expected the assignment attempt to have ZERO effect -- re-reading the "
                          "SAME computed-style object still reports the real, untouched cascade "
                          "value, the real element's own element.style also stays unaffected, and "
                          "no real style attribute was ever written -- got document.title = "
                          (pr-str title)))
                 (done)))
        (.catch (fn [err]
                  (is false (str "QuickJS WASM engine initialization / page load failed: "
                                 (or (.-message err) err)))
                  (done))))))
