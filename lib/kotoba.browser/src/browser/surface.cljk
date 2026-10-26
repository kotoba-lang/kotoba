(ns browser.surface
  "Kotoba-only OS/browser UI surface.

   This is the shell model for using the browser UI as the OS UI itself. It is
   still just kotoba DOM data and host ABI ops: windows, panels, and launchers
   are document nodes, not native widgets."
  (:require [browser.text-edit :as text-edit]
            [cssom.layout :as layout]
            [kotoba.wasm.dom :as dom]))

(def default-theme
  {:font-size 14
   :line-height 20
   :padding 6
   :gap 6
   :fg "#111111"
   :bg "#f5f6f8"
   :button-bg "#e4e8ef"})

(defn empty-surface
  ([] (empty-surface {}))
  ([opts]
   {:surface/id (or (:id opts) "kotoba-os")
    :surface/title (or (:title opts) "Kotoba")
    :surface/viewport (or (:viewport opts) [1280 800])
    :surface/theme (merge default-theme (:theme opts))
    :surface/apps []
    :surface/windows []
    :surface/focus nil
    :surface/input-log []
    :surface/next-window-id 1}))

(defn register-app
  [surface app]
  (update surface :surface/apps conj app))

(defn- next-window-id
  [surface]
  [(str "w" (:surface/next-window-id surface))
   (update surface :surface/next-window-id inc)])

(defn open-window
  [surface {:keys [app-id title rect document] :as window}]
  (let [[id surface] (next-window-id surface)
        window (merge {:window/id id
                       :window/app-id app-id
                       :window/title (or title app-id id)
                       :window/rect (or rect [80 80 520 360])
                       :window/document document
                       :window/text (text-edit/empty-state)
                       :window/state :normal}
                      (dissoc window :app-id :title :rect :document))]
    (-> surface
        (update :surface/windows conj window)
        (assoc :surface/focus id))))

