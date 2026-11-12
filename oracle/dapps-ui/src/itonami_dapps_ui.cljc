(ns itonami-dapps-ui
  "Oracle twin of the three session UI documents added for AWAI-2793
  (sound/display/soshiki under resources/aiueos/session/apps/).
  Hiccup documents plus Garden style data, readable by bb, JVM Clojure
  and Basilisp. No reader conditionals on purpose, so every hosted
  `.cljc` dialect reads this file as is (`:lpy` unmeasured).

  One-shot local measurement only (workspace AGENTS.md oracle rule,
  JUN-579): run by hand, record dated evidence under
  oracle/dapps-ui/evidence-*.md. Never CI, never a gate, never a build
  or packaging input, never a fallback for native results."
  (:require [clojure.string :as string]))

(def shared-classes
  "Every CSS class token the three documents may use. All are shared
  dds classes from the vendored stylesheet; the documents add no
  view-scoped rules, so `styles` stays empty and the Garden compile
  proves it."
  #{"dds-ext-section" "session-view" "app-window" "app-window-head"
    "window-close" "app-window-title" "window-spacer" "app-window-state"
    "app-window-body" "dads-heading" "session-lede" "session-out"
    "app-empty-state" "app-return"})

(def styles
  "Garden style data for the three documents. Empty: the documents use
  only shared classes, so a real Garden compile must yield \"\"."
  [])

(defn- window [id title state lede bind note]
  [:section {:id id :class "dds-ext-section session-view" :data-view id :hidden true}
   [:article {:class "app-window"}
    [:header {:class "app-window-head"}
     [:a {:class "window-close" :href "#desktop" :aria-label "Close app"} "×"]
     [:span {:class "app-window-title"} title]
     [:span {:class "window-spacer"} ""]
     [:span {:class "app-window-state"} state]]
    [:div {:class "app-window-body"}
     [:h1 {:class "dads-heading" :data-size "32"} title]
     [:p {:class "session-lede"} lede]
     [:pre {:class "session-out" :data-bind bind} ""]
     [:p {:class "app-empty-state"} note]
     [:a {:class "app-return" :href "#desktop"} "デスクトップへ"]]]])

(def documents
  [{:id "sound" :title "Sound" :state "Sound"
    :lede "音量とミュート。最後の設定が保存されます。"
    :bind "sound" :note "最後の設定が保存されます。"}
   {:id "display" :title "Display" :state "Display"
    :lede "画面の明るさ。最後の設定が保存されます。"
    :bind "display" :note "最後の設定が保存されます。"}
   {:id "soshiki" :title "Soshiki" :state "Soshiki"
    :lede "サークルとロールで組織を作り、Botにプロフィールを持たせる。"
    :bind "soshiki" :note "サークルとロールの概要をこのデバイスから読みます。"}])

(defn hiccup
  "Hiccup document for the dapp id. Unknown ids refuse with an error map."
  [id]
  (if-let [doc (first (filter #(= id (:id %)) documents))]
    (window (:id doc) (:title doc) (:state doc)
            (:lede doc) (:bind doc) (:note doc))
    {:error "unknown-document" :id id}))

(defn used-classes
  "Every :class token used by the three documents, split on whitespace."
  []
  (let [forms (mapcat #(tree-seq sequential? identity (hiccup (:id %))) documents)]
    (set (mapcat #(string/split % #"\s+") (keep :class (filter map? forms))))))
