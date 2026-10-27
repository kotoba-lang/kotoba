(ns browser.input
  "Canonical pointer/keyboard event reducer for the kotoba-only browser surface.

   Host adapters and aiueos providers normalize their own event names into this
   vocabulary before reducing against browser.surface."
  (:require [browser.surface :as surface]))

(def titlebar-height 28)
(def resize-handle-size 16)

(defn empty-state
  []
  {:pointer/position [0 0]
   :pointer/capture nil})

(defn- point-in-rect?
  [[px py] [x y w h]]
  (and (<= x px (+ x w))
       (<= y py (+ y h))))

(defn window-at
  [surface point]
  (first (filter #(point-in-rect? point (:window/rect %))
                 (reverse (:surface/windows surface)))))

(defn- in-titlebar?
  [[px py] [_x y _w _h]]
  (<= y py (+ y titlebar-height)))

(defn- in-resize-handle?
  [[px py] [x y w h]]
  (and (<= (- (+ x w) resize-handle-size) px (+ x w))
       (<= (- (+ y h) resize-handle-size) py (+ y h))))

(defn normalize-event
  "Converts host/aiueos event records into the browser input vocabulary."
  [event]
  (let [cap (or (:aiueos/capability event) (:capability event))
        t (:event/type event)]
    (cond
      (= cap "pointer/move")
      (merge {:event/type :pointer/move :x (:x event) :y (:y event)}
             (select-keys event [:pointerId :pointerType :isPrimary
                                 :pointer-id :pointer-type :is-primary?
                                 :pressure :width :height]))

      (= cap "pointer/down")
      (merge {:event/type :pointer/down
              :button (or (:button event) 0)
              :x (:x event)
              :y (:y event)}
             (select-keys event [:pointerId :pointerType :isPrimary
                                 :pointer-id :pointer-type :is-primary?
                                 :pressure :width :height]))

      (= cap "pointer/up")
      (merge {:event/type :pointer/up
              :button (or (:button event) 0)
              :x (:x event)
              :y (:y event)}
             (select-keys event [:pointerId :pointerType :isPrimary
                                 :pointer-id :pointer-type :is-primary?
                                 :pressure :width :height]))

      (= cap "pointer/cancel")
      (merge {:event/type :pointer/cancel
              :x (:x event)
              :y (:y event)}
             (select-keys event [:pointerId :pointerType :isPrimary
                                 :pointer-id :pointer-type :is-primary?
                                 :pressure :width :height]))

      (= cap "pointer/click")
      (merge {:event/type :pointer/click
              :button (or (:button event) 0)
              :x (:x event)
              :y (:y event)}
             (select-keys event [:pointerId :pointerType :isPrimary
                                 :pointer-id :pointer-type :is-primary?
                                 :pressure :width :height]))

      (= cap "pointer/wheel")
      (merge {:event/type :pointer/wheel
              :x (:x event)
              :y (:y event)
              :delta-x (or (:delta-x event) (:deltaX event) 0)
              :delta-y (or (:delta-y event) (:deltaY event) 0)}
             (select-keys event [:pointerId :pointerType :isPrimary
                                 :pointer-id :pointer-type :is-primary?
                                 :pressure :width :height]))

      (= cap "keyboard/key")
      ;; document-input's own key-event builder already fully supports
      ;; :alt?/:repeat? (checks (contains? event :alt?)/:repeat? to set
      ;; a dispatched KeyboardEvent's real altKey/repeat fields) -- this
      ;; branch silently dropped both, so a real Alt-modified keypress or
      ;; a real OS-level key-repeat (a held-down key) reached a page's
      ;; own addEventListener('keydown', ...) listener with altKey/repeat
      ;; always false, regardless of what the host actually reported.
      ;; Confirmed via direct REPL reproduction before touching source.
      (cond-> {:event/type :key/down :key (:key event)}
        (:shift? event) (assoc :shift? true)
        (:ctrl? event) (assoc :ctrl? true)
        (:meta? event) (assoc :meta? true)
        (:alt? event) (assoc :alt? true)
        (:repeat? event) (assoc :repeat? true))

      (= cap "keyboard/type")
      {:event/type :text/input :text (:text event)}

      (= cap "text/composition-start")
      {:event/type :composition/start}

      (= cap "text/composition-update")
      {:event/type :composition/update :text (:text event)}

      (= cap "text/composition-end")
      {:event/type :composition/end :text (:text event)}

      (#{:pointer/down :pointer/move :pointer/up :pointer/cancel
         :pointer/click :pointer/wheel
         :key/down :key/up :text/input
         :text/caret :text/selection
         :composition/start :composition/update :composition/end
         :select/change :file/select} t)
      event

      (= t :dom/click)
      (assoc event :event/type :pointer/click)

      (= t :dom/input)
      {:event/type :text/input :text (:value event)}

      :else
      (assoc event :event/type :unknown))))

(defn- event-point
  [input event]
  (let [event (normalize-event event)]
    [(or (:x event) (first (:pointer/position input)) 0)
     (or (:y event) (second (:pointer/position input)) 0)]))

