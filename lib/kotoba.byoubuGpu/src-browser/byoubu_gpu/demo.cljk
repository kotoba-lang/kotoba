(ns byoubu-gpu.demo
  "The tier-2 demo page and its own evidence.

  Mounts every catalog backdrop live, and exposes `window.byoubuGpu` so a
  browser test can drive it: which tier each canvas resolved to, how many
  frames it presented, and the mean colour of the content band read back off
  the real swapchain. That last one is the point — it is the same measurement
  the plate and poster tiers went through, so tier 2 lands in the catalog as a
  number rather than a screenshot somebody looked at once."
  (:require [byoubu.core :as byoubu]
            [byoubu-gpu.core :as gpu]))

(defonce handles (atom {}))

(defn- canvas-for [id]
  (.querySelector js/document (str "canvas[data-backdrop='" (name id) "']")))

(defn- sample-band
  "Mean sRGB over the content band — full width, 30%..75% of height — read
  back from the canvas. Same window the plate and poster were measured in."
  [canvas]
  (let [w (.-width canvas) h (.-height canvas)
        off (js/document.createElement "canvas")
        _   (set! (.-width off) w)
        _   (set! (.-height off) h)
        c2  (.getContext off "2d")]
    (.drawImage c2 canvas 0 0)
    (let [y0 (js/Math.round (* h 0.30))
          y1 (js/Math.round (* h 0.75))
          d  (.-data (.getImageData c2 0 y0 w (- y1 y0)))
          n  (/ (.-length d) 4)]
      (loop [i 0 r 0 g 0 b 0]
        (if (< i (.-length d))
          (recur (+ i 4) (+ r (aget d i)) (+ g (aget d (+ i 1))) (+ b (aget d (+ i 2))))
          (let [hx (fn [v] (let [s (.toString (js/Math.round (/ v n)) 16)]
                             (if (= 1 (.-length s)) (str "0" s) s)))]
            (str "#" (hx r) (hx g) (hx b))))))))

(defn ^:export init! []
  (doseq [id (byoubu/ids)]
    (when-let [cv (canvas-for id)]
      (-> (gpu/mount! cv id {:animate? false})
          (.then (fn [h]
                   (swap! handles assoc id h)
                   (set! (.-textContent (.querySelector js/document
                                                        (str "#status-" (name id))))
                         (str (name (:tier h))
                              (when-let [r (:reason h)] (str " — " r)))))))))
  ;; test surface
  (set! (.-byoubuGpu js/window)
        #js {:tiers (fn [] (clj->js (into {} (for [[k v] @handles] [(name k) (name (:tier v))]))))
             :reasons (fn [] (clj->js (into {} (for [[k v] @handles :when (:reason v)]
                                                 [(name k) (:reason v)]))))
             :frames (fn [] (clj->js (into {} (for [[k v] @handles]
                                                [(name k) (if-let [f (:frames v)] @f 0)]))))
             :ready (fn [] (= (count @handles) (count (byoubu/ids))))
             :sample (fn [id]
                       (if-let [cv (canvas-for (keyword id))]
                         (sample-band cv)
                         nil))}))
