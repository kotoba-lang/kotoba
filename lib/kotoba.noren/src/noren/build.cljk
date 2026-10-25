(ns noren.build
  "事業者の公開面を建てる。純 `.cljc`（`css` 文字列は呼び出し側が読んで渡す）。

  ## この名前空間が守る 1 つの規則

  **貰っていない事実は書かない。** 営業時間も電話番号も住所もメニューも、
  brief に無ければ節ごと出さず `:missing` に積んで返す。それらしい文言で
  埋めるのは捏造で、しかも相手の店の事実についての捏造である。診断で
  `:hours` が落ちた店に、想像した営業時間の載ったサイトを見せるのは
  提案ではなく事故になる。

  ## 建てた面は自分の基準を通る

  生成物は `noren.diagnose` にそのまま掛けられる。相手のサイトを採点する
  loop が、自分の出す面を採点していなければ話にならない。テストが
  `build → diagnose` を実際に通し、UI/presence の両方に閾値を置いている。

  UI 基盤は `jp-go-dds`（workspace の base design system）。app-css が足すのは
  DADS が持たない層 —— safe-area / dvh / tap-target / focus ring / reduced-motion
  —— だけで、色も間隔も DADS の token をそのまま引く。"
  (:require [kotoba.lang.text :as str]
            [jp-go-dds.core :as dds]
            [jp-go-dds.page :as page]))

