(ns kami.input
  "hiccup for input — key/pointer bindings described as EDN data, interpreted into axes
   and actions. The binding map is data: store it as datoms, fork it, rebind without code.

     {:axes    {\"MoveX\" {:pos #{\"d\" \"ArrowRight\"} :neg #{\"a\" \"ArrowLeft\"} :scale 220.0}
                \"MoveY\" {:pos #{\"w\" \"ArrowUp\"}    :neg #{\"s\" \"ArrowDown\"} :scale 220.0}}
      :actions {:jump #{\" \"} :fire #{\"f\"}}
      :stick   {:x \"MoveX\" :y \"MoveY\" :radius 72.0 :dead 0.12}}

   `:scale` is the axis's full-deflection magnitude (an axis with no `:scale` reports the
   raw -1/0/1 it always did). This is what lets a scene say \"the player moves at 220 world
   units per second\" as *data* rather than as a constant baked into every game's guest
   code — see `axis-scale`'s docstring for why the host, not the guest, owns it.

   `:stick` is the pointer/touch half of the same idea: a drag on the game surface deflects
   the two named axes exactly as far as the keys would, so a game authored against MoveX/
   MoveY is playable on a phone without a second input path.

   `wire!` attaches listeners that read the map and report axis/action changes; it returns
   an unsubscribe fn. The same EDN map drives any executor (web here; a native input layer
   reads the identical data). Everything above `wire!` is pure `.cljc` — the interpretation
   is data, not platform code, and is unit-tested on the JVM.")

(def default-map
  {:axes    {"MoveX" {:pos #{"d" "D" "ArrowRight"} :neg #{"a" "A" "ArrowLeft"}}
             "MoveY" {:pos #{"w" "W" "ArrowUp"}    :neg #{"s" "S" "ArrowDown"}}}
   :actions {:jump #{" "} :fire #{"f" "F"}}})

(def default-stick
  "Pointer-drag defaults. `:radius` is the drag distance (CSS px) that counts as full
   deflection; `:dead` is the fraction of it ignored so a tap doesn't twitch the player;
   `:zone` is the `[x0 y0 x1 y1]` fraction of the surface a drag must start inside."
  {:x "MoveX" :y "MoveY" :radius 72.0 :dead 0.12 :zone [0.0 0.0 1.0 1.0]})

(defn stick-spec
  "The resolved single-`:stick` spec — defaults, plus whatever the scene declared. `:stick
   false` (the opt-out) resolves to the defaults so the *names* stay readable; `sticks` is
   what actually gates the behaviour."
  [imap]
  (merge default-stick (when (map? (:stick imap)) (:stick imap))))

(defn sticks
  "Every pointer stick this input map exposes, in match order.

   One stick over the whole surface is the default and covers any game steered by MoveX/
   MoveY. `:sticks` declares several with `:zone`s instead — a game with a third driven
   axis needs a second thumb, or it is keyboard-only on a phone no matter how good the
   single stick is. `:stick false` opts out entirely."
  [imap]
  (cond
    (false? (:stick imap)) []
    (seq (:sticks imap)) (mapv #(merge default-stick %) (:sticks imap))
    :else (let [s (stick-spec imap)]
            (if (or (some? (:stick imap))
                    (and (contains? (:axes imap) (:x s))
                         (contains? (:axes imap) (:y s))))
              [s]
              []))))

(defn stick-at
  "The stick a drag starting at the surface point `[nx ny]` (0..1) belongs to, or nil."
  [imap [nx ny]]
  (some (fn [s]
          (let [[x0 y0 x1 y1] (:zone s [0.0 0.0 1.0 1.0])]
            (when (and (<= x0 nx x1) (<= y0 ny y1)) s)))
        (sticks imap)))

(defn axis-scale
  "The full-deflection magnitude of `axis` in `imap` (1.0 when the axis declares none).

   Why the host owns this: a guest reading `(axis \"MoveX\")` and multiplying by its own
   speed constant would have to spend an f32 constant per game and could never be retuned
   by forking the scene EDN. Scaling here keeps `set-velocity!` a straight pass-through of
   the axis (`(set-velocity! p (axis \"MoveX\") (axis \"MoveY\") zero)`) — the idiom every
   game in the catalog already writes — while the *magnitude* stays authorable data."
  [imap axis]
  (or (get-in imap [:axes axis :scale]) 1.0))

(defn with-axis-scale
  "Return `imap` with `scale` applied as the default `:scale` of every axis that doesn't
   declare one of its own. Lets a scene state one world-level speed and still override a
   single axis (a plane's climb rate vs its cruise) without repeating itself."
  [imap scale]
  (if (and (number? scale) (pos? scale))
    (update imap :axes
            (fn [axes]
              (reduce-kv (fn [m k v] (assoc m k (update v :scale #(or % scale)))) {} axes)))
    imap))

(defn axes-from-held
  "Pure: given the input-map and the set of currently-held keys, return {axis value}, each
   in [-scale,scale] (so [-1,1] for an axis with no `:scale`). Works in CLJ or CLJS — the
   binding logic is data, not platform code."
  [imap held]
  (reduce-kv (fn [m axis {:keys [pos neg scale]}]
               ;; an axis with no :scale is left as the exact integer -1/0/1 it always
               ;; reported — multiplying by 1.0 would widen it to a double and change what
               ;; every existing caller sees for no reason.
               (let [d (- (if (some held pos) 1 0) (if (some held neg) 1 0))]
                 (assoc m axis (if scale (* scale d) d))))
             {} (:axes imap)))

(defn- clamp1 [^double v] (max -1.0 (min 1.0 v)))

(defn- sqrt [^double v]
  #?(:clj (Math/sqrt v) :cljs (js/Math.sqrt v)))

(defn stick-axes
  "Pure: the axis values for a pointer drag from `[ox oy]` to `[px py]`, in the same units
   `axes-from-held` reports (so a full-radius drag equals holding the key).

   Screen y grows downward while the `MoveY`-style axis's `:pos` is bound to up/forward
   keys, so the y deflection is inverted — a drag *up* the screen reads as +1, matching
   what W/ArrowUp does. Deflection is clamped to the unit disc, so a drag past the radius
   saturates instead of overshooting the keyboard's own maximum.

   The 3-arity uses the input map's single `:stick`; the 4-arity takes one resolved spec
   (from `sticks`/`stick-at`), which is how a two-thumb layout drives its two sticks."
  ([imap origin point] (stick-axes imap (stick-spec imap) origin point))
  ([imap {:keys [x y radius dead]} [ox oy] [px py]]
  (let [r (max 1.0 (double radius))
        dx (clamp1 (/ (- (double px) (double ox)) r))
        dy (clamp1 (/ (- (double oy) (double py)) r))
        mag (sqrt (+ (* dx dx) (* dy dy)))
        dead (double dead)
        ;; past the dead zone, rescale so the first live pixel is a small push, not a jump
        k (if (> mag dead)
            (/ (min 1.0 (/ (- mag dead) (max 1.0e-6 (- 1.0 dead)))) mag)
            0.0)]
    (cond-> {}
      x (assoc x (* (axis-scale imap x) dx k))
      y (assoc y (* (axis-scale imap y) dy k))))))

(defn stick-rest
  "Pure: the axis values for a released pointer — that stick's axes at zero."
  ([imap] (stick-rest imap (stick-spec imap)))
  ([_imap {:keys [x y]}]
   (cond-> {} x (assoc x 0.0) y (assoc y 0.0))))

(defn stick-enabled?
  "Does this input map expose any pointer stick at all?"
  [imap]
  (boolean (seq (sticks imap))))

(defn action-for [imap k]
  (some (fn [[a ks]] (when (contains? ks k) a)) (:actions imap)))

(defn bound-key?
  "Is `k` bound to any axis or action in `imap`? Used to scope preventDefault to keys the
   game actually consumes — Space and the arrows scroll the page otherwise, which on a
   full-bleed canvas game reads as the controls being broken."
  [imap k]
  (boolean
   (or (action-for imap k)
       (some (fn [[_ {:keys [pos neg]}]] (or (contains? pos k) (contains? neg k)))
             (:axes imap)))))

#?(:cljs
   (defn wire!
     "Interpret the EDN input-map against window key events and (when a `:target` element is
      given) pointer drags on that element. Calls (on-axes {axis v}) when an axis changes,
      (on-action kw down?) on bound action keys, and (on-pointer {:x :y :down?}) with the
      pointer in 0..1 surface coordinates. Returns an unsubscribe fn.

      Options: `:target` — the element pointer drags are read from (usually the game canvas).
      Omitted, only the keyboard is wired, exactly as before."
     [imap {:keys [on-axes on-action on-pointer target]}]
     (let [held (atom #{})
           ;; pointerId -> {:stick spec :origin [clientX clientY]}. Keyed by pointer, not a
           ;; single slot, so a two-thumb layout can drive both sticks at once.
           drags (atom {})
           recompute #(when on-axes (on-axes (axes-from-held imap @held)))
           kd (fn [e]
                (let [k (.-key e)]
                  (when (bound-key? imap k) (.preventDefault e))
                  (when-not (contains? @held k)
                    (swap! held conj k)
                    (when-let [a (action-for imap k)] (when on-action (on-action a true)))
                    (recompute))))
           ku (fn [e]
                (let [k (.-key e)]
                  (when (contains? @held k)
                    (swap! held disj k)
                    (when-let [a (action-for imap k)] (when on-action (on-action a false)))
                    (recompute))))
           surface (fn [e]
                     (let [r (.getBoundingClientRect target)
                           w (max 1.0 (.-width r)) h (max 1.0 (.-height r))]
                       {:x (/ (- (.-clientX e) (.-left r)) w)
                        :y (/ (- (.-clientY e) (.-top r)) h)}))
           pd (fn [e]
                (let [s (surface e)]
                  (when on-pointer (on-pointer (assoc s :down? true)))
                  (when-let [stick (stick-at imap [(:x s) (:y s)])]
                    (.preventDefault e)
                    (swap! drags assoc (.-pointerId e)
                           {:stick stick :origin [(.-clientX e) (.-clientY e)]})
                    (try (.setPointerCapture target (.-pointerId e)) (catch :default _ nil)))))
           pm (fn [e]
                (when on-pointer
                  (on-pointer (assoc (surface e) :down? (seq @drags))))
                (when-let [{:keys [stick origin]} (get @drags (.-pointerId e))]
                  (.preventDefault e)
                  (when on-axes
                    (on-axes (stick-axes imap stick origin
                                         [(.-clientX e) (.-clientY e)])))))
           pu (fn [e]
                (when-let [{:keys [stick]} (get @drags (.-pointerId e))]
                  (swap! drags dissoc (.-pointerId e))
                  (try (.releasePointerCapture target (.-pointerId e)) (catch :default _ nil))
                  ;; releasing one thumb rests only ITS axes — the other stick keeps flying
                  (when on-axes (on-axes (stick-rest imap stick)))))]
       (.addEventListener js/window "keydown" kd)
       (.addEventListener js/window "keyup" ku)
       (when target
         (.addEventListener target "pointerdown" pd)
         (.addEventListener target "pointermove" pm)
         (.addEventListener target "pointerup" pu)
         (.addEventListener target "pointercancel" pu))
       (fn []
         (.removeEventListener js/window "keydown" kd)
         (.removeEventListener js/window "keyup" ku)
         (when target
           (.removeEventListener target "pointerdown" pd)
           (.removeEventListener target "pointermove" pm)
           (.removeEventListener target "pointerup" pu)
           (.removeEventListener target "pointercancel" pu))))))
