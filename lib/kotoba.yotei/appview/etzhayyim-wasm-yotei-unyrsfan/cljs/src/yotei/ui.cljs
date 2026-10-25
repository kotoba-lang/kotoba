(ns yotei.ui
  (:require [yotei.state :as state]
            [reagent.core :as reagent]))

;; Port of CalendarView.svelte / BookingPage.svelte / EventList.svelte.
;; Structural chrome is hand-rolled hiccup (appkit.core is still .cljk on
;; main and invisible to shadow-cljs — same contract as kafun.ui/saiban.ui).

(defn fmt-date [js-date]
  (subs (.toISOString js-date) 0 10))

(defn- new-date [offset-days]
  (let [d (js/Date.)]
    (.setHours d 0 0 0)
    (.setDate d (+ (.getDate d) offset-days))
    d))

(defn- week-start []
  (let [d (js/Date.)
        dow (.getDay d)
        off (+ (- 1 dow) (* 7 (:week-offset @state/app)))]
    (.setHours d 0 0 0)
    (.setDate d (+ (.getDate d) off))
    d))

(defn- pad2 [n]
  (if (< n 10) (str "0" n) (str n)))

(defn- hour-hhmm [hour]
  (str (pad2 hour) ":00"))

(defn- dow-available? [availability dow hour]
  (let [hhmm (hour-hhmm hour)]
    (boolean (some (fn [a]
                     (and (= (:day-of-week a) dow)
                          (not (pos? (compare (:start-time a) hhmm)))
                          (pos? (compare (:end-time a) hhmm))))
                   availability))))

(defn- events-at [events date-str hour]
  (filter (fn [e]
            (let [s (str (:start-at e))
                  e-date (subs s 0 10)
                  e-hour (js/parseInt (subs s 11 13) 10)]
              (and (= e-date date-str) (= e-hour hour))))
          events))

(defn- load-week []
  (let [cal-id (:calendar-id @state/app)]
    (when (seq cal-id)
      (state/set-val :loading true)
      (let [start (week-start)
            end-d (js/Date. (.getTime start))
            _ (.setDate end-d (+ (.getDate end-d) 6))
            start-str (fmt-date start)
            end-str (fmt-date end-d)]
        (state/xrpc "com.etzhayyim.apps.yotei.getAvailability"
                    {:calendarId cal-id}
                    (fn [avail-res]
                      (state/set-val :availability (get avail-res :availability []))
                      (state/xrpc "com.etzhayyim.apps.yotei.listEvents"
                                  {:calendarId cal-id :dateFrom start-str :dateTo end-str}
                                  (fn [evt-res]
                                    (state/set-val :events (get evt-res :events []))
                                    (state/set-val :loading false)))))))))

(defn- input-value [e]
  (.. e -target -value))

(defn- dow-cell [availability events ws hour dow]
  (let [d (js/Date. (.getTime ws))]
    (.setDate d (+ (.getDate d) dow))
    (let [date-str (fmt-date d)
          real-dow (mod (inc dow) 7)
          avail? (dow-available? availability real-dow hour)
          hour-events (events-at events date-str hour)]
      ^{:key dow}
      [:td {:class (str "yt-cell" (when avail? " yt-cell-avail"))}
       (doall
        (for [evt hour-events]
          ^{:key (:id evt)}
          [:div {:class "yt-evt"} (:title evt)]))])))

(defn- hour-row [availability events ws hour]
  (let [cells (doall
               (for [dow (range 7)]
                 (dow-cell availability events ws hour dow)))]
    ^{:key hour}
    [:tr
     [:td {:class "hour-label"} (str hour ":00")]
     cells]))

