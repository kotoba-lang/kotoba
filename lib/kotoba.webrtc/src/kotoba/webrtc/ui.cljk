(ns kotoba.webrtc.ui
  "Operator-facing console for a video-call/WebRTC host runtime.

  Renders an HTML read-only panel of active sessions, room membership and
  call-quality stats, using kotoba-lang/html + css. Pure data → markup: no
  network. The host runtime owns the actual RTCPeerConnection/media
  transport; this view only observes session/room/stats state."
  (:require [html.core :as html]
            [css.core :as css]
            [kotoba.webrtc.room :as room]
            [kotoba.webrtc.stats :as stats]))

(def ^:private extra-rules
  {})

(def ^:private sheet (css/merge-theme extra-rules))

(defn- stylesheet [] (html/->html (css/style-node sheet)))

(defn- session-rows [sessions]
  (for [s sessions]
    [:tr [:td (:webrtc.session/call-id s)]
     [:td (or (:webrtc.session/local-id s) "—")]
     [:td (or (:webrtc.session/remote-id s) "—")]
     [:td (name (:webrtc.session/state s))]
     [:td.amt (count (:webrtc.session/ice-candidates s))]]))

(defn- room-rows [r]
  (for [pid (room/participant-ids r)]
    [:tr [:td (str pid)]
     [:td.amt (count (room/tracks-of r pid))]
     [:td.amt (count (room/subscribers-of r pid))]]))

(defn- stats-rows [samples]
  (for [s samples]
    (let [q (stats/classify s)]
      [:tr [:td (case q :good [:span.ok "good"] :degraded [:span.warn "degraded"] [:span.err "poor"])]
       [:td.amt (:webrtc.stats/packets-lost s)]
       [:td.amt (:webrtc.stats/jitter-ms s)]
       [:td.amt (:webrtc.stats/round-trip-ms s)]])))

(defn dashboard
  "Render a full HTML console for a video-call host runtime."
  [{:keys [sessions room stats]}]
  (html/->html
    [:html
     [:head [:meta {:charset "utf-8"}] [:title "webrtc · operator"]
      [:hiccup/raw (stylesheet)]]
     [:body
      [:header.bar [:h1 "Video Call — Operator Console"] [:span.badge "read-only · host-injected transport"]]
      [:main
       (when (seq sessions)
         [:section.card [:h2 "Sessions"]
          [:table [:thead [:tr [:th "Call ID"] [:th "Local"] [:th "Remote"] [:th "State"] [:th.amt "ICE candidates"]]]
           [:tbody (session-rows sessions)]]])
       (when (and room (seq (room/participant-ids room)))
         [:section.card [:h2 "Room: " (str (:webrtc.room/room-id room))]
          [:table [:thead [:tr [:th "Participant"] [:th.amt "Tracks"] [:th.amt "Subscribers"]]]
           [:tbody (room-rows room)]]])
       (when (seq stats)
         [:section.card [:h2 "Call quality"]
          [:table [:thead [:tr [:th "Quality"] [:th.amt "Lost"] [:th.amt "Jitter (ms)"] [:th.amt "RTT (ms)"]]]
           [:tbody (stats-rows stats)]]])]]]))
