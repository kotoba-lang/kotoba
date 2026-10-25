(ns rtc.media
  "Media track types and state — abstracts audio/video/screen-share
  tracks with mute/active lifecycle. Restored from kami-rtc's `media`
  module (kami-engine/kami-rtc/src/media.rs, deleted PR #82).")

(def media-kinds #{:audio :video :screen-share})
(def track-states #{:active :muted :ended})

(defn media-constraints
  ([] (media-constraints {}))
  ([{:keys [audio video video-width video-height frame-rate]
     :or {audio true video true video-width 640 video-height 480 frame-rate 30}}]
   {:audio audio :video video :video-width video-width :video-height video-height :frame-rate frame-rate}))

(defn audio-only-constraints [] (media-constraints {:audio true :video false}))

(defn hd-video-constraints
  []
  (media-constraints {:audio true :video true :video-width 1280 :video-height 720 :frame-rate 30}))

(defn track-stats
  []
  {:bytes-sent 0 :bytes-received 0 :packets-lost 0 :jitter-ms 0.0 :round-trip-ms 0.0})
