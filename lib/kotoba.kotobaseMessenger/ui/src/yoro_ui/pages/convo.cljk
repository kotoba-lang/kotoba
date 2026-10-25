(ns yoro-ui.pages.convo
  "Convo (DM) list page — port of svelte routes/convo/+page.svelte."
  (:require [kotoba.lang.text :as str]
            [reagent.core :as r]
            [re-frame.core :as rf]
            [yoro-ui.router :as router]
            [yoro-ui.components.post-card :refer [avatar]]))

(defn- relative-time [iso-str]
  (when iso-str
    (let [now (.now js/Date)
          then (try (.-getTime (js/Date. iso-str)) (catch js/Error _ now))
          diff-ms (- now then)
          diff-m (/ diff-ms 60000)
          diff-h (/ diff-m 60)
          diff-d (/ diff-h 24)]
      (cond
        (< diff-m 1) "今"
        (< diff-m 60) (str (js/Math.floor diff-m) "分")
        (< diff-h 24) (str (js/Math.floor diff-h) "時間")
        :else (str (js/Math.floor diff-d) "日")))))

(defn- pref-btn [{:keys [active? on active-icon inactive-icon title]}]
  [:button {:class (str "flex-shrink-0 w-6 h-6 rounded-full flex items-center justify-center text-[12px] "
                        (if active? "bg-[#1CB0F6]/15" "opacity-30 hover:opacity-60"))
            :title title
            :on-click (fn [e] (.stopPropagation e) (on))}
   (if active? active-icon inactive-icon)])

