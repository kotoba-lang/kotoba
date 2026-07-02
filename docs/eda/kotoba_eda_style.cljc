(ns kotoba.eda.style
  "kotoba EDA Flow Workbench page CSS, as css.core EDN rule data — the
  page-authoring counterpart to kotoba.eda.ui's hiccup. Rendered to a CSS
  string via css.core/css (see kotoba-lang/css), the same EDN-to-CSS
  substrate liquid-glass-ui uses. This namespace owns exactly the ruleset
  that used to be the hand-typed <style> block in docs/eda/index.html —
  values are kept as literal strings (not bare numbers) so css.core's
  unitless-vs-px inference never has to guess.

  `rules` is a *vector* of `[selector decls]` pairs, not a map: Clojure map
  literals with more than 8 entries silently become PersistentHashMap, whose
  iteration order does not match source order — for ~60 selectors that would
  scramble CSS cascade order relative to the original hand-typed <style>
  block (same-specificity selectors are order-dependent). A vector guarantees
  `css.core/css` emits rules in exactly the order written here, which is the
  original page's source order."
  (:require [css.core :as css]))

(def root-vars
  {"--bg" "#f7f8fb"
   "--panel" "#ffffff"
   "--ink" "#172033"
   "--muted" "#667085"
   "--line" "#d7dce5"
   "--blue" "#2563eb"
   "--cyan" "#0891b2"
   "--green" "#16825d"
   "--amber" "#b45309"
   "--red" "#c2410c"
   "--violet" "#6d28d9"
   "--mono" "\"SFMono-Regular\", ui-monospace, Menlo, Consolas, monospace"
   "--sans" "system-ui, -apple-system, \"Hiragino Kaku Gothic ProN\", \"Noto Sans JP\", sans-serif"})

