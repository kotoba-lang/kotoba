(ns run-nbb-contract-tests
  (:require [css.core :as css]
            [css.utility :as utility]))

(defn check! [label expected actual]
  (when-not (= expected actual)
    (throw (js/Error. (str label ": expected " (pr-str expected)
                           ", got " (pr-str actual))))))

(check! "CLJS declarations" "display: flex; opacity: 0.5;"
        (css/style {:display :flex :opacity 0.5}))
(check! "CLJS responsive utility" {:flex-direction :row}
        (utility/utility-rule "md:flex-row"))
(check! "CLJS strict utility detection" ["unknown-utility"]
        (utility/unsupported ["flex" "unknown-utility"]))
(let [blocked? (try (css/style {:color "red;} .evil{x:y"}) false
                    (catch :default _ true))]
  (check! "CLJS rule-breakout guard" true blocked?))
(println "✓ kotoba-lang/css CLJS contract")