(defn- calendar-view []
  (let [{:keys [calendar-id availability events loading week-offset]} @state/app
        day-names ["Sun" "Mon" "Tue" "Wed" "Thu" "Fri" "Sat"]
        hours (vec (range 7 21))
        ws (week-start)
        header-dow (fn [dow]
                     (let [d (js/Date. (.getTime ws))]
                       (.setDate d (+ (.getDate d) dow))
                       ^{:key dow}
                       [:th
                        [:div {:class "dow"} (day-names (mod (inc dow) 7))]
                        [:div {:class "dom"} (.getDate d)]]))
        rows (doall
              (for [hour hours]
                (hour-row availability events ws hour)))]
    [:div
     [:div {:class "yt-row"}
      [:input {:class "yt-input" :type "text" :placeholder "Calendar ID"
               :value calendar-id
               :on-change (fn [e] (state/set-val :calendar-id (input-value e)))}]
      [:button {:class "yt-btn" :on-click load-week} "Load"]]
     [:div {:class "yt-spread"}
      [:button {:class "yt-btn-ghost"
                :on-click (fn [_] (state/set-val :week-offset (dec week-offset)) (load-week))}
       "Prev"]
      [:span (str (fmt-date ws) " week")]
      [:button {:class "yt-btn-ghost"
                :on-click (fn [_] (state/set-val :week-offset (inc week-offset)) (load-week))}
       "Next"]]
     (if loading
       [:div {:class "yt-center"} "Loading..."]
       [:div {:class "yt-calendar-scroll"}
        [:table {:class "yt-cal"}
         [:thead
          [:tr
           [:th {:style {:width "48px"}}]
           (doall (map header-dow (range 7)))]]
         [:tbody rows]]])]))

(defn- status-badge [status]
  [:span {:class (str "yt-badge yt-badge-" (name (or status :proposed)))}
   (name (or status :proposed))])

(defn- load-bookings []
  (let [cal-id (:calendar-id @state/app)]
    (when (seq cal-id)
      (state/xrpc "com.etzhayyim.apps.yotei.listBookings"
                  {:calendarId cal-id}
                  (fn [res]
                    (state/set-val :bookings (get res :bookings [])))))))

(defn- propose-booking []
  (let [{:keys [calendar-id requester-did duration-min message]} @state/app]
    (when (and (seq calendar-id) (seq requester-did))
      (state/set-val :submitting true)
      (state/set-val :result "")
      (state/xrpc "com.etzhayyim.apps.yotei.proposeBooking"
                  {:calendarId calendar-id
                   :requesterDid requester-did
                   :durationMin duration-min
                   :message message}
                  (fn [res]
                    (state/set-val :result (str "Booking " (:id res) " — " (:status res)))
                    (state/set-val :submitting false)
                    (load-bookings))))))

(defn- booking-view []
  (let [{:keys [calendar-id requester-did duration-min message submitting result bookings]} @state/app]
    [:div
     [:h2 "Book a Meeting"]
     [:div {:class "yt-form"}
      [:input {:class "yt-input" :type "text" :placeholder "Calendar ID"
               :value calendar-id
               :on-change (fn [e] (state/set-val :calendar-id (input-value e)))}]
      [:input {:class "yt-input" :type "text" :placeholder "Your DID (did:web:...)"
               :value requester-did
               :on-change (fn [e] (state/set-val :requester-did (input-value e)))}]
      [:div {:class "yt-row"}
       [:span {:class "yt-muted"} "Duration"]
       [:select {:class "yt-select" :value duration-min
                 :on-change (fn [e] (state/set-val :duration-min (js/parseInt (input-value e) 10)))}
        (doall
         (for [d [15 30 45 60 90]]
           ^{:key d}
           [:option {:value d} (str d " min")]))]]
      [:textarea {:class "yt-textarea" :rows 2 :placeholder "Message (optional)"
                  :value message
                  :on-change (fn [e] (state/set-val :message (input-value e)))}]
      [:button {:class "yt-btn"
                :disabled (or submitting (not (seq calendar-id)) (not (seq requester-did)))
                :on-click propose-booking}
       (if submitting "Proposing..." "Propose Booking")]
      (when (seq result)
        [:div {:class "yt-result"} result])]
     [:div {:class "yt-spread"}
      [:h3 "Bookings"]
      [:button {:class "yt-link" :on-click load-bookings} "Refresh"]]
     (if (empty? bookings)
       [:div {:class "yt-center"} "No bookings yet"]
       [:div {:class "yt-stack"}
        (doall
         (for [bk bookings]
           ^{:key (:id bk)}
           [:div {:class "yt-card"}
            [:div {:class "yt-spread" :style {:margin-bottom "4px"}}
             [:span {:class "yt-mono"} (:id bk)]
             [status-badge (:status bk)]]
            [:div (:requester-did bk)]
            [:div {:class "yt-dim" :style {:font-size "11px"}}
             (str (:duration-min bk) "min — " (subs (str (:created-at bk)) 0 16))]
            (when-let [slot (:confirmed-slot bk)]
              [:div {:style {:font-size "11px" :color "#4ade80" :margin-top "4px"}}
               (str "Confirmed: " slot)])]))])]))

