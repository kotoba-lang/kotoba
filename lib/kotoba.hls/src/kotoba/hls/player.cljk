(ns kotoba.hls.player
  "The browser half: poll the plane, drive `kotoba.hls`, apply its effects
  to a real `<video>`.

  Everything that decides anything is in `kotoba.hls` and tested there.
  What is left here is the part that genuinely needs a DOM and an HLS
  implementation — and it is written once, so the two sites that show the
  same broadcast cannot drift apart."
  (:require [kotoba.hls :as hls]
            [kotoba.hls.view :as view]
            ["hls.js/dist/hls.min.js" :as Hls]))

(defonce ^:private rt (atom {:state (hls/create-state) :hls nil :timer nil}))

(defn- el [id] (.getElementById js/document id))

(defn- render! [state locale]
  (when-let [box (el view/container-id)]
    (.setAttribute box "data-mode" (hls/mode state)))
  (when-let [s (el view/status-id)]
    (set! (.-textContent s) (hls/status state locale))))

(defn- native-hls?
  "Whether the browser plays HLS itself.

  Checked BEFORE reaching for hls.js, never after. iOS Safari has no Media
  Source Extensions, so hls.js cannot work there at all — preferring it is
  how an HLS page ends up working on the developer's Mac and showing a
  black rectangle on every phone."
  [^js video]
  (let [c (.canPlayType video "application/vnd.apple.mpegurl")]
    (boolean (and (string? c) (seq c)))))

(declare dispatch!)

(defn- detach! []
  (when-let [^js h (:hls @rt)]
    (try (.destroy h) (catch :default _ nil)))
  (swap! rt assoc :hls nil)
  (when-let [^js video (el view/video-id)]
    ;; Clearing src and reloading is what actually stops a NATIVE HLS
    ;; playback; destroying the hls.js instance above only covers the MSE
    ;; path, and on Safari the old stream would otherwise keep running
    ;; underneath the next one.
    (try (.removeAttribute video "src") (.load video) (catch :default _ nil))))

(defn- attach! [url locale]
  (let [^js video (el view/video-id)]
    (detach!)
    (cond
      (native-hls? video)
      (do (set! (.-src video) url)
          (-> (.play video) (.catch (fn [_] (render! (:state @rt) locale)))))

      (.isSupported Hls)
      (let [^js h (Hls. #js {:lowLatencyMode true :backBufferLength 30})]
        (swap! rt assoc :hls h)
        (.on h (.-ERROR (.-Events Hls))
             (fn [_ ^js data]
               ;; Only fatal errors surface. hls.js recovers from the rest on
               ;; its own, and reporting them would flap the UI through a
               ;; perfectly healthy stream.
               (when (.-fatal data)
                 (dispatch! {:type :playback-failed
                             :message (if (= :ja locale)
                                        "再生が中断されました"
                                        "stream interrupted")}))))
        (.loadSource h url)
        (.attachMedia h video)
        (-> (.play video) (.catch (fn [_] nil))))

      :else
      (dispatch! {:type :playback-failed
                  :message (if (= :ja locale)
                             "このブラウザは HLS を再生できません"
                             "this browser cannot play HLS")}))))

(defn- handle-effect! [[kind payload] locale]
  (case kind
    :attach (attach! payload locale)
    :detach (detach!)
    nil))

(defn- dispatch! [event]
  (let [locale (:locale @rt :en)
        {:keys [state effects]} (hls/apply-event (:state @rt) event)]
    (swap! rt assoc :state state)
    (render! state locale)
    (doseq [e effects] (handle-effect! e locale))
    state))

(defn- poll! [base interval]
  (-> (js/fetch (hls/list-broadcasts-url base) #js {:cache "no-store"})
      (.then (fn [^js r]
               (if (.-ok r) (.json r) (throw (js/Error. (str "HTTP " (.-status r)))))))
      (.then (fn [^js body]
               (dispatch! {:type :broadcasts
                           :broadcasts (js->clj (or (.-broadcasts body) #js [])
                                                :keywordize-keys true)})))
      (.catch (fn [e]
                (js/console.error "hls:" e)
                (dispatch! {:type :unreachable
                            :message (if (= :ja (:locale @rt))
                                       "配信サーバーに接続できません"
                                       "could not reach the live plane")})))
      (.finally (fn []
                  (swap! rt assoc :timer (js/setTimeout #(poll! base interval) interval))))))

(defn ^:export boot
  "Start watching. `opts` (a JS object, so a plain page can call this):
    base     plane origin; \"\" for same-origin (default \"\")
    locale   \"ja\" or \"en\" (default \"en\")
    interval poll milliseconds (default kotoba.hls/default-poll-interval-ms)"
  ([] (boot #js {}))
  ([^js opts]
   (let [base (or (.-base opts) "")
         locale (if (= "ja" (.-locale opts)) :ja :en)
         interval (or (.-interval opts) hls/default-poll-interval-ms)]
     (swap! rt assoc :locale locale)
     (render! (:state @rt) locale)
     (poll! base interval))))
