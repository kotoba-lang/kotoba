(ns browser.compat.quickjs-style-property-smoke-test
  "Real page-script round-trip proof that an individual
  `element.style.<prop> = value` mutation -- previously silently reverted
  by the very next CSS cascade recompute on any page with a stylesheet,
  since it only ever touched the derived, cascade-computed `:style/<prop>`
  attr directly and never the `:style-inline` attr the cascade actually
  treats as authoritative input -- now survives through actual QuickJS
  WASM end-to-end, across a real page commit boundary (each `<script>` tag
  gets its own commit, with a real cascade recompute, before the next one
  runs).

  Uses `browser.session/load-html!`, NOT `navigate!`/a `:fetch-fn` page --
  `:css` is a fully separate argument from `:html` (`load-html!`'s own
  docstring: 'a `<style>` tag `:html` might literally contain is NOT
  auto-extracted'), and `navigate!`'s fetch-fn-driven path has no way to
  supply a `:css` string at all, so a `<style>` tag embedded in that path's
  HTML is silently inert -- confirmed the hard way while building this
  test: an earlier draft embedded `<style>` directly in `navigate!`'s HTML
  and both proof scripts kept passing even with the source fix fully
  reverted, since with no real `:css` at all `browser.core/render-document`
  skips `apply-cascade` entirely (`(seq css-rules)` false), so neither
  script ever exercised a real cascade recompute in the first place."
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
                                                {:url "kotoba://style-property-round-trip"
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

(deftest quickjs-real-individual-style-property-set-survives-the-next-page-commit-test
  (async done
    (-> (run-styled-page-and-read-title!
         {:css ".note { color: blue }"
          :html (str "<main><p id=\"note\" class=\"note\">Hello</p></main>"
                     "<script>"
                     "document.getElementById('note').style.color = 'red';"
                     "</script>"
                     "<script>"
                     "document.title = document.getElementById('note').style.color;"
                     "</script>")})
        (.then (fn [title]
                 (println "quickjs real style.color set, across a commit boundary ->" (pr-str title))
                 (is (= "red" title)
                     (str "expected the mutated color to survive the cascade recompute that "
                          "runs between the two <script> tags' commits, got document.title = "
                          (pr-str title)))
                 (done)))
        (.catch (fn [err]
                  (is false (str "QuickJS WASM engine initialization / page load failed: "
                                 (or (.-message err) err)))
                  (done))))))

(deftest quickjs-real-individual-style-property-remove-does-not-ghost-resurrect-on-the-next-commit-test
  ;; The precise, JS-observable failure mode this guards against: without
  ;; this fix, removeProperty only ever deleted the derived, literal
  ;; :style/color attr directly -- it never touched :style-inline (the
  ;; attr the cascade treats as authoritative input) -- so the very next
  ;; commit's cascade recompute would silently RESURRECT the "removed"
  ;; property right back from the still-populated :style-inline map. Real
  ;; browsers' CSSStyleDeclaration.color only ever reflects the INLINE
  ;; declaration (never a stylesheet's cascaded value -- that needs
  ;; getComputedStyle, not implemented here), so a stylesheet fallback
  ;; can't be observed this way -- but a ghost resurrection of an
  ;; explicitly-removed inline property absolutely can be. A `:css` rule
  ;; (even one matching nothing here) is required for `apply-cascade` to
  ;; run on the commit between the two <script> tags at all -- see this
  ;; namespace's own docstring.
  (async done
    (-> (run-styled-page-and-read-title!
         {:css "body { margin: 0 }"
          :html (str "<main><p id=\"note\" style=\"color: red\">Hello</p></main>"
                     "<script>"
                     "document.getElementById('note').style.removeProperty('color');"
                     "</script>"
                     "<script>"
                     "document.title = document.getElementById('note').style.color;"
                     "</script>")})
        (.then (fn [title]
                 (println "quickjs real style.removeProperty('color'), across a commit boundary ->" (pr-str title))
                 (is (= "" title)
                     (str "expected the removed property to STAY removed across the cascade "
                          "recompute that runs between the two <script> tags' commits (not "
                          "ghost-resurrect from a stale :style-inline), got document.title = "
                          (pr-str title)))
                 (done)))
        (.catch (fn [err]
                  (is false (str "QuickJS WASM engine initialization / page load failed: "
                                 (or (.-message err) err)))
                  (done))))))