(defn close-window
  "Close window-id. If it was the focused window, focus the last remaining
   window (matching open-window's own convention of always focusing the most
   recently opened one) instead of leaving :surface/focus nil -- real
   window-manager UX always transfers focus to another open window rather
   than dropping it, and every input action in apply-action (keyboard/text/
   scroll) that omits an explicit window-id targets (:surface/focus surface),
   so leaving it nil here would silently swallow the user's next keystroke
   until they explicitly refocused something, even with other windows still
   open."
  [surface window-id]
  (let [remaining (vec (remove #(= (:window/id %) window-id) (:surface/windows surface)))
        was-focused? (= (:surface/focus surface) window-id)]
    (assoc surface
           :surface/windows remaining
           :surface/focus (if was-focused?
                            (:window/id (peek remaining))
                            (:surface/focus surface)))))

(defn focus-window
  "Focus window-id, and raise it to the end of :surface/windows (this
   codebase's own z-order convention: window-node renders windows in
   :surface/windows order, later = drawn on top, and window-at's hit-test
   walks that same order in reverse to find the topmost window under a
   point) -- without this, focus and stacking order can permanently
   diverge: once two windows overlap, whichever was opened LATER always
   wins the overlap region's hit-test forever, even after the user clicks
   to focus the other one, since focus alone never changed which window
   renders on top. Real window-manager UX always raises a window when it
   becomes focused."
  [surface window-id]
  (if (some #(= (:window/id %) window-id) (:surface/windows surface))
    (-> surface
        (assoc :surface/focus window-id)
        (update :surface/windows
                (fn [windows]
                  (let [target (first (filter #(= (:window/id %) window-id) windows))
                        others (remove #(= (:window/id %) window-id) windows)]
                    (vec (concat others [target]))))))
    surface))

(defn move-window
  [surface window-id [x y]]
  (update surface :surface/windows
          (fn [windows]
            (mapv (fn [w]
                    (if (= (:window/id w) window-id)
                      (update w :window/rect (fn [[_ _ ww hh]] [x y ww hh]))
                      w))
                  windows))))

(defn resize-window
  [surface window-id [w h]]
  (update surface :surface/windows
          (fn [windows]
            (mapv (fn [window]
                    (if (= (:window/id window) window-id)
                      (update window :window/rect (fn [[x y _ _]] [x y w h]))
                      window))
                  windows))))

(defn record-key
  [surface window-id key]
  (update surface :surface/input-log conj
          {:event :keyboard/key :window-id window-id :key key}))

(defn scroll-window
  [surface window-id delta-x delta-y]
  (-> surface
      (update :surface/input-log conj
              {:event :window/scroll
               :window-id window-id
               :delta-x delta-x
               :delta-y delta-y})
      (update :surface/windows
              (fn [windows]
                (mapv (fn [window]
                        (if (= (:window/id window) window-id)
                          (let [[x y] (or (:window/scroll window) [0 0])]
                            (assoc window :window/scroll [(max 0 (+ x delta-x))
                                                          (max 0 (+ y delta-y))]))
                          window))
                      windows)))))

(defn append-text
  [surface window-id text]
  (-> surface
      (update :surface/input-log conj
              {:event :text/input :window-id window-id :text text})
      (update :surface/windows
              (fn [windows]
                (mapv (fn [window]
                        (if (= (:window/id window) window-id)
                          (let [edited (text-edit/insert-text
                                        (or (:window/text window) (text-edit/empty-state))
                                        text)]
                            (assoc window
                                   :window/text edited
                                   :window/text-buffer (:text/value edited)))
                          window))
                      windows)))))

(defn edit-text
  [surface window-id op]
  (update surface :surface/windows
          (fn [windows]
            (mapv (fn [window]
                    (if (= (:window/id window) window-id)
                      (let [state (or (:window/text window) (text-edit/empty-state))
                            edited (case (:text/op op)
                                     :caret (text-edit/collapse state (:caret op))
                                     :select (text-edit/select state (:start op) (:end op))
                                     :delete-backward (text-edit/delete-backward state)
                                     :delete-forward (text-edit/delete-forward state)
                                     :move-caret (text-edit/move-caret state (:delta op) {:extend? (:extend? op)})
                                     :move-to (text-edit/move-to state (:caret op) {:extend? (:extend? op)})
                                     :move-to-end (text-edit/move-to state
                                                                     (count (:text/value state ""))
                                                                     {:extend? (:extend? op)})
                                     :select-all (text-edit/select-all state)
                                     :composition-start (text-edit/composition-start state)
                                     :composition-update (text-edit/composition-update state (:text op))
                                     :composition-end (text-edit/composition-end state (:text op))
                                     state)]
                        (assoc window
                               :window/text edited
                               :window/text-buffer (:text/value edited)))
                      window))
                  windows))))

(defn app-by-id
  [surface app-id]
  (first (filter #(= (:app/id %) app-id) (:surface/apps surface))))

(defn launch-app
  [surface app-id]
  (if-let [app (app-by-id surface app-id)]
    (open-window surface
                 {:app-id app-id
                  :title (:app/title app)
                  :rect (:app/default-rect app)
                  :document (if-let [f (:app/document-fn app)]
                              (f {:surface surface :app app})
                              (:app/document app))})
    surface))

(defn apply-action
  "Pure surface reducer. Host input adapters should translate pointer/keyboard
   events into this action vocabulary before entering the WASM guest."
  [surface {:keys [action app-id window-id position size key text delta-x delta-y] :as event}]
  (case action
    :app/launch (launch-app surface app-id)
    :window/focus (focus-window surface window-id)
    :window/close (close-window surface window-id)
    :window/move (move-window surface window-id position)
    :window/resize (resize-window surface window-id size)
    :window/scroll (scroll-window surface (or window-id (:surface/focus surface))
                                  (or delta-x 0)
                                  (or delta-y 0))
    :keyboard/key (record-key surface (or window-id (:surface/focus surface)) key)
    :text/input (append-text surface (or window-id (:surface/focus surface)) text)
    :text/edit (edit-text surface (or window-id (:surface/focus surface)) event)
    :surface/noop surface
    surface))

(defn apply-actions
  [surface actions]
  (reduce apply-action surface actions))

(defn- style
  [m]
  (into {} (remove (comp nil? val) m)))

(defn- append-text!
  [document parent-id text]
  (let [[id document] (dom/create-text-node document text)]
    (dom/append-child document parent-id id)))

(defn- element!
  [document parent-id tag attrs]
  (let [[id document] (dom/create-element document tag)
        document (reduce-kv (fn [d k v]
                              (if (= k :style)
                                (dom/set-style d id v)
                                (dom/set-attribute d id k v)))
                            document
                            attrs)
        document (if parent-id (dom/append-child document parent-id id) document)]
    [id document]))

(declare render-node!)

(defn- render-content!
  [document parent-id content]
  (cond
    (nil? content)
    document

    (string? content)
    (append-text! document parent-id content)

    (vector? content)
    (render-node! document parent-id content)

    (sequential? content)
    (reduce #(render-content! %1 parent-id %2) document content)

    :else
    (append-text! document parent-id (str content))))

(defn render-node!
  [document parent-id [tag & body]]
  (let [[attrs children] (if (map? (first body))
                           [(first body) (rest body)]
                           [{} body])
        [id document] (element! document parent-id tag attrs)]
    (reduce #(render-content! %1 id %2) document children)))

(defn- window-node
  [surface window focused?]
  (let [[x y w h] (:window/rect window)]
    [:section {:class (str "window" (when focused? " focused"))
               :data-window-id (:window/id window)
               :style (style {:padding 0
                              :width w
                              :height h
                              :background (if focused? "#ffffff" "#eef1f5")})}
     [:header {:class "titlebar"
               :style {:background (if focused? "#d8e7ff" "#dde2ea")
                       :padding 6}}
      (:window/title window)]
     [:main {:class "window-body"
             :style {:padding 8
                     :background "#ffffff"}}
      (or (:window/document window)
          [:p (str "app " (:window/app-id window) " has no document")])]
     [:footer {:class "window-geometry"
               :style {:padding 4 :font-size 12 :color "#5f6875"}}
      (str x "," y " " w "x" h)]]))

(defn surface-node
  [surface]
  [:main {:class "kotoba-os"
          :data-surface-id (:surface/id surface)
          :style {:background "#f5f6f8" :padding 8}}
   [:header {:class "topbar"
             :style {:background "#ffffff" :padding 8}}
    (:surface/title surface)]
   [:nav {:class "launcher"
          :style {:background "#edf0f5" :padding 6}}
    (for [{:app/keys [id title]} (:surface/apps surface)]
      [:button {:data-app-id id :style {:padding 6}} (or title id)])]
   [:section {:class "workspace"
              :style {:background "#f5f6f8" :padding 8}}
    (for [window (:surface/windows surface)]
      (window-node surface window (= (:window/id window) (:surface/focus surface))))]])

(defn render-surface
  [surface]
  (let [[root-id document] (dom/create-element dom/empty-document :surface)
        document (dom/set-root document root-id)
        document (render-node! document root-id (surface-node surface))
        [ops document] (dom/consume-ops document)
        tree (dom/tree document)
        [width _height] (:surface/viewport surface)
        draw-ops (layout/draw-ops tree {:width width
                                        :theme (:surface/theme surface)})]
    {:surface surface
     :document document
     :tree tree
     :ops ops
     :draw-ops draw-ops}))