(defn- convo-row [{:keys [id members last-message unread-count muted archived pinned]} my-did]
  (let [peer (first (remove #(= (:did %) my-did) members))
        display-name (or (:displayName peer) (:handle peer) "Unknown")
        last-text (get-in last-message [:message :text] "")]
    [:div {:class "flex items-center gap-3 px-4 py-3 border-b border-gv2-border/40 hover:bg-gv2-bg-card/30 cursor-pointer"
           :on-click #(router/navigate! (str "/messages/" id))}
     [avatar {:src (:avatar peer)
              :display-name display-name
              :size 48}]
     [:div {:class "flex-1 min-w-0"}
      [:div {:class "flex items-center justify-between"}
       [:span {:class "font-bold text-[14px] text-gv2-text-primary truncate"}
        (when pinned "📌 ") display-name]
       [:span {:class "text-[11px] text-gv2-text-muted flex-shrink-0 ml-2"}
        (relative-time (get-in last-message [:message :sentAt]))]]
      [:div {:class "flex items-center justify-between mt-0.5"}
       [:p {:class "text-[13px] text-gv2-text-muted truncate"}
        (or last-text "メッセージなし")]
       [:div {:class "flex items-center gap-1 flex-shrink-0 ml-2"}
        (when (pos? (or unread-count 0))
          [:span {:class "min-w-[18px] h-[18px] rounded-full bg-[#1CB0F6] text-white text-[11px] font-bold flex items-center justify-center px-1"}
           (str unread-count)])]]]
     [:div {:class "flex items-center gap-1 flex-shrink-0"}
      [pref-btn {:active? pinned :active-icon "📌" :inactive-icon "📌" :title (if pinned "ピン留め解除" "ピン留め")
                 :on #(rf/dispatch [:convos/set-preference! id :pinned (not pinned)])}]
      [pref-btn {:active? muted :active-icon "🔕" :inactive-icon "🔔" :title (if muted "通知を再開" "ミュート")
                 :on #(rf/dispatch [:convos/set-preference! id :muted (not muted)])}]
      [pref-btn {:active? archived :active-icon "📤" :inactive-icon "📥" :title (if archived "アーカイブ解除" "アーカイブ")
                 :on #(rf/dispatch [:convos/set-preference! id :archived (not archived)])}]]]))

(defn- skeleton-row []
  [:div {:class "flex items-center gap-3 px-4 py-3 border-b border-gv2-border/40"}
   [:div {:class "w-12 h-12 rounded-full bg-gv2-border/40 animate-pulse flex-shrink-0"}]
   [:div {:class "flex-1"}
    [:div {:class "h-3 bg-gv2-border/40 rounded w-1/3 mb-2 animate-pulse"}]
    [:div {:class "h-3 bg-gv2-border/40 rounded w-2/3 animate-pulse"}]]])

;; ---------------------------------------------------------------------------
;; Search results — cross-conversation. :convo-search/matching-convos is
;; metadata-only (always complete, from :convos/list); :convo-search/
;; matching-messages is content search scoped to convos opened this
;; session (see yoro-ui.state.convo-search's docstring for why).

(defn- search-convo-row [c my-did]
  (let [peer (first (remove #(= (:did %) my-did) (:members c)))
        title (:title c)
        display-name (or (and (seq title) title) (:displayName peer) (:handle peer) "Unknown")]
    [:div {:class "flex items-center gap-3 px-4 py-2.5 border-b border-gv2-border/40 hover:bg-gv2-bg-card/30 cursor-pointer"
           :on-click #(router/navigate! (str "/messages/" (:id c)))}
     [avatar {:src (:avatar peer) :display-name display-name :size 36}]
     [:span {:class "font-bold text-[14px] text-gv2-text-primary truncate"} display-name]]))

(defn- search-message-row [{:keys [convo-id rkey snippet convo-title]}]
  [:div {:class "flex flex-col gap-0.5 px-4 py-2.5 border-b border-gv2-border/40 hover:bg-gv2-bg-card/30 cursor-pointer"
         :on-click #(router/navigate! (str "/messages/" convo-id))}
   [:span {:class "text-[11px] font-bold text-gv2-text-muted truncate"} (or (seq convo-title) convo-id)]
   [:span {:class "text-[13px] text-gv2-text-primary truncate"} snippet]])

(defn- search-results [my-did]
  (let [matching-convos @(rf/subscribe [:convo-search/matching-convos])
        matching-messages @(rf/subscribe [:convo-search/matching-messages])]
    (if (and (empty? matching-convos) (empty? matching-messages))
      [:div {:class "flex flex-col items-center justify-center py-20 text-center px-6"}
       [:div {:class "text-4xl mb-3"} "🔍"]
       [:p {:class "text-[13px] text-gv2-text-muted"} "見つかりませんでした"]]
      [:div
       (when (seq matching-convos)
         [:<>
          [:p {:class "px-4 pt-3 pb-1 text-[11px] font-bold text-gv2-text-muted"} "会話"]
          (for [c matching-convos] ^{:key (:id c)} [search-convo-row c my-did])])
       (when (seq matching-messages)
         [:<>
          [:p {:class "px-4 pt-3 pb-1 text-[11px] font-bold text-gv2-text-muted"}
           "メッセージ（このセッションで開いた会話のみ）"]
          (for [m matching-messages]
            ^{:key (str (:convo-id m) "-" (:rkey m))} [search-message-row m])])])))

(defn convo-list-page []
  (let [show-archived? (r/atom false)]
    (r/create-class
     {:display-name "convo-list-page"

      :component-did-mount
      (fn [_]
        (when (empty? @(rf/subscribe [:convos/list]))
          (rf/dispatch [:convos/refresh])))

      :reagent-render
      (fn []
        (let [archived @(rf/subscribe [:convos/list-archived])
              convos (if @show-archived? archived @(rf/subscribe [:convos/list-visible]))
              loading? @(rf/subscribe [:convos/is-loading?])
              error @(rf/subscribe [:convos/error])
              signed-in? @(rf/subscribe [:auth/signed-in?])
              my-did @(rf/subscribe [:auth/did])
              search-query @(rf/subscribe [:convo-search/query])
              searching? (and signed-in? (seq (str/trim search-query)))]
          [:div {:class "flex flex-col"}

           ;; Header
           [:div {:class "px-4 py-3 border-b border-gv2-border flex items-center justify-between sticky top-0 z-10 bg-gv2-bg-base"}
            [:h2 {:class "text-[17px] font-bold text-gv2-text-primary"} "メッセージ"]
            [:div {:class "flex items-center gap-3"}
             (when (seq archived)
               [:button {:class "text-[12px] text-gv2-text-muted"
                         :on-click #(swap! show-archived? not)}
                (if @show-archived? "戻る" (str "アーカイブ (" (count archived) ")"))])
             [:button {:class    "text-[#1CB0F6] font-semibold text-[14px]"
                       :on-click #(if signed-in?
                                    (router/navigate! "/messages/new")
                                    (rf/dispatch [:auth-modal/open]))}
              "新規作成"]]]

           (when signed-in?
             [:div {:class "px-4 py-2 border-b border-gv2-border sticky top-[57px] z-10 bg-gv2-bg-base"}
              [:input {:type "search" :placeholder "会話・メッセージを検索"
                       :class "w-full px-3 py-2 rounded-xl bg-gv2-bg-card border border-gv2-border text-[13px] outline-none focus:border-[#1CB0F6]/50"
                       :value search-query
                       :on-change #(rf/dispatch [:convo-search/set-query! (.. % -target -value)])}]])

           (cond
             (not signed-in?)
             [:div {:class "flex flex-col items-center justify-center py-20 text-center px-6"}
              [:div {:class "text-5xl mb-4"} "💬"]
              [:p {:class "text-[14px] text-gv2-text-muted"} "メッセージを見るにはサインインが必要です"]]

             searching?
             [search-results my-did]

             (and loading? (empty? convos))
             (for [i (range 5)] ^{:key i} [skeleton-row])

             (and error (empty? convos))
             [:div {:class "flex flex-col items-center justify-center py-20 text-center px-6"}
              [:div {:class "text-5xl mb-4"} "⚠️"]
              [:h3 {:class "text-[16px] font-bold text-gv2-text-primary mb-2"} "読み込みエラー"]
              [:p {:class "text-[13px] text-gv2-text-muted mb-4"} "メッセージを取得できませんでした"]
              [:button {:class    "px-4 py-2 rounded-xl bg-[#1CB0F6] text-white font-semibold text-[14px]"
                        :on-click #(rf/dispatch [:convos/refresh])}
               "再試行"]]

             (empty? convos)
             [:div {:class "flex flex-col items-center justify-center py-20 text-center px-6"}
              [:div {:class "text-5xl mb-4"} "✉️"]
              [:h3 {:class "text-[16px] font-bold text-gv2-text-primary mb-2"}
               (if @show-archived? "アーカイブなし" "メッセージなし")]
              (when-not @show-archived?
                [:p {:class "text-[13px] text-gv2-text-muted"} "プロフィールからDMを送ってみよう"])]

             :else
             (for [c convos]
               ^{:key (:id c)} [convo-row c my-did]))]))})))
