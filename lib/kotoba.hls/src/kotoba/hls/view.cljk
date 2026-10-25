(ns kotoba.hls.view
  "The live-player markup, once, as hiccup — so two sites showing the same
  broadcast do not draw two different players.

  Layout comes from `kotoba-ui.shell` and every value is a `--hig-*` token
  (kotoba-ui agent-guide rules 2 and 4). The only app CSS is the handful of
  rules a `<video>` needs that no shell scaffold covers, and they are keyed
  off `data-mode` so the player script never writes an inline style.

  `player` returns a body FRAGMENT, not a document: a static site wraps it
  in its own page shell with a cached stylesheet link, a Worker wraps it in
  `kotoba-ui.shell/page`. Those are genuinely different hosting models and
  the component should not care which it is in."
  (:require [css.core :as css]
            [kotoba-ui.shell :as shell]))

(def container-id "hls-player")
(def video-id "hls-video")
(def status-id "hls-status")

(def rules
  "The player's own unlayered CSS. App CSS is unlayered and library CSS
  lives in `@layer kotoba.hig, kotoba.glass`, so these win without a single
  compound selector (agent-guide rule 3)."
  [;; Constant near-black behind the video in both appearances. Deliberately
   ;; not a flipping token: a white flash before the first frame is worse
   ;; than a permanently dark backdrop, and every video surface agrees.
   [(str "#" container-id)
    {:position "relative"
     :border-radius "var(--hig-radius-large, 16px)"
     :overflow "hidden"
     :background "black"
     :aspect-ratio "16 / 9"
     :display "flex"
     :align-items "center"
     :justify-content "center"}]
   [(str "#" video-id)
    {:width "100%" :height "100%" :display "block"
     :object-fit "contain" :background "black"}]
   ;; Only show the element once something is actually attached; until then
   ;; the box holds the status line alone.
   [(str "#" container-id "[data-mode=\"unknown\"] #" video-id ", "
         "#" container-id "[data-mode=\"idle\"] #" video-id ", "
         "#" container-id "[data-mode=\"error\"] #" video-id)
    {:display "none"}]
   [(str "#" status-id)
    {:position "absolute" :left "var(--hig-spacing-3, 14px)"
     :bottom "var(--hig-spacing-3, 14px)"
     :font-size "var(--hig-text-caption1-font-size)"
     :color "white" :background "rgba(0,0,0,.45)"
     :border-radius "var(--hig-radius-small, 8px)"
     :padding "4px 10px"}]
   ;; With no video behind it the pill has nothing to sit on, so centre the
   ;; text instead of parking it in the corner of an empty black rectangle.
   [(str "#" container-id "[data-mode=\"unknown\"] #" status-id ", "
         "#" container-id "[data-mode=\"idle\"] #" status-id ", "
         "#" container-id "[data-mode=\"error\"] #" status-id)
    {:position "static" :background "transparent"
     :font-size "var(--hig-text-body-font-size)" :text-align "center"}]])

(defn css
  "The player rules as a CSS string, for a host that inlines its own
  `<style>`."
  []
  (css/css {:rules rules}))

(defn player
  "The player fragment.

  opts:
    :mode    initial `data-mode` (default \"unknown\") — server-rendered so
             the box is not blank before the script runs
    :status  initial status text
    :label   accessible name for the video element"
  ([] (player nil))
  ([{:keys [mode status label]
     :or {mode "unknown" status "checking…" label "live video"}}]
   [:div {:id container-id :data-mode mode}
    [:video {:id video-id :playsinline true :controls true :muted true
             :aria-label label}]
    [:div {:id status-id :role "status"} status]]))

(defn section
  "The player wrapped in a `kotoba-ui.shell/section`, with optional
  `:title` and `:note` copy around it — the shape both current hosts want."
  [{:keys [title note] :as opts}]
  (shell/section
   (cond-> {:wide true} title (assoc :title title))
   (shell/stack {:gap :3}
                (player opts)
                (when note [:p.hig-footnote note]))))
