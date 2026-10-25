(ns office-style.preview
  "Preview SVG rendering for CLJC StyleIR."
  (:require [kotoba.lang.text :as str]))

(defn- esc [x]
  (-> (str (or x ""))
      (str/replace "&" "&amp;")
      (str/replace "<" "&lt;")
      (str/replace ">" "&gt;")
      (str/replace "\"" "&quot;")))

(defn- hex-color [x fallback]
  (let [s (-> (or x fallback) str (str/replace #"^#" "") str/upper)]
    (if (re-matches #"[0-9A-F]{6}" s) s fallback)))

(defn- color [ir role fallback]
  (str "#" (hex-color (get-in ir [:office-style/colors role]) fallback)))

(defn preview-svg [ir]
  (let [w 960
        h 540
        accent (color ir :office-style.color/accent1 "496B9A")
        dk (color ir :office-style.color/dk1 "17202A")
        lt (color ir :office-style.color/lt1 "FFFFFF")
        font (or (get-in ir [:office-style/fonts :office-style.font/majorFont])
                 (get-in ir [:office-style/fonts :office-style.font/minorFont])
                 "Aptos")]
    (str "<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"" w "\" height=\"" h "\" viewBox=\"0 0 " w " " h "\">"
         "<rect width=\"" w "\" height=\"" h "\" fill=\"" lt "\"/>"
         "<rect x=\"0\" y=\"0\" width=\"14\" height=\"" h "\" fill=\"" accent "\"/>"
         "<text x=\"52\" y=\"86\" font-family=\"" (esc font) ",Arial,sans-serif\" font-size=\"42\" font-weight=\"700\" fill=\"" dk "\">StyleIR preview</text>"
         "<text x=\"52\" y=\"134\" font-family=\"" (esc font) ",Arial,sans-serif\" font-size=\"20\" fill=\"#526170\">"
         (esc (str "slides " (count (:office-style/slides ir))
                   " / masters " (count (:office-style/masters ir))
                   " / layouts " (count (:office-style/layouts ir))))
         "</text>"
         "<rect x=\"52\" y=\"186\" width=\"360\" height=\"190\" rx=\"8\" fill=\"#f7f8fb\" stroke=\"#d8dee8\"/>"
         "<text x=\"78\" y=\"235\" font-family=\"" (esc font) ",Arial,sans-serif\" font-size=\"22\" fill=\"" dk "\">"
         (esc font) "</text>"
         "<circle cx=\"92\" cy=\"304\" r=\"28\" fill=\"" accent "\"/>"
         "<text x=\"136\" y=\"312\" font-family=\"ui-monospace,Menlo,monospace\" font-size=\"18\" fill=\"" dk "\">"
         (esc accent) "</text>"
         "</svg>")))
