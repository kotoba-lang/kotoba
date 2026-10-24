(ns editor.core
  "A portable structural-EDN editor: walk a map, surface every editable number/colour
   as a labelled leaf, edit it with `assoc-in`. No DOM, no re-frame, no host effects —
   a consuming app supplies the UI (sliders, colour pickers) and the persistence.
   Same separation kotoba-lang/kuro uses for terminal sessions (portable data model;
   host provides the effects). See README for the full rationale."
  (:require [kotoba.lang.text :as str]))

(def ^:private max-depth 3)

(defn color-vec?
  "A [r g b] vector of numbers in [0,1] — the palette convention already common across
   kotoba-lang/etzhayyim consumers (skins, hues, materials)."
  [v]
  (and (vector? v) (= 3 (count v)) (every? number? v) (every? #(<= 0 % 1) v)))

(defn- label [path]
  (str/join " › " (map name path)))

(defn editable-paths
  "Walk `data` up to `max-depth` and collect every editable leaf as
   `{:path [...] :value v :kind :number|:color :label \"a › b\"}`. Colour vectors are
   matched before generic numbers (a colour IS a vector of numbers, but isn't a further
   map level to recurse into). Booleans/keywords/strings/other structures are left
   alone — this is a numbers-and-colours editor, not a general EDN editor."
  ([data] (editable-paths data [] 0))
  ([data path depth]
   (cond
     (color-vec? data)
     [{:path path :value data :kind :color :label (label path)}]

     (and (map? data) (< depth max-depth))
     (vec (mapcat (fn [[k v]] (editable-paths v (conj path k) (inc depth))) data))

     (number? data)
     [{:path path :value data :kind :number :label (label path)}]

     :else [])))

(defn set-value
  "Apply an edited value back into `data` at `path` — pure, structural."
  [data path v]
  (assoc-in data path v))

;; --- colour <-> hex, for an <input type=color> ---------------------------------------

(defn- clamp01 [x] (max 0.0 (min 1.0 x)))
(defn- ->255 [x] #?(:clj (Math/round (* 255.0 (clamp01 x)))
                     :cljs (js/Math.round (* 255.0 (clamp01 x)))))
(defn- hex2 [n] (let [s #?(:clj (Integer/toHexString n) :cljs (.toString n 16))]
                  (if (= 1 (count s)) (str "0" s) s)))

(defn color->hex
  "[r g b] (0..1 floats) → \"#rrggbb\"."
  [[r g b]]
  (str "#" (hex2 (->255 r)) (hex2 (->255 g)) (hex2 (->255 b))))

(defn hex->color
  "\"#rrggbb\" → [r g b] (0..1 floats)."
  [hex]
  (let [h (str/replace hex "#" "")
        n (fn [i] #?(:clj (Integer/parseInt (subs h (* 2 i) (+ 2 (* 2 i))) 16)
                     :cljs (js/parseInt (subs h (* 2 i) (+ 2 (* 2 i))) 16)))]
    [(/ (n 0) 255.0) (/ (n 1) 255.0) (/ (n 2) 255.0)]))

;; --- a reasonable slider range for a number we've never seen before ------------------

(defn slider-bounds
  "A heuristic [min max step] for a number with no declared schema: scale around the
   current value so the slider is always usable (0 → [0 10 0.1]; negative → mirrored;
   otherwise half..double, floored at a sane minimum). Not exact, but every value stays
   reachable and the slider is never degenerate (min == max)."
  [v]
  (cond
    (zero? v) [0.0 10.0 0.1]
    (neg? v)  (let [a #?(:clj (Math/abs (double v)) :cljs (js/Math.abs v))]
                [(* -2 a) (* -0.5 a) (max 0.01 (/ a 100.0))])
    :else     [(* 0.5 (double v)) (* 2.0 (double v)) (max 0.01 (/ v 100.0))]))
