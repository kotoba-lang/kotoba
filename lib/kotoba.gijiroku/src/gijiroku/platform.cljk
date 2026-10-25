(ns gijiroku.platform
  "MeetingPlatform — the port every meeting service (Zoom / Google Meet /
  Teams) implements, so `gijiroku.operation` never branches on platform. Each
  concrete client (`gijiroku.zoom` `gijiroku.google-meet` `gijiroku.teams`)
  normalizes its native REST payload into `gijiroku.model` shapes. I/O
  (:http-fn :json-write :json-read) is injected — the same host-caps
  discipline `kekkai.kotoba`/`langchain.db` use — so this namespace and its
  clients stay dependency-free and swap for a real HTTP stack only at the
  edge.

  `mock-platform` is the default: a deterministic in-memory meeting so the
  actor and its tests run offline, without OAuth apps or admin consent."
  (:require [gijiroku.model :as m]))

(defprotocol MeetingPlatform
  (meeting-meta [p external-id] "Fetch meeting metadata → gijiroku.model/meeting, or nil.")
  (fetch-recording [p external-id] "Fetch recording asset-ref → gijiroku.model/recording, or nil.")
  (fetch-transcript [p external-id] "Fetch/normalize transcript → gijiroku.model/transcript, or nil.")
  (list-participants [p external-id] "Fetch the participant roster.")
  (verify-webhook [p headers raw-body] "Verify an inbound webhook's signature; boolean."))

;; ───────────────────────── mock (default) ─────────────────────────

(def ^:private demo-tenant "cloud-itonami")

(defn- demo-meeting [external-id]
  {:id external-id :platform :mock :external-id external-id
   :title "週次すり合わせ" :host "p-jun" :tenant demo-tenant
   :participants [{:id "p-jun" :email "jun@gftd.group"}
                  {:id "p-guest" :email "guest@example.com"}]
   :status :ended :scheduled-start 1751500000})

(defn- demo-transcript [external-id]
  {:id (str "t-" external-id) :meeting-id external-id :source :platform-native :lang "ja"
   :segments
   [{:seg-id "s1" :speaker "p-jun" :t0 0 :t1 12 :text "進捗を共有します。" :sensitive #{}}
    {:seg-id "s2" :speaker "p-guest" :t0 12 :t1 40
     :text "了解です、来週までに数値をまとめます。" :sensitive #{}}]})

(defrecord MockPlatform [fixtures]
  MeetingPlatform
  (meeting-meta [_ external-id] (get-in fixtures [:meetings external-id] (demo-meeting external-id)))
  (fetch-recording [_ external-id]
    {:id (str "r-" external-id) :meeting-id external-id :platform :mock
     :asset-ref (str "b2://gijiroku/" external-id ".mp4") :duration-s 2400 :format "mp4"})
  (fetch-transcript [_ external-id] (get-in fixtures [:transcripts external-id] (demo-transcript external-id)))
  (list-participants [p external-id] (m/participant-ids (meeting-meta p external-id)))
  (verify-webhook [_ _headers _raw-body] true))

(defn mock-platform
  ([] (mock-platform {}))
  ([fixtures] (->MockPlatform fixtures)))

;; ───────────────────────── registry ─────────────────────────

(defn dispatch
  "Look up the MeetingPlatform impl for a meeting's :platform key. `impls` is
  a map like {:zoom (zoom/client ...) :google-meet (...) :teams (...)
  :mock (mock-platform)} assembled by the caller (`gijiroku.operation`
  defaults every key to `mock-platform`)."
  [impls platform-kw]
  (or (get impls platform-kw) (get impls :mock) (mock-platform)))