(def rules
  [[":root" root-vars]
   ["*" {:box-sizing "border-box"}]
   ["html" {:scroll-behavior "smooth"}]
   ["body" {:margin "0" :color "var(--ink)" :font-family "var(--sans)"
            :background "var(--bg)" :-webkit-font-smoothing "antialiased"}]
   ["a" {:color "var(--blue)" :text-decoration "none"}]
   ["a:hover" {:text-decoration "underline"}]
   ["code, pre, .mono" {:font-family "var(--mono)"}]
   ["nav" {:position "sticky" :top "0" :z-index "20"
           :border-bottom "1px solid var(--line)"
           :background "rgba(255,255,255,.92)" :backdrop-filter "blur(10px)"}]
   [".nav-inner" {:max-width "1360px" :margin "0 auto" :min-height "52px"
                  :display "flex" :align-items "center" :gap "18px" :padding "0 18px"}]
   [".brand" {:font-weight "760"}]
   [".nav-links" {:margin-left "auto" :display "flex" :gap "14px"
                  :flex-wrap "wrap" :font-size "13px"}]
   ["main" {:max-width "1360px" :margin "0 auto" :padding "18px"}]
   [".hero" {:display "grid" :grid-template-columns "1.2fr .8fr" :gap "18px"
             :align-items "stretch" :padding "18px 0 20px"}]
   ["h1" {:margin "0 0 8px" :font-size "clamp(28px, 4vw, 48px)"
          :line-height "1.08" :letter-spacing "0"}]
   ["h2" {:margin "0 0 10px" :font-size "18px"}]
   ["h3" {:margin "0 0 8px" :font-size "14px"}]
   ["p" {:margin "0" :color "var(--muted)" :line-height "1.6"}]
   [".panel, .tile, .stage, .log-row" {:background "var(--panel)"
                                        :border "1px solid var(--line)"
                                        :border-radius "8px"}]
   [".panel" {:padding "14px"}]
   [".hero .panel:first-child" {:display "flex" :flex-direction "column"
                                 :justify-content "center"}]
   [".badges" {:display "flex" :flex-wrap "wrap" :gap "8px" :margin "14px 0 0"}]
   [".badge" {:border "1px solid var(--line)" :border-radius "999px"
              :padding "4px 9px" :background "#fff" :color "var(--muted)"
              :font "12px/1.2 var(--mono)"}]
   [".badge.ok" {:color "var(--green)" :border-color "#9bd8bf" :background "#ecfdf5"}]
   [".badge.warn" {:color "var(--amber)" :border-color "#f1c27b" :background "#fff7ed"}]
   [".badge.stop" {:color "var(--red)" :border-color "#f3a086" :background "#fff1ed"}]
   [".workspace" {:display "grid"
                  :grid-template-columns "300px minmax(0, 1fr) 360px"
                  :gap "14px" :align-items "start"}]
   [".stack" {:display "grid" :gap "12px"}]
   ["label" {:display "grid" :gap "5px" :margin-bottom "10px"
             :color "var(--muted)" :font-size "12px"}]
   ["select, input[type=\"range\"], input[type=\"number\"]"
    {:width "100%" :min-height "34px" :border "1px solid var(--line)"
     :border-radius "6px" :background "#fff" :color "var(--ink)"
     :padding "5px 8px" :font "13px var(--sans)"}]
   [".checks" {:display "grid" :grid-template-columns "1fr 1fr" :gap "7px"
               :margin-top "8px"}]
   [".checks label" {:margin "0" :display "flex" :align-items "center"
                      :gap "7px" :color "var(--ink)" :font-size "12px"}]
   ["button, .button" {:min-height "34px" :border "1px solid var(--line)"
                        :border-radius "6px" :background "#fff" :color "var(--ink)"
                        :font-weight "690" :cursor "pointer" :padding "7px 10px"}]
   ["button:hover, .button:hover" {:border-color "#a8b3c7" :background "#f8fafc"
                                    :text-decoration "none"}]
   ["button.primary" {:background "var(--blue)" :color "#fff" :border-color "var(--blue)"}]
   ["button.danger" {:color "var(--red)"}]
   [".actions" {:display "grid" :grid-template-columns "1fr 1fr" :gap "8px"}]
   [".actions .wide" {:grid-column "1 / -1"}]
   [".metrics" {:display "grid" :grid-template-columns "repeat(4, 1fr)" :gap "8px"}]
   [".metric" {:padding "10px" :background "#f8fafc" :border "1px solid var(--line)"
               :border-radius "6px"}]
   [".metric span" {:display "block" :color "var(--muted)" :font-size "11px"}]
   [".metric b" {:display "block" :margin-top "4px" :font-size "20px"}]
   [".score-list" {:display "grid" :gap "8px"}]
   [".score-row" {:display "grid" :grid-template-columns "88px 1fr 46px"
                  :gap "8px" :align-items "center" :font-size "12px"}]
   [".bar" {:height "9px" :border-radius "999px" :background "#e2e8f0" :overflow "hidden"}]
   [".bar span" {:display "block" :height "100%" :background "var(--blue)"}]
   [".maturity-grid" {:display "grid"
                       :grid-template-columns "repeat(3, minmax(0, 1fr))"
                       :gap "8px" :margin "10px 0"}]
   [".maturity-card" {:padding "10px" :border "1px solid var(--line)"
                       :border-radius "6px" :background "#f8fafc"}]
   [".maturity-card span" {:display "block" :color "var(--muted)" :font-size "11px"}]
   [".maturity-card b" {:display "block" :margin-top "4px" :font-size "18px"}]
   [".matrix" {:width "100%" :border-collapse "collapse" :font-size "12px"
               :margin-top "10px"}]
   [".matrix th, .matrix td" {:border-bottom "1px solid var(--line)"
                               :padding "7px 6px" :text-align "left"
                               :vertical-align "top"}]
   [".matrix th" {:color "var(--muted)" :font-weight "700"}]
   [".drop" {:border "1px dashed #9aa7bd" :border-radius "8px"
             :background "#f8fafc" :padding "12px"}]
   [".drop input" {:width "100%" :font-size "12px"}]
   [".canvas-wrap" {:position "relative" :overflow "hidden" :border-radius "8px"
                    :border "1px solid var(--line)" :background "#eef2f7"}]
   ["canvas" {:width "100%" :height "420px" :display "block"}]
   [".canvas-tabs" {:position "absolute" :top "8px" :left "8px" :display "flex"
                    :gap "6px" :flex-wrap "wrap"}]
   [".canvas-tabs button" {:min-height "28px" :padding "4px 8px" :font-size "12px"
                            :background "rgba(255,255,255,.9)"}]
   [".canvas-tabs button.active" {:color "#fff" :background "var(--cyan)"
                                   :border-color "var(--cyan)"}]
   [".stage-grid" {:display "grid" :grid-template-columns "repeat(3, minmax(0, 1fr))"
                   :gap "8px"}]
   [".stage" {:padding "10px" :min-height "92px" :border-left "4px solid #cbd5e1"}]
   [".stage.active" {:border-left-color "var(--blue)"
                      :box-shadow "inset 0 0 0 1px #93c5fd"}]
   [".stage.done" {:border-left-color "var(--green)"}]
   [".stage.fail" {:border-left-color "var(--red)"}]
   [".stage b" {:display "block" :font-size "12px"}]
   [".stage span" {:display "block" :margin-top "4px" :color "var(--muted)"
                   :font-size "11px" :line-height "1.35"}]
   [".gate" {:display "flex" :align-items "center" :justify-content "space-between"
             :gap "8px" :padding "8px 0" :border-bottom "1px solid var(--line)"}]
   [".gate:last-child" {:border-bottom "0"}]
   [".gate button" {:min-height "28px" :padding "4px 8px" :font-size "12px"}]
   [".gate strong" {:font-size "12px"}]
   [".gate span" {:color "var(--muted)" :font-size "11px"}]
   [".log" {:display "grid" :gap "7px" :max-height "360px" :overflow "auto"}]
   [".log-row" {:padding "8px" :font-size "12px"}]
   [".log-row b" {:color "var(--violet)"}]
   [".log-row small" {:display "block" :color "var(--muted)" :margin-top "3px"}]
   ["pre" {:margin "0" :max-height "380px" :overflow "auto" :padding "10px"
           :border "1px solid var(--line)" :border-radius "6px"
           :background "#101827" :color "#dbeafe" :font-size "11px"
           :line-height "1.45"}]
   [".source-links" {:display "flex" :flex-wrap "wrap" :gap "8px" :margin-top "10px"}]
   [".source-links a" {:font-size "12px"}]])

(def media-1120
  [[".workspace" {:grid-template-columns "280px minmax(0, 1fr)"}]
   [".workspace > aside:last-child" {:grid-column "1 / -1"}]])

(def media-780
  [[".hero, .workspace" {:grid-template-columns "1fr"}]
   [".stage-grid, .metrics, .maturity-grid" {:grid-template-columns "repeat(2, minmax(0, 1fr))"}]
   [".nav-inner" {:align-items "flex-start" :padding-top "10px" :padding-bottom "10px"}]])

(def media-520
  [[".stage-grid, .metrics, .maturity-grid, .actions" {:grid-template-columns "1fr"}]
   ["canvas" {:height "360px"}]])

(def sheet
  {:rules rules
   :media [["(max-width: 1120px)" media-1120]
           ["(max-width: 780px)" media-780]
           ["(max-width: 520px)" media-520]]})

(defn page-css
  "The full CSS text for the workbench page, rendered from `sheet` via
  css.core/css."
  []
  (css/css sheet))
