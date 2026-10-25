(ns kotoba-code.composer-input
  (:require ["ink" :refer [Text useInput]]
            ["react" :as react]
            ["string-width" :as string-width-module]))

(def string-width (or (.-default string-width-module) string-width-module))

(defn graphemes [s]
  (if (some? (.-Segmenter js/Intl))
    (let [segmenter (js/Intl.Segmenter. "ja" #js {:granularity "grapheme"})]
      (mapv #(.-segment %) (js/Array.from (.segment segmenter (or s "")))))
    (vec (js/Array.from (or s "")))))

(defn width [s]
  (string-width (or s "")))

(defn viewport
  "Return graphemes around cursor that fit max terminal columns."
  [parts cursor max-columns]
  (let [max-columns (max 4 max-columns)
        cursor-glyph (if (< cursor (count parts)) (nth parts cursor) " ")
        cursor-width (max 1 (width cursor-glyph))
        left-budget (max 0 (- max-columns cursor-width))
        start (loop [i cursor used 0]
                (if (zero? i)
                  0
                  (let [w (width (nth parts (dec i)))]
                    (if (> (+ used w) left-budget)
                      i
                      (recur (dec i) (+ used w))))))
        before (subvec parts start cursor)
        used (+ (width (apply str before)) cursor-width)
        end (loop [i (min (inc cursor) (count parts)) used used]
              (if (>= i (count parts))
                i
                (let [w (width (nth parts i))]
                  (if (> (+ used w) max-columns)
                    i
                    (recur (inc i) (+ used w))))))
        after-start (min (inc cursor) (count parts))]
    {:before (apply str before)
     :cursor cursor-glyph
     :after (apply str (subvec parts after-start end))
     :left-clipped? (pos? start)
     :right-clipped? (< end (count parts))}))

(defn composer-input [props]
  (let [value (or (.-value props) "")
        on-change (.-onChange props)
        on-submit (.-onSubmit props)
        placeholder (or (.-placeholder props) "")
        max-columns (or (.-maxColumns props) 60)
        [cursor set-cursor] (react/useState (count (graphemes value)))
        parts (graphemes value)]
    (react/useEffect
     (fn []
       (when (> cursor (count parts))
         (set-cursor (count parts)))
       js/undefined)
     #js [value cursor])
    (useInput
     (fn [input key]
       (cond
         (.-return key) (on-submit value)
         (.-leftArrow key) (set-cursor #(max 0 (dec %)))
         (.-rightArrow key) (set-cursor #(min (count parts) (inc %)))
         (.-backspace key)
         (when (pos? cursor)
           (on-change (apply str (concat (subvec parts 0 (dec cursor))
                                         (subvec parts cursor))))
           (set-cursor (dec cursor)))
         (.-delete key)
         (when (< cursor (count parts))
           (on-change (apply str (concat (subvec parts 0 cursor)
                                         (subvec parts (inc cursor))))))
         (or (.-upArrow key) (.-downArrow key) (.-tab key)
             (and (.-ctrl key) (= input "c")))
         nil
         (seq input)
         (let [inserted (graphemes input)]
           (on-change (apply str (concat (subvec parts 0 cursor)
                                         inserted
                                         (subvec parts cursor))))
           (set-cursor (+ cursor (count inserted))))
         :else nil)))
    (if (empty? parts)
      (react/createElement
       Text #js {:dimColor true}
       (react/createElement Text #js {:inverse true}
                            (if (seq placeholder) (subs placeholder 0 1) " "))
       (if (> (count placeholder) 1) (subs placeholder 1) ""))
      (let [{:keys [before cursor after left-clipped? right-clipped?]}
            (viewport parts cursor max-columns)]
        (react/createElement
         Text #js {:wrap "truncate"}
         (when left-clipped? "…")
         before
         (react/createElement Text #js {:inverse true} cursor)
         after
         (when right-clipped? "…"))))))
