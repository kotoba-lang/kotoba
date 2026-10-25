(ns computeruse.computer
  "Computer (desktop) abstraction — the host-capability boundary.

  The real desktop (xdotool/screencapture on a workstation, a VNC
  sandbox, an OS-automation MCP) is injected as an IComputer
  implementation; the library only consumes the protocol.
  `mock-computer` provides a pure-data virtual screen for tests and
  offline runs.

  Screenshots are whatever the host returns: a string description
  (mock), or Anthropic image content blocks
  [{:type \"image\" :source {:type \"base64\" …}}] (real host) —
  computeruse.tool passes them through to the tool result untouched."
  (:require [kotoba.lang.text :as str]))

(defprotocol IComputer
  (-screenshot [c])
  (-key! [c key-combo]   "e.g. \"ctrl+s\", \"Return\"")
  (-type! [c text])
  (-mouse-move! [c x y])
  (-click! [c button x y] "button: :left :right :middle :double")
  (-scroll! [c x y direction amount])
  (-cursor-position [c]  "→ [x y]"))

;; ───────────────────────── mock computer ─────────────────────────

(defn- render-screen [{:keys [screen cursor focus]}]
  (let [[w h] (:size screen)]
    (str "Screen " w "x" h ", cursor at " cursor "\n"
         (str/join "\n"
                   (map-indexed
                    (fn [i {:keys [title rect content]}]
                      (str (if (= i focus) "* " "  ")
                           "[" title "] rect=" rect
                           " content=\"" content "\""))
                    (:windows screen))))))

(defn- window-at [windows x y]
  (first (keep-indexed
          (fn [i {:keys [rect]}]
            (let [[rx ry rw rh] rect]
              (when (and (<= rx x (+ rx rw)) (<= ry y (+ ry rh)))
                i)))
          windows)))

(defn mock-computer
  "Virtual screen for tests/offline runs. Returns
  {:computer IComputer :state atom} — the atom exposes the screen,
  cursor, focused window, and an action :log for assertions.

  screen: {:size [w h]
           :windows [{:title \"Editor\" :rect [x y w h] :content \"…\"}]}

  Clicking inside a window focuses it; typing appends to the focused
  window's :content; the screenshot is a deterministic text rendering."
  [screen]
  (let [s (atom {:screen screen :cursor [0 0] :focus 0 :log []})
        log! (fn [entry] (swap! s update :log conj entry))]
    {:state s
     :computer
     (reify IComputer
       (-screenshot [_]
         (log! [:screenshot])
         (render-screen @s))
       (-key! [_ k]
         (log! [:key k])
         (str "Pressed " k))
       (-type! [_ text]
         (log! [:type text])
         (swap! s (fn [st] (update-in st [:screen :windows (:focus st) :content] str text)))
         (str "Typed " (pr-str text)))
       (-mouse-move! [_ x y]
         (log! [:mouse-move x y])
         (swap! s assoc :cursor [x y])
         (str "Moved to [" x " " y "]"))
       (-click! [_ button x y]
         (log! [:click button x y])
         (swap! s (fn [st]
                    (cond-> (assoc st :cursor [x y])
                      (window-at (get-in st [:screen :windows]) x y)
                      (assoc :focus (window-at (get-in st [:screen :windows]) x y)))))
         (str (name button) " click at [" x " " y "]"))
       (-scroll! [_ x y direction amount]
         (log! [:scroll x y direction amount])
         (str "Scrolled " (name direction) " by " amount))
       (-cursor-position [_] (:cursor @s)))}))