(defn actions-for-event
  [surface input event]
  (let [event (normalize-event event)
        point (event-point input event)
        focused (:surface/focus surface)]
    (case (:event/type event)
      :pointer/down
      (if-let [window (window-at surface point)]
        (let [[x y w h] (:window/rect window)
              id (:window/id window)
              action (cond
                       (in-resize-handle? point (:window/rect window))
                       {:kind :resize
                        :window-id id
                        :origin point
                        :start-size [w h]}

                       (in-titlebar? point (:window/rect window))
                       {:kind :drag
                        :window-id id
                        :offset [(- (first point) x) (- (second point) y)]})]
          {:input (assoc input
                         :pointer/position point
                         :pointer/capture action)
           :actions [{:action :window/focus :window-id id}]})
        {:input (assoc input :pointer/position point)
         :actions []})

      :pointer/move
      (let [capture (:pointer/capture input)
            action (case (:kind capture)
                     :drag
                     (let [[dx dy] (:offset capture)]
                       {:action :window/move
                        :window-id (:window-id capture)
                        :position [(- (first point) dx) (- (second point) dy)]})

                     :resize
                     (let [[ox oy] (:origin capture)
                           [sw sh] (:start-size capture)]
                       {:action :window/resize
                        :window-id (:window-id capture)
                        :size [(max 120 (+ sw (- (first point) ox)))
                               (max 80 (+ sh (- (second point) oy)))]})

                     nil)]
        {:input (assoc input :pointer/position point)
         :actions (cond-> [] action (conj action))})

      :pointer/up
      {:input (assoc input :pointer/position point :pointer/capture nil)
       :actions []}

      ;; A real pointercancel (an interrupted gesture -- capture stolen by
      ;; the OS/another surface, a multi-touch conflict, etc.) ends the
      ;; current pointer interaction exactly like pointerup does, per the
      ;; Pointer Events spec. This case was previously entirely absent, so
      ;; it silently fell through to the default no-op clause below and
      ;; left :pointer/capture untouched -- a canceled titlebar-drag or
      ;; resize-handle-drag stayed "captured," so the very next unrelated
      ;; :pointer/move (from a totally different gesture) was misinterpreted
      ;; as a continuation of the old drag/resize. Confirmed via direct REPL
      ;; reproduction before this fix: down -> cancel -> an unrelated move
      ;; to a far-away point still relocated the window as if the drag were
      ;; still live.
      :pointer/cancel
      {:input (assoc input :pointer/position point :pointer/capture nil)
       :actions []}

      :pointer/click
      (if-let [window (window-at surface point)]
        {:input (assoc input :pointer/position point)
         :actions [{:action :window/focus :window-id (:window/id window)}]}
        {:input (assoc input :pointer/position point)
         :actions []})

      :pointer/wheel
      (if-let [window (window-at surface point)]
        {:input (assoc input :pointer/position point)
         :actions [{:action :window/scroll
                    :window-id (:window/id window)
                    :delta-x (:delta-x event)
                    :delta-y (:delta-y event)
                    :x (first point)
                    :y (second point)}]}
        {:input (assoc input :pointer/position point)
         :actions []})

      :key/down
      (let [edit-action (case (:key event)
                          "Backspace" {:action :text/edit :window-id focused
                                       :text/op :delete-backward}
                          "Delete" {:action :text/edit :window-id focused
                                    :text/op :delete-forward}
                          "ArrowLeft" {:action :text/edit :window-id focused
                                       :text/op :move-caret :delta -1
                                       :extend? (:shift? event)}
                          "ArrowRight" {:action :text/edit :window-id focused
                                        :text/op :move-caret :delta 1
                                        :extend? (:shift? event)}
                          "Home" {:action :text/edit :window-id focused
                                  :text/op :move-to :caret 0
                                  :extend? (:shift? event)}
                          "End" {:action :text/edit :window-id focused
                                 :text/op :move-to-end
                                 :extend? (:shift? event)}
                          "a" (when (or (:meta? event) (:ctrl? event))
                                {:action :text/edit :window-id focused
                                 :text/op :select-all})
                          "A" (when (or (:meta? event) (:ctrl? event))
                                {:action :text/edit :window-id focused
                                 :text/op :select-all})
                          nil)]
        {:input input
         :actions (cond-> [{:action :keyboard/key :window-id focused :key (:key event)}]
                    edit-action (conj edit-action))})

      :text/input
      {:input input
       :actions [{:action :text/input :window-id focused :text (:text event)}]}

      :text/caret
      {:input input
       :actions [{:action :text/edit :window-id focused
                  :text/op :caret :caret (:caret event)}]}

      :text/selection
      {:input input
       :actions [{:action :text/edit :window-id focused
                  :text/op :select :start (:start event) :end (:end event)}]}

      :composition/start
      {:input input
       :actions [{:action :text/edit :window-id focused
                  :text/op :composition-start}]}

      :composition/update
      {:input input
       :actions [{:action :text/edit :window-id focused
                  :text/op :composition-update :text (:text event)}]}

      :composition/end
      {:input input
       :actions [{:action :text/edit :window-id focused
                  :text/op :composition-end :text (:text event)}]}

      {:input input :actions []})))

(defn reduce-event
  [surface input event]
  (let [{:keys [input actions]} (actions-for-event surface input event)]
    {:surface (surface/apply-actions surface actions)
     :input input
     :actions actions}))

(defn reduce-events
  ([surface events]
   (reduce-events surface (empty-state) events))
  ([surface input events]
   (reduce (fn [{:keys [surface input actions]} event]
             (let [result (reduce-event surface input event)]
               (update result :actions #(into actions %))))
           {:surface surface :input input :actions []}
           events)))