(def app-css
  "DADS に無い層だけ。値は DADS の token を引く（ここで色を作らない）。"
  "
html { overflow-x: clip; }
body { min-height: 100dvh; margin: 0;
       padding-left: env(safe-area-inset-left); padding-right: env(safe-area-inset-right);
       padding-bottom: env(safe-area-inset-bottom); }
.noren-header { padding-top: max(1.5rem, env(safe-area-inset-top)); }
.noren-main { max-width: 60rem; margin: 0 auto; padding: 0 1rem 4rem; }
.noren-sec { padding: 2rem 0; border-top: 1px solid var(--color-border-divider, #d8d8d8); }
.noren-sec:first-of-type { border-top: 0; }
.noren-dl { display: grid; grid-template-columns: 8rem 1fr; gap: .75rem 1rem; margin: 0; }
.noren-dl dt { font-weight: 700; }
.noren-dl dd { margin: 0; }
.noren-items { list-style: none; padding: 0; margin: 0; }
.noren-items li { display: flex; justify-content: space-between; gap: 1rem;
                  padding: .75rem 0; border-bottom: 1px solid var(--color-border-divider, #d8d8d8); }
.noren-actions { display: flex; flex-wrap: wrap; gap: .75rem; }
.noren-actions a, .noren-actions button {
  min-height: 48px; display: inline-flex; align-items: center; }
input, textarea, select { font-size: 16px; min-height: 48px; }
a:focus-visible, button:focus-visible, input:focus-visible, textarea:focus-visible {
  outline: 3px solid var(--color-primitive-blue-900, #0017c1); outline-offset: 2px; }
a { transition: opacity .15s ease; }
@media (prefers-reduced-motion: reduce) {
  * { animation-duration: .001ms !important; transition-duration: .001ms !important; }
}
@media (max-width: 40rem) {
  .noren-dl { grid-template-columns: 1fr; gap: .25rem 0; }
  .noren-main { padding: 0 .75rem 3rem; }
}
")

(def ^:private required-facts
  "面が仕事をするために要る事実 → brief のキー。欠けたら節を出さない。"
  {:fact/address :address
   :fact/tel :tel
   :fact/hours :hours})

(defn ^:private jsonld
  "貰った事実だけで schema.org オブジェクトを組む。キーの取捨がそのまま
  『何を知っているか』の申告になるので、nil を書き込まない。"
  [{:keys [name surface url address tel hours description]}]
  (let [m (cond-> {"@context" "https://schema.org"
                   "@type" (if (= surface :catalog) "Store" "Restaurant")
                   "name" name}
            url         (assoc "url" url)
            tel         (assoc "telephone" tel)
            description (assoc "description" description)
            address     (assoc "address" {"@type" "PostalAddress" "streetAddress" address})
            (seq hours) (assoc "openingHours" (vec hours)))]
    ;; 依存を増やさないための最小 JSON 直列化。値は文字列/ベクタ/map だけ。
    (letfn [(esc [s] (-> (str s)
                         (str/replace "\\" "\\\\") (str/replace "\"" "\\\"")
                         (str/replace "\n" "\\n") (str/replace "<" "\\u003c")))
            (enc [v] (cond
                       (map? v) (str "{" (str/join "," (map (fn [[k x]] (str "\"" (esc k) "\":" (enc x))) v)) "}")
                       (sequential? v) (str "[" (str/join "," (map enc v)) "]")
                       :else (str "\"" (esc v) "\"")))]
      (enc m))))

(defn ^:private items-section
  [surface items]
  (when (seq items)
    [:section {:class "noren-sec" :id "items"}
     (dds/heading {:level 2} (if (= surface :catalog) "商品" "メニュー"))
     (into [:ul {:class "noren-items"}]
           (map (fn [{:keys [name price note]}]
                  [:li [:span [:strong name] (when note [:span " — " note])]
                   [:span (str price "円")]])
                items))]))

(defn site
  "`brief`（所有者から貰った事実）+ `{:css dds-css-string}` → `{:html :missing :borrowed-assets}`。

  `:missing` は空でないまま出荷してよい —— **埋まっていないことが見える面**は、
  埋めた気になっている面より正しい。提案時はここが所有者への質問票になる。"
  [{:keys [name surface url address tel hours items description commerce-terms year] :as brief}
   {:keys [css dark?]}]
  (let [missing (->> required-facts
                     (keep (fn [[fact k]]
                             (let [v (get brief k)]
                               (when (or (nil? v) (and (coll? v) (empty? v))
                                         (and (string? v) (str/blank? v)))
                                 fact))))
                     vec)
        missing (cond-> missing
                  (empty? items) (conj (if (= surface :catalog) :fact/catalog-items :fact/menu-items))
                  (and (= surface :catalog) (str/blank? commerce-terms))
                  (conj :fact/commerce-terms))
        html
        (page/->page
         {:title (str name (when description (str " — " description)))
          :description description
          :css css
          :app-css app-css
          :dark? (boolean dark?)
          :head [[:meta {:property "og:title" :content name}]
                 [:meta {:property "og:type" :content "website"}]
                 (when description [:meta {:property "og:description" :content description}])
                 (when url [:meta {:property "og:url" :content url}])
                 [:script {:type "application/ld+json"} (jsonld brief)]]}
         [:header {:class "noren-header noren-main"}
          (dds/heading {:level 1} name)
          (when description [:p description])
          [:div {:class "noren-actions"}
           (when tel (dds/button {:href (str "tel:" (str/replace tel #"[^0-9+]" "")) :variant :primary} "電話する"))
           (dds/button {:href "#contact" :variant :secondary} "問い合わせ")]]
         [:main {:class "noren-main"}
          (when (or address tel (seq hours))
            [:section {:class "noren-sec" :id "info"}
             (dds/heading {:level 2} "お店の情報")
             [:dl {:class "noren-dl"}
              (when address (list [:dt "所在地"] [:dd [:address address]]))
              (when tel (list [:dt "電話"] [:dd [:a {:href (str "tel:" (str/replace tel #"[^0-9+]" ""))} tel]]))
              (when (seq hours) (list [:dt "営業時間"] [:dd (into [:div] (map (fn [h] [:div h]) hours))]))]])
          (items-section surface items)
          (when-not (str/blank? commerce-terms)
            [:section {:class "noren-sec" :id "terms"}
             (dds/heading {:level 2} "特定商取引法に基づく表記")
             [:p commerce-terms]])
          [:section {:class "noren-sec" :id "contact"}
           (dds/heading {:level 2} "お問い合わせ")
           [:form {:method "post" :action "#"}
            (dds/form-field {:label "お名前" :id "nm"} (dds/input-text {:id "nm" :name "name"}))
            (dds/form-field {:label "ご用件" :id "msg"} (dds/textarea {:id "msg" :name "message"}))
            (dds/button {:type "submit" :variant :primary} "送信")]]]
         [:footer {:class "noren-main"}
          [:p (str "© " (or year "") " " name)]])]
    {:html html
     :missing missing
     ;; **相手の素材は 1 つも運ばない。** governor はこの列が空でないと止める。
     :borrowed-assets []}))
