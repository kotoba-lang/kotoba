(ns run-nbb-contract-tests
  (:require [html.core :as html]
            [kotoba.html :as kotoba]))

(defn check! [label expected actual]
  (when-not (= expected actual)
    (throw (js/Error. (str label ": expected " (pr-str expected)
                           ", got " (pr-str actual))))))

(check! "CLJS Hiccup and escaping"
        "<main id=\"app\">\n  <p>a &lt; b</p>\n</main>"
        (kotoba/html [:main#app [:p "a < b"]]))
(check! "CLJS fragment"
        "<i>a</i><i>b</i>"
        (html/->html [:<> [:i "a"] [:i "b"]]))
(check! "CLJS trusted raw"
        "<b>trusted</b>"
        (html/->html (kotoba/raw "<b>trusted</b>")))
(let [blocked? (try (html/->html [:script "x</SCRIPT><img src=x>"]) false
                    (catch :default _ true))]
  (check! "CLJS RAWTEXT breakout guard" true blocked?))
(println "✓ kotoba-lang/html CLJS contract")
