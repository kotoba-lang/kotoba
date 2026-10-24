(ns kami.studio.ui
  "The Kami Studio hub page — a static link-out grid to the 6 separate 3D-editor
  apps (Modeler/Animator/BIM Editor/CAD/Sculpt/Amenominaka), not an editor itself.
  Pure hiccup rendered via kotoba-lang/html + kotoba-lang/css, no reagent/build step.
  HIG/WCAG hardening (viewport-fit, safe-area, focus-visible, dark theme-color,
  responsive breakpoint, lang attr): design-quality Co-Scientist audit
  (com-junkawasaki/root ADR-2607132300 addendum 3)."
  (:require [html.core :as html]
            [css.core :as css]))

(def apps
  [{:name "Vehicle Physics" :kind "Shared node / beam document" :url "https://kotoba-lang.github.io/kami-app-modeler/?workspace=vehicle-physics"}
   {:name "Modeler" :kind "Polygon & modifiers" :url "https://kotoba-lang.github.io/kami-app-modeler/"}
   {:name "Animator" :kind "Timeline & keyframes" :url "https://kotoba-lang.github.io/kami-app-animator/"}
   {:name "BIM Editor" :kind "Building information" :url "https://kotoba-lang.github.io/kami-app-bim-editor/"}
   {:name "CAD" :kind "NURBS & precision" :url "https://kotoba-lang.github.io/kami-app-cad/"}
   {:name "Sculpt" :kind "Digital clay" :url "https://kotoba-lang.github.io/kami-app-sculpt/"}
   {:name "Amenominaka" :kind "Realtime Archviz" :url "https://kotoba-lang.github.io/kami-app-amenominaka/"}])

(def stylesheet
  (css/css
   {:rules
    {"html" {:color-scheme "dark"}
     "body" {:margin 0 :font-family "system-ui" :background "#08101d" :color "#eff5ff"
             :overflow-x "clip"}
     "header,main" {:max-width 1100 :margin "auto"
                     :padding "max(28px,env(safe-area-inset-top)) max(22px,env(safe-area-inset-right)) max(28px,env(safe-area-inset-bottom)) max(22px,env(safe-area-inset-left))"}
     "header" {:display :flex :justify-content :space-between}
     ".grid" {:display :grid :grid-template-columns "repeat(auto-fit,minmax(260px,1fr))" :gap 16}
     "a" {:color :inherit :text-decoration :none}
     "a:focus-visible" {:outline "2px solid #8cb5ff" :outline-offset "2px" :border-radius "4px"}
     ".card" {:min-height 170 :padding 22 :border "1px solid #304968" :border-radius 12
               :background "linear-gradient(145deg,#12223a,#0b1626)"}
     ".card:hover" {:border-color "#8cb5ff" :transform "translateY(-3px)"}
     ".eyebrow" {:color "#98b8ec" :font-size 12 :text-transform :uppercase :letter-spacing ".12em"}
     "h2" {:margin "16px 0 8px"}}
    :media
    {"(max-width:600px)"
     {"header,main" {:padding "max(20px,env(safe-area-inset-top)) max(16px,env(safe-area-inset-right)) max(20px,env(safe-area-inset-bottom)) max(16px,env(safe-area-inset-left))"}
      "h1" {:font-size 22}}}}))

(defn page []
  (html/html5
   [:html {:lang "en"}
    [:head
     [:meta {:charset "utf-8"}]
     [:meta {:name "viewport" :content "width=device-width,initial-scale=1,viewport-fit=cover"}]
     [:meta {:name "theme-color" :content "#08101d"}]
     [:title "Kami Studio"]
     [:style stylesheet]]
    [:body
     [:header [:strong "KAMI STUDIO"] [:span "One interoperable 3D workspace"]]
     [:main
      [:p.eyebrow "Author · animate · visualize"]
      [:h1 "A cohesive creation suite."]
      [:section.grid
       (for [{:keys [name kind url]} apps]
         [:a {:href url}
          [:article.card
           [:span.eyebrow kind]
           [:h2 name]
           [:p "Open workspace →"]]])]]]]))
