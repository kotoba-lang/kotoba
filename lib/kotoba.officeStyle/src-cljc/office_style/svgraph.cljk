(ns office-style.svgraph)

(def default-width 9144000)
(def default-height 5143500)

(defn- finite-number? [x]
  (and (number? x)
       #?(:clj (Double/isFinite (double x))
          :cljs (js/isFinite x))))

(defn- positive-number-or [x fallback]
  (if (and (finite-number? x) (pos? x)) x fallback))

(defn presentation [ir]
  {:svgraph/version "svgraph-presentation/1"
   :svgraph/source (:office-style/source ir)
   :svgraph/slide-size (let [{:office-style/keys [cx cy]} (:office-style/slide-size ir)]
                         [(positive-number-or cx default-width)
                          (positive-number-or cy default-height)])
   :svgraph/theme {:svgraph/colors (or (:office-style/colors ir) {})
                   :svgraph/fonts (or (:office-style/fonts ir) {})}
   :svgraph/masters (mapv (fn [part] {:svgraph/id part :svgraph/part part})
                          (:office-style/masters ir))
   :svgraph/layouts (mapv (fn [part] {:svgraph/id part :svgraph/part part})
                          (:office-style/layouts ir))
   :svgraph/slides (mapv (fn [part] {:svgraph/id part :svgraph/part part :svgraph/shapes []})
                         (:office-style/slides ir))})
