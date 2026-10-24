;; `.cljc` is a claim about two platforms. Everything in this namespace is
;; portable by construction — no keys, no I/O — and `write-document` still came
;; out as zeros on ClojureScript because it used `int` on the characters of a
;; String, which means something different there.
(ns run-tests (:require [pdf.core :as pdf]))

(def failures (atom 0))
(defn check [label expected actual]
  (if (= expected actual)
    (println "  ok  " label)
    (do (swap! failures inc)
        (println "  FAIL" label "expected" (pr-str expected) "got" (pr-str actual)))))

(def document
  (pdf/write-document
   [{:width 595 :height 842
     :content (str (pdf/text-command {:x 72 :y 760 :text "Hello"})
                   (pdf/line-command {:from [72 700] :to [523 700]}))}]))

(def text (apply str (map char document)))

(println "pdf on nbb:")
(check "starts with the PDF header" "%PDF-1.4" (subs text 0 8))
(check "every byte is in range" true (every? #(<= 0 % 255) document))
(check "has an xref" true (boolean (re-find #"(?m)^xref$" text)))
(check "has a trailer with a Root" true (boolean (re-find #"/Root 1 0 R" text)))
(check "has startxref and EOF" true (boolean (re-find #"startxref\n\d+\n%%EOF" text)))
(check "the page is there" true (boolean (re-find #"/Type /Page\b" text)))

;; The parser reading back what the writer produced — on the platform where the
;; writer was broken.
(let [{:keys [objects]} (pdf/parse text)]
  (check "parses back" true (map? objects))
  (check "and finds the catalog" true
         (boolean (some #(= :Catalog (:Type %)) (vals objects)))))

(println "\nnbb:" @failures "failures")
(when (pos? @failures) (js/process.exit 1))
