(ns kotoba.hls
  "Watching a live HLS broadcast, as a pure reducer.

  A live-video page has to answer three questions over and over -- is
  anything broadcasting, is it the same thing that is already attached, and
  what should the viewer be told -- and every one of them is decided from
  data. Only the attaching itself needs a DOM. So the decisions live here,
  in portable `.cljc` with tests, and the host applies the effects, exactly
  as `kotoba.webrtc.whip` splits WHIP's decisions from its transport.

  This exists because the same logic had been written twice, in two
  languages, for two sites -- once as ClojureScript and once as JavaScript
  embedded in a Clojure string. That is the shape of bug that gets fixed in
  one copy.

  Portable across JVM / ClojureScript / SCI / GraalVM: no I/O, no DOM, no
  HLS library."
  (:require [kotoba.lang.text :as str]))

(def states
  "Valid viewer states.

    :unknown -- nothing asked yet
    :idle    -- the plane answered, nothing is broadcasting
    :live    -- a broadcast is attached
    :error   -- the plane is unreachable, or playback failed fatally"
  #{:unknown :idle :live :error})

(defn create-state
  "A viewer that has not asked anything yet."
  []
  {:hls/state :unknown
   :hls/playing nil
   :hls/error nil})

(defn live-broadcast
  "The broadcast to play from a listBroadcasts payload, or nil.

  `broadcasts` is the decoded list; each entry is a map with at least
  `:live` and `:playlistUrl`. The LAST live entry wins, not the first: the
  plane lists oldest-first, so the newest live broadcast is the one a
  viewer opening the page now means to watch. Entries without a playlist
  URL are ignored rather than attached as nil, which would blank the
  player for no visible reason."
  [broadcasts]
  (->> broadcasts
       (filter :live)
       (filter #(not (str/blank? (str (:playlistUrl %)))))
       last))

(defn apply-event
  "Apply a viewer event, returning {:state :effects}.

    {:type :broadcasts :broadcasts [...]}
      the plane answered. Effects:
        [:attach url]  a different broadcast than the attached one
        [:detach]      nothing is live but something is attached
      Re-attaching the SAME url emits nothing -- without that check every
      poll would tear down and rebuild a perfectly healthy player.

    {:type :unreachable :message m}
      -> :error, effect [:detach] if something was attached.

    {:type :playback-failed :message m}
      a fatal player error -> :error, effect [:detach].

  Unknown event types return the state unchanged."
  [state {:keys [type broadcasts message]}]
  (case type
    :broadcasts
    (let [b (live-broadcast broadcasts)
          url (:playlistUrl b)
          playing (:hls/playing state)]
      (cond
        (nil? b)
        {:state (assoc state :hls/state :idle :hls/playing nil :hls/error nil)
         :effects (if playing [[:detach]] [])}

        (= url playing)
        {:state (assoc state :hls/state :live :hls/error nil) :effects []}

        :else
        {:state (assoc state :hls/state :live :hls/playing url :hls/error nil)
         :effects [[:attach url]]}))

    (:unreachable :playback-failed)
    {:state (assoc state :hls/state :error :hls/playing nil :hls/error message)
     :effects (if (:hls/playing state) [[:detach]] [])}

    {:state state :effects []}))

;; ---------------------------------------------------------------------------
;; What the viewer is told
;; ---------------------------------------------------------------------------

(def ^:private status-text
  {:unknown {:ja "確認しています…" :en "checking…"}
   :idle {:ja "配信していません" :en "nothing is live right now"}
   :live {:ja "配信中" :en "live"}})

(defn status
  "The line under (or over) the player, for `locale` :ja or :en.

  Idle is phrased as a fact, not a failure: nobody is broadcasting most of
  the time, and a page that renders that as an error trains people to
  ignore real errors."
  ([state] (status state :en))
  ([state locale]
   (let [k (:hls/state state)]
     (if (= :error k)
       (or (:hls/error state)
           (if (= :ja locale) "再生できません" "playback unavailable"))
       (get-in status-text [k (if (= :ja locale) :ja :en)]
               (get-in status-text [:unknown :en]))))))

(defn mode
  "The value for the player container's `data-mode`, which is what the
  stylesheet keys off -- so nothing ever writes an inline style."
  [state]
  (name (:hls/state state :unknown)))

(defn live?
  [state]
  (= :live (:hls/state state)))

;; ---------------------------------------------------------------------------
;; Polling
;; ---------------------------------------------------------------------------

(def default-poll-interval-ms
  "How often to re-ask when idle. Opening the page before the broadcaster
  presses start is the normal case, so the page waits rather than making
  someone reload."
  8000)

(defn list-broadcasts-url
  "The plane's listBroadcasts endpoint for `base` (\"\" for same-origin)."
  [base]
  (str base "/xrpc/app.aozora.live.listBroadcasts"))
