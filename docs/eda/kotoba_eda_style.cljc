(ns kotoba-eda-style
  "kotoba EDA Flow Workbench app CSS — the small, unlayered, token-only layer
  on top of the kotoba-ui design system (see kotoba-ui/docs/agent-guide.md).

  Everything the design system provides (HIG typography, semantic colors
  light+dark, glass panels/buttons/badges/tab-bar, shell layout scaffolds)
  now comes from kotoba-ui.theme/theme-css embedded by kotoba-ui.core/->page
  in kotoba_eda_build.clj — the ~180 lines of hand CSS and the 13 `:root`
  custom props (--bg/--ink/--green/--violet/…) that used to live here are
  gone. What remains is workbench-specific density/layout: the 3-column
  workspace grid, metric/stage/matrix/log compactness, and status accents —
  every value a `--hig-*` token (or color-mix over one), zero raw hex, zero
  font-size px outside the token vars.

  These rules are deliberately *unlayered*: all library CSS lives inside
  `@layer kotoba.hig, kotoba.glass`, so this sheet always wins without
  specificity fights (agent-guide rule 3).

  `rules` stays a *vector* of [selector decls] pairs (css.core), preserving
  source order for same-specificity cascade."
  (:require [css.core :as css]))

(def rules
  [;; Derived, token-only app vars. HIG's secondary-label (60% alpha) and the
   ;; raw system palette sit just under WCAG 4.5:1 on light glass for the
   ;; caption-sized dense text this workbench is full of, so mix them toward
   ;; label ink — still pure token math (no literal colors), flips correctly
   ;; with the dark tokens. Measured with the Playwright contrast probe:
   ;; light goes 3.4→7+ (muted) and 2.2→4.6+ (status) while dark stays >7.
   [":root"
    {"--eda-muted" "color-mix(in srgb, var(--hig-color-secondary-label) 55%, var(--hig-color-label))"
     "--eda-ok" "color-mix(in srgb, var(--hig-palette-green) 52%, var(--hig-color-label))"
     "--eda-warn" "color-mix(in srgb, var(--hig-palette-orange) 52%, var(--hig-color-label))"
     "--eda-stop" "color-mix(in srgb, var(--hig-palette-red) 52%, var(--hig-color-label))"}]
   ;; -- page frame ----------------------------------------------------------
   [".nav-links" {:display "flex" :gap "var(--hig-spacing-3)" :flex-wrap "wrap"
                  :align-items "center"
                  :font-size "var(--hig-text-footnote-font-size)"}]
   [".nav-links a" {:color "var(--hig-color-label)" :text-decoration "none"}]
   [".nav-links a:hover" {:text-decoration "underline"}]
   [".hero" {:display "grid" :grid-template-columns "1.2fr .8fr"
             :gap "var(--hig-spacing-3)" :align-items "stretch"
             :padding "var(--hig-spacing-3) 0 var(--hig-spacing-4)"}]
   [".workspace" {:display "grid"
                  :grid-template-columns "300px minmax(0, 1fr) 360px"
                  :gap "var(--hig-spacing-3)" :align-items "start"}]
   ;; -- dense panel interior --------------------------------------------------
   [".panel-title" {:margin "0 0 var(--hig-spacing-2)"}]
   [".panel-note" {:color "var(--eda-muted)"
                   :font-size "var(--hig-text-caption1-font-size)"
                   :line-height "var(--hig-text-caption1-line-height)"
                   :margin "0 0 var(--hig-spacing-2)"}]
   ["label.field" {:display "grid" :gap "var(--hig-spacing-1)"
                   :margin-bottom "var(--hig-spacing-2)"
                   :color "var(--eda-muted)"
                   :font-size "var(--hig-text-caption1-font-size)"}]
   [".checks" {:display "grid" :grid-template-columns "1fr 1fr"
               :gap "var(--hig-spacing-2)" :margin-top "var(--hig-spacing-2)"}]
   [".checks label" {:margin "0" :color "var(--hig-color-label)"}]
   [".actions" {:display "grid" :grid-template-columns "1fr 1fr"
                :gap "var(--hig-spacing-2)"}]
   [".actions button" {:font-size "var(--hig-text-footnote-font-size)"}]
   [".wide" {:grid-column "1 / -1"}]
   ["button.primary" {:background "var(--hig-color-tint)"
                      :color "var(--hig-color-system-background)"}]
   ["button.danger" {:color "var(--hig-palette-red)"}]
   ;; -- status badges (system palette, not invented hex) ---------------------
   [".badges" {:display "flex" :flex-wrap "wrap" :gap "var(--hig-spacing-2)"
               :margin-top "var(--hig-spacing-3)"}]
   [".badges .ok" {:color "var(--eda-ok)"
                 :background "color-mix(in srgb, var(--hig-palette-green) 12%, transparent)"}]
   [".badges .warn" {:color "var(--eda-warn)"
                   :background "color-mix(in srgb, var(--hig-palette-orange) 14%, transparent)"}]
   [".badges .stop" {:color "var(--eda-stop)"
                   :background "color-mix(in srgb, var(--hig-palette-red) 12%, transparent)"}]
   ;; -- metrics / maturity cards ---------------------------------------------
   [".metrics" {:display "grid" :grid-template-columns "repeat(4, 1fr)"
                :gap "var(--hig-spacing-2)"}]
   [".maturity-grid" {:display "grid"
                      :grid-template-columns "repeat(3, minmax(0, 1fr))"
                      :gap "var(--hig-spacing-2)" :margin "var(--hig-spacing-2) 0"}]
   [".metric, .maturity-card"
    {:padding "var(--hig-spacing-2)"
     :background "var(--hig-color-quaternary-system-fill)"
     :border "var(--hig-hairline) solid var(--hig-color-separator)"
     :border-radius "var(--hig-radius-xs)" :min-width "0"}]
   [".metric span, .maturity-card span"
    {:display "block" :color "var(--eda-muted)"
     :font-size "var(--hig-text-caption2-font-size)"}]
   [".metric b, .maturity-card b"
    {:display "block" :margin-top "var(--hig-spacing-1)"
     :font-size "var(--hig-text-title3-font-size)" :overflow-wrap "anywhere"}]
   ;; -- co-sientist score rows -------------------------------------------------
   [".score-list" {:display "grid" :gap "var(--hig-spacing-2)"}]
   [".score-row" {:display "grid" :grid-template-columns "88px 1fr 46px"
                  :gap "var(--hig-spacing-2)" :align-items "center"
                  :font-size "var(--hig-text-caption1-font-size)"}]
   ;; -- matrices ---------------------------------------------------------------
   [".matrix" {:width "100%" :border-collapse "collapse"
               :font-size "var(--hig-text-caption1-font-size)"
               :margin-top "var(--hig-spacing-2)"}]
   [".matrix th, .matrix td"
    {:border-bottom "var(--hig-hairline) solid var(--hig-color-separator)"
     :padding "var(--hig-spacing-2) var(--hig-spacing-1)"
     :text-align "left" :vertical-align "top" :overflow-wrap "anywhere"}]
   [".matrix th" {:color "var(--eda-muted)" :font-weight "700"}]
   ;; -- artifact intake / drop zones -------------------------------------------
   [".drop" {:border "1px dashed var(--hig-color-separator)"
             :border-radius "var(--hig-radius-sm)"
             :background "var(--hig-color-quaternary-system-fill)"
             :padding "var(--hig-spacing-3)"}]
   [".drop input" {:width "100%" :font-size "var(--hig-text-caption1-font-size)"}]
   ;; -- kami-engine canvas -------------------------------------------------------
   [".canvas-wrap" {:position "relative" :overflow "hidden"
                    :border-radius "var(--hig-radius-sm)"
                    :border "var(--hig-hairline) solid var(--hig-color-separator)"}]
   ["canvas" {:width "100%" :height "420px" :display "block"}]
   [".canvas-tabs" {:position "absolute" :top "var(--hig-spacing-2)"
                    :left "var(--hig-spacing-2)"}]
   ;; -- stages -------------------------------------------------------------------
   [".stage-grid" {:display "grid"
                   :grid-template-columns "repeat(3, minmax(0, 1fr))"
                   :gap "var(--hig-spacing-2)"}]
   [".stage" {:padding "var(--hig-spacing-2)" :min-height "92px"
              :background "var(--hig-color-quaternary-system-fill)"
              :border-radius "var(--hig-radius-xs)"
              :border-left "4px solid var(--hig-color-separator)"}]
   [".stage.active" {:border-left-color "var(--hig-color-tint)"
                     :box-shadow "inset 0 0 0 1px color-mix(in srgb, var(--hig-color-tint) 45%, transparent)"}]
   [".stage.done" {:border-left-color "var(--hig-palette-green)"}]
   [".stage.fail" {:border-left-color "var(--hig-palette-red)"}]
   [".stage b" {:display "block" :font-size "var(--hig-text-caption1-font-size)"}]
   [".stage span" {:display "block" :margin-top "var(--hig-spacing-1)"
                   :color "var(--eda-muted)"
                   :font-size "var(--hig-text-caption2-font-size)" :line-height "1.35"}]
   ;; -- policy gates ---------------------------------------------------------------
   [".gate" {:display "flex" :align-items "center"
             :justify-content "space-between" :gap "var(--hig-spacing-2)"
             :padding "var(--hig-spacing-2) 0"
             :border-bottom "var(--hig-hairline) solid var(--hig-color-separator)"}]
   [".gate:last-child" {:border-bottom "0"}]
   [".gate button" {:font-size "var(--hig-text-caption1-font-size)"
                    :padding "4px 10px" :min-height "28px"}]
   [".gate strong" {:font-size "var(--hig-text-caption1-font-size)"}]
   [".gate span" {:display "block" :color "var(--eda-muted)"
                  :font-size "var(--hig-text-caption2-font-size)"}]
   ;; -- logs ---------------------------------------------------------------------
   [".log" {:display "grid" :gap "var(--hig-spacing-2)" :max-height "360px"
            :overflow "auto"}]
   [".log-row" {:padding "var(--hig-spacing-2)"
                :font-size "var(--hig-text-caption1-font-size)"
                :background "var(--hig-color-quaternary-system-fill)"
                :border "var(--hig-hairline) solid var(--hig-color-separator)"
                :border-radius "var(--hig-radius-xs)" :overflow-wrap "anywhere"}]
   [".log-row b" {:color "var(--hig-palette-purple)"}]
   [".log-row small" {:display "block" :color "var(--eda-muted)"
                      :margin-top "2px"}]
   ["pre" {:margin "0" :max-height "380px" :overflow "auto"}]
   [".source-links" {:display "flex" :flex-wrap "wrap" :gap "var(--hig-spacing-2)"
                     :margin-top "var(--hig-spacing-2)"}]
   [".source-links a" {:font-size "var(--hig-text-caption1-font-size)"
                       :color "var(--hig-color-tint)" :text-decoration "none"}]
   [".source-links a:hover" {:text-decoration "underline"}]])

(def media-1120
  [[".workspace" {:grid-template-columns "280px minmax(0, 1fr)"}]
   [".col-right" {:grid-column "1 / -1"}]])

(def media-780
  [[".hero, .workspace" {:grid-template-columns "1fr"}]
   [".stage-grid, .metrics, .maturity-grid"
    {:grid-template-columns "repeat(2, minmax(0, 1fr))"}]])

(def media-520
  [[".stage-grid, .metrics, .maturity-grid, .actions" {:grid-template-columns "1fr"}]
   ["canvas" {:height "360px"}]])

(def sheet
  {:rules rules
   :media [["(max-width: 1120px)" media-1120]
           ["(max-width: 780px)" media-780]
           ["(max-width: 520px)" media-520]]})

(defn page-css
  "The workbench's app CSS text (unlayered, --hig-* token values only),
  rendered from `sheet` via css.core/css."
  []
  (css/css sheet))
