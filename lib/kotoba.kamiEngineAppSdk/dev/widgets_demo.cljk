(ns widgets-demo
  "Self-test demo for `kami-ui-sdk.widgets` (Slider/ColorSwatch/Carousel).
   Not part of the library — a verification harness only. Mounts one of
   each widget, dispatches synthetic PointerEvent/click interactions on
   load, and writes pass/fail assertions into #results so a headless
   `--dump-dom` capture can be grepped for the outcome."
  (:require [kami-ui-sdk.widgets :as w]))

(defonce results (atom []))

(defn- check! [label pass?]
  (swap! results conj [label pass?]))

(defn- render-results! []
  (let [pre (.getElementById js/document "results")
        lines (map (fn [[label pass?]] (str (if pass? "PASS" "FAIL") " - " label)) @results)]
    (set! (.-textContent pre) (.join (into-array lines) "\n"))))

(defn- q [sel] (.querySelector js/document sel))

(defn ^:export run []
  (let [slider-mount (q "#slider-mount")
        swatch-mount (q "#swatch-mount")
        carousel-mount (q "#carousel-mount")
        !slider-val (atom nil)
        !swatch-val (atom nil)
        !carousel-val (atom nil)
        slider (w/slider! slider-mount {:label "Height" :min 0 :max 2 :step 0.05 :value 1.0
                                         :on-change #(reset! !slider-val %)})
        swatch (w/color-swatch! swatch-mount {:presets ["#fa5757" "#33bfff" "#66e673" "#ffbf33"]
                                               :value "#33bfff"
                                               :on-change #(reset! !swatch-val %)})
        carousel (w/carousel! carousel-mount
                               {:items [{:id :buzz :label "Buzz"
                                         :thumbnail (fn [_stage]
                                                      (let [svg (.createElementNS js/document "http://www.w3.org/2000/svg" "svg")]
                                                        (.setAttribute svg "width" "40") (.setAttribute svg "height" "40")
                                                        svg))}
                                        {:id :ponytail :label "Ponytail"}
                                        {:id :bald :label "Bald"}]
                                :value :buzz
                                :on-change #(reset! !carousel-val (:id %))})]
    ;; --- Slider: verify initial paint + drag-to-value + setValue API ---
    (check! "slider mounted" (some? (:el slider)))
    (check! "slider initial value" (= 1.0 ((:get-value slider))))
    (let [wrap (.-firstElementChild slider-mount)
          track (aget (.-children wrap) 1) ;; wrap -> [row, track]
          rect (.getBoundingClientRect track)
          mid-x (+ (.-left rect) (* 0.75 (.-width rect)))]
      (.dispatchEvent track (js/PointerEvent. "pointerdown" #js {:clientX mid-x :pointerId 1 :bubbles true}))
      (.dispatchEvent track (js/PointerEvent. "pointerup" #js {:clientX mid-x :pointerId 1 :bubbles true}))
      (check! "slider drag changed value via onChange" (some? @!slider-val))
      (check! "slider drag value near 75%" (< (js/Math.abs (- @!slider-val 1.5)) 0.3)))
    ((:set-value slider) 0.5 false)
    (check! "slider setValue API" (= 0.5 ((:get-value slider))))

    ;; --- ColorSwatch: verify initial + click-to-select ---
    (check! "swatch mounted" (some? (:el swatch)))
    (check! "swatch initial value" (= "#33bfff" ((:get-value swatch))))
    (let [green-btn (aget (.querySelectorAll swatch-mount "button") 2)]
      (.click green-btn)
      (check! "swatch click changed value via onChange" (= "#66e673" @!swatch-val))
      (check! "swatch getValue reflects click" (= "#66e673" ((:get-value swatch)))))

    ;; --- Carousel: verify initial + paging ---
    (check! "carousel mounted" (some? (:el carousel)))
    (check! "carousel initial value" (= :buzz ((:get-value carousel))))
    (let [next-btn (aget (.querySelectorAll carousel-mount "button") 1)]
      (.click next-btn)
      (check! "carousel next changed value via onChange" (= :ponytail @!carousel-val))
      (check! "carousel getValue reflects page" (= :ponytail ((:get-value carousel)))))

    (render-results!)))
