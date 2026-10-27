(ns browser.compat.quickjs-style-csstext-smoke-test
  "Real page-script round-trip proof that `element.style.cssText` now
   reads/writes the element's raw inline style TEXT instead of being
   treated as a fake property named `style/css-text` -- previously
   `el.style.cssText = 'color: red; font-size: 20px'` silently namespaced
   `cssText` as if it were a real CSS property (`__kotobaStyleAttrName`
   kebab-cases it to `style/css-text`), so the REAL declarations inside
   the string were never parsed or applied at all: `getComputedStyle(el)
   .color`/`.fontSize` stayed unset, confirmed via a temporary diagnostic
   test before touching source. Worse, the getter read the SAME fake
   attr back verbatim, so `el.style.cssText = x; el.style.cssText === x`
   would misleadingly appear to hold true even though the CSS effect
   never happened.

   Fixed by special-casing `cssText` to reuse the exact same, already-
   correct `setAttribute('style', ...)` path (the plain, un-namespaced
   `style` attr) instead of inventing a new one -- so this file follows
   `quickjs_style_property_smoke_test.cljs`'s own established pattern:
   `load-html!` with a real `:css` rule (not `navigate!`, which has no
   way to supply one -- see that file's own docstring for why an inert
   `:css` means a cascade recompute never actually runs between the two
   `<script>` tags' commits, silently making any test non-discriminating)."
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
                                                {:url "kotoba://style-csstext-round-trip"
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

(deftest quickjs-real-style-csstext-set-applies-the-real-declarations-test
  (async done
    (-> (run-styled-page-and-read-title!
         {:css "body { margin: 0 }"
          :html (str "<main><p id=\"note\">Hello</p></main>"
                     "<script>"
                     "document.getElementById('note').style.cssText = 'color: red; font-size: 20px';"
                     "</script>"
                     "<script>"
                     "var cs = getComputedStyle(document.getElementById('note'));"
                     "document.title = 'color=' + cs.color + '|fontSize=' + cs.fontSize;"
                     "</script>")})
        (.then (fn [title]
                 (println "quickjs real style.cssText set applies real declarations ->" (pr-str title))
                 (is (= "color=red|fontSize=20" title)
                     (str "expected cssText's declarations to actually reach the cascade, "
                          "not be silently dropped as a fake property, got document.title = "
                          (pr-str title)))
                 (done)))
        (.catch (fn [err]
                  (is false (str "QuickJS WASM engine initialization / page load failed: "
                                 (or (.-message err) err)))
                  (done))))))

(deftest quickjs-real-style-csstext-get-reflects-the-raw-inline-text-test
  (async done
    (-> (run-styled-page-and-read-title!
         {:css "body { margin: 0 }"
          :html (str "<main><p id=\"note\">Hello</p></main>"
                     "<script>"
                     "document.getElementById('note').style.cssText = 'color: red';"
                     "</script>"
                     "<script>"
                     "var note = document.getElementById('note');"
                     "document.title = 'cssText=' + note.style.cssText + "
                     "'|getAttribute=' + note.getAttribute('style');"
                     "</script>")})
        (.then (fn [title]
                 (println "quickjs real style.cssText getter ->" (pr-str title))
                 (is (= "cssText=color: red|getAttribute=color: red" title)
                     (str "expected style.cssText to read back the same raw text "
                          "getAttribute('style') does, got document.title = " (pr-str title)))
                 (done)))
        (.catch (fn [err]
                  (is false (str "QuickJS WASM engine initialization / page load failed: "
                                 (or (.-message err) err)))
                  (done))))))

(deftest quickjs-real-style-csstext-survives-the-next-page-commits-cascade-recompute-test
  (async done
    (-> (run-styled-page-and-read-title!
         {:css ".note { color: blue }"
          :html (str "<main><p id=\"note\" class=\"note\">Hello</p></main>"
                     "<script>"
                     "document.getElementById('note').style.cssText = 'color: red';"
                     "</script>"
                     "<script>"
                     "document.title = document.getElementById('note').style.color;"
                     "</script>")})
        (.then (fn [title]
                 (println "quickjs real style.cssText set, across a commit boundary ->" (pr-str title))
                 (is (= "red" title)
                     (str "expected the cssText-set color to survive the cascade recompute "
                          "that runs between the two <script> tags' commits, got document.title = "
                          (pr-str title)))
                 (done)))
        (.catch (fn [err]
                  (is false (str "QuickJS WASM engine initialization / page load failed: "
                                 (or (.-message err) err)))
                  (done))))))
