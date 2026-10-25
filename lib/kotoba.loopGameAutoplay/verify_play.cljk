(ns verify-play
  "Fast check of the *device* code path without waiting 16 minutes for a phone.

  The self-start path (`?mode=play&genome=...`) is the one that broke: it was
  handed a flat genome instead of `{w,b}`, threw inside setInterval where
  nothing could see it, and left the game playing with NO INPUT until a
  level-up modal blocked it forever -- which cost a 20-minute recording of a
  frozen screen before anyone noticed.

  This runs that exact URL in headless Chromium for 45 seconds and asserts the
  player actually moved. Displacement is the assertion that matches the bug;
  reaching a given level is a property of the champion, not of the wiring."
  (:require ["fs" :as fs]
            [clojure.edn :as edn]
            [loop-game-autoplay.env :as env]
            [loop-game-autoplay.policy :as policy]
            [loop-game-autoplay.server :as server]))

(def held (atom {}))
(def js-state
  (js/Function "return {t: G.t, level: G.level, pending: !!G.lvlpending, over: !!G.over, x: G.player.x, y: G.player.y, err: window.__autoplay.error || null};"))

(defn- sleep [ms] (js/Promise. (fn [r] (js/setTimeout r ms))))

(let [champ (edn/read-string (fs/readFileSync "target/run-champion.edn" "utf8"))
      pol (select-keys (policy/genome->policy (:genome champ)) [:w :b])]
  (-> (server/start! {:game-file (:game champ)})
      (.then (fn [srv] (swap! held assoc :srv srv) (env/launch! {})))
      (.then (fn [b]
               (swap! held assoc :b b)
               (.newPage b)))
      (.then (fn [page]
               (swap! held assoc :page page)
               (.goto page (str (:url (:srv @held)) "?mode=play&seed=1&genome="
                                (js/encodeURIComponent (js/JSON.stringify (clj->js pol))))
                      #js {:waitUntil "load"})))
      (.then (fn [_] (sleep 45000)))
      (.then (fn [_] (.evaluate (:page @held) js-state)))
      (.then (fn [st]
               (let [{:keys [t level pending over x y err]} (js->clj st :keywordize-keys true)
                     moved (+ (abs x) (abs y))]
                 (println (str "after 45s: game-time " (.toFixed (/ t 1000) 1) "s"
                               "  level " level
                               "  player-displacement " (.toFixed moved 1) "px"
                               "  draft-pending " pending
                               "  over " over
                               "  page-error " (pr-str err)))
                 ;; Displacement is the assertion that matches the bug: with a
                 ;; malformed policy the driver threw inside setInterval, no key
                 ;; was ever set, and the player sat at the origin for the whole
                 ;; run. Level is a property of the champion, not of the wiring.
                 (swap! held assoc :ok (and (nil? err) (not pending) (> t 40000) (> moved 100))))))
      (.then (fn [_] (.close (:b @held))))
      (.then (fn [_] (server/stop! (:srv @held))))
      (.then (fn [_]
               (println (if (:ok @held)
                          "PASS  the device code path steers the player and reports no error"
                          "FAIL  see the line above"))
               (js/process.exit (if (:ok @held) 0 1))))
      (.catch (fn [e] (println "ERROR" (str e)) (js/process.exit 2)))))