(defn- fmt-dt [iso]
  (let [s (str iso)]
    (when (seq s)
      (let [d (js/Date. s)]
        (str (.toLocaleDateString d "ja-JP" #js {:month "short" :day "numeric" :weekday "short"})
             " "
             (.toLocaleTimeString d "ja-JP" #js {:hour "2-digit" :minute "2-digit"}))))))

(defn- cancel-event [id]
  (state/xrpc "com.etzhayyim.apps.yotei.cancelEvent" {:id id}
              (fn [_]
                (let [cal-id (:calendar-id @state/app)]
                  (when (seq cal-id)
                    (state/xrpc "com.etzhayyim.apps.yotei.listEvents"
                                {:calendarId cal-id :dateFrom (.toISOString (js/Date.))}
                                (fn [res]
                                  (state/set-val :events (get res :events [])))))))))

(defn- load-events []
  (let [cal-id (:calendar-id @state/app)]
    (when (seq cal-id)
      (state/set-val :loading true)
      (state/xrpc "com.etzhayyim.apps.yotei.listEvents"
                  {:calendarId cal-id :dateFrom (.toISOString (js/Date.))}
                  (fn [res]
                    (state/set-val :events (get res :events []))
                    (state/set-val :loading false))))))

(defn- events-view []
  (let [{:keys [calendar-id events loading]} @state/app]
    [:div
     [:h2 "Upcoming Events"]
     [:div {:class "yt-row"}
      [:input {:class "yt-input" :type "text" :placeholder "Calendar ID"
               :value calendar-id
               :on-change (fn [e] (state/set-val :calendar-id (input-value e)))}]
      [:button {:class "yt-btn" :on-click load-events} "Load"]]
     (if loading
       [:div {:class "yt-center"} "Loading..."]
       (if (empty? events)
         [:div {:class "yt-center"} "No upcoming events"]
         [:div {:class "yt-stack"}
          (doall
           (for [evt events]
             ^{:key (:id evt)}
             [:div {:class "yt-card"}
              [:div {:style {:display "flex" :align-items "flex-start" :justify-content "space-between"}}
               [:div {:style {:flex 1}}
                [:div {:style {:font-size "15px" :font-weight 500}} (:title evt)]
                [:div {:class "yt-muted" :style {:font-size "13px" :margin-top "2px"}}
                 (str (fmt-dt (:start-at evt)) " — " (fmt-dt (:end-at evt)))]
                (when-let [loc (:location evt)]
                  [:div {:class "yt-dim" :style {:font-size "11px" :margin-top "2px"}} loc])]
               [:button {:class "yt-cancel" :on-click (fn [_] (cancel-event (:id evt)))}
                "Cancel"]]]))]))]))

(defn- tab-bar []
  (let [route (:route @state/app)
        tabs [[:calendar "📅" "Calendar"]
              [:booking "📋" "Book"]
              [:events "📆" "Events"]]]
    [:nav {:class "yt-nav"}
     (doall
      (for [[id icon label] tabs]
        ^{:key id}
        [:button {:class (str "yt-tab " (if (= route id) "yt-tab-active" "yt-tab-idle"))
                  :on-click (fn [_] (state/set-val :route id))}
         [:span {:class "icon"} icon]
         [:span {:class "label"} label]]))]))

(defn root-view []
  (let [route (:route @state/app)]
    [:div {:class "yt-root"}
     [:header {:class "yt-header"}
      [:span "Yotei"]]
     (when-let [err (:error @state/app)]
       [:div {:class "yt-center" :style {:color "#fca5a5"}} (str "Error: " err)])
     [:main {:class "yt-main"}
      [:div {:class "yt-content"}
       (case route
         :calendar [calendar-view]
         :booking [booking-view]
         [events-view])]]
     [tab-bar]]))
