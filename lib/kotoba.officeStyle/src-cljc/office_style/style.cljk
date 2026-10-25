(ns office-style.style
  "Deterministic CLJC StyleIR extraction from PowerPoint OOXML."
  (:require [kotoba.lang.text :as str]
            [office-style.opc :as opc]))

(defn- attr [s k]
  (nth (re-find (re-pattern (str "\\b" (name k) "=(['\"])(.*?)\\1")) s) 2 nil))

(defn- parse-long-or-zero [x]
  (try
    (or (parse-long (or x "0")) 0)
    (catch #?(:clj Exception :cljs :default) _
      0)))

(defn- parse-int-radix [s radix]
  #?(:clj (Integer/parseInt s radix)
     :cljs (js/parseInt s radix)))

(defn- codepoint-string [n]
  #?(:clj (String. (Character/toChars n))
     :cljs (.fromCodePoint js/String n)))

(defn- decode-numeric-entity [[raw hex dec]]
  (try
    (let [n (if hex
              (parse-int-radix hex 16)
              (parse-int-radix dec 10))]
      (codepoint-string n))
    (catch #?(:clj Exception :cljs :default) _
      raw)))

(defn- xml-attr [x]
  (-> (str (or x ""))
      (str/replace #"&#x([0-9A-Fa-f]+);|&#([0-9]+);" decode-numeric-entity)
      (str/replace "&lt;" "<")
      (str/replace "&gt;" ">")
      (str/replace "&quot;" "\"")
      (str/replace "&apos;" "'")
      (str/replace "&amp;" "&")))

(defn- part-sort-key [path]
  (if-let [[_ prefix n] (re-matches #"^(ppt/(?:slides/slide|slideLayouts/slideLayout|slideMasters/slideMaster))(\d+)\.xml$" path)]
    [prefix (count n) n]
    [path 0]))

(defn- srgb-colors [xml]
  (->> (concat
        (re-seq #"<a:([A-Za-z0-9]+)>\s*<a:srgbClr\b[^>]*\bval=(['\"])([0-9A-Fa-f]{6})\2" xml)
        (re-seq #"<a:([A-Za-z0-9]+)>\s*<a:sysClr\b[^>]*\blastClr=(['\"])([0-9A-Fa-f]{6})\2" xml))
       (map (fn [[_ role _ color]]
              [(keyword "office-style.color" role) (str/upper color)]))
       (into {})))

(defn- typefaces [xml]
  (->> (re-seq #"<a:(majorFont|minorFont)>[\s\S]*?<a:latin\b[^>]*\btypeface=(['\"])(.*?)\2" xml)
       (map (fn [[_ role _ face]]
              [(keyword "office-style.font" role) (xml-attr face)]))
       (into {})))

(defn- slide-size [presentation-xml]
  (when-let [tag (second (re-find #"<p:sldSz\b([^>]*)>" (or presentation-xml "")))]
    {:office-style/cx (parse-long-or-zero (attr tag :cx))
     :office-style/cy (parse-long-or-zero (attr tag :cy))
     :office-style/type (keyword (or (attr tag :type) "custom"))}))

(defn style-ir [pkg]
  (let [entries (if (map? (:office-style/entries pkg))
                  (:office-style/entries pkg)
                  {})
        theme-xml (or (get entries "ppt/theme/theme1.xml") "")
        presentation-xml (get entries "ppt/presentation.xml")
        slides (->> entries
                    keys
                    (filter #(re-matches #"ppt/slides/slide\d+\.xml" %))
                    (sort-by part-sort-key)
                    vec)
        layouts (->> entries
                     keys
                     (filter #(re-matches #"ppt/slideLayouts/slideLayout\d+\.xml" %))
                     (sort-by part-sort-key)
                     vec)
        masters (->> entries
                     keys
                     (filter #(re-matches #"ppt/slideMasters/slideMaster\d+\.xml" %))
                     (sort-by part-sort-key)
                     vec)]
    {:office-style/kind :style-ir
     :office-style/version "style-ir/1"
     :office-style/source {:office-style/app :ppt}
     :office-style/colors (srgb-colors theme-xml)
     :office-style/fonts (typefaces theme-xml)
     :office-style/slide-size (slide-size presentation-xml)
     :office-style/slides slides
     :office-style/layouts layouts
     :office-style/masters masters}))

(defn extract-bytes [bytes]
  (-> bytes opc/open-pptx style-ir))
