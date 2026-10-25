(ns kami.ongaku.notation.xml
  "Minimal, dependency-free XML reader/writer for the MusicXML subset
  kami.ongaku.notation.musicxml round-trips through: no DTD/entity
  expansion beyond the five predefined XML entities, no namespaces, no
  CDATA. Not a general-purpose/validating XML processor.

  Portable .cljc — uses only String-as-sequence operations (charAt/subs)
  that clj and cljs both support identically on strings, no platform XML
  library."
  (:require [kotoba.lang.text :as str]))

(defn escape-text [s]
  (-> s
      (str/replace "&" "&amp;")
      (str/replace "<" "&lt;")
      (str/replace ">" "&gt;")))

(defn escape-attr [s]
  (str/replace (escape-text s) "\"" "&quot;"))

(def ^:private entity->char {"amp" "&" "lt" "<" "gt" ">" "quot" "\"" "apos" "'"})

(defn unescape-text [s]
  (str/replace s #"&(amp|lt|gt|quot|apos);" (fn [[_ n]] (entity->char n))))

(defn- ws? [c] (contains? #{\space \tab \newline \return} c))

(defn- ch [s i] (.charAt s i))

(defn- skip-ws [s i]
  (loop [i i]
    (if (and (< i (count s)) (ws? (ch s i))) (recur (inc i)) i)))

(defn- find-char [s from c]
  (loop [i from]
    (cond (>= i (count s)) nil
          (= (ch s i) c) i
          :else (recur (inc i)))))

(defn- find-str [s from needle]
  (let [n (count needle)]
    (loop [i from]
      (cond (> (+ i n) (count s)) nil
            (= (subs s i (+ i n)) needle) i
            :else (recur (inc i))))))

(defn- name-char? [c]
  (not (or (ws? c) (contains? #{\< \> \/ \= \"} c))))

(defn- read-name [s i]
  (loop [j i]
    (if (and (< j (count s)) (name-char? (ch s j)))
      (recur (inc j))
      [(subs s i j) j])))

(defn- read-attrs [s i]
  (loop [i (skip-ws s i) attrs {}]
    (let [c (when (< i (count s)) (ch s i))]
      (if (or (nil? c) (= c \>) (= c \/))
        [attrs i]
        (let [[attr-name j] (read-name s i)
              j (skip-ws s j)
              j (if (and (< j (count s)) (= (ch s j) \=)) (inc j) j)
              j (skip-ws s j)
              quote-char (ch s j)
              val-start (inc j)
              val-end (find-char s val-start quote-char)
              value (unescape-text (subs s val-start val-end))]
          (recur (skip-ws s (inc val-end)) (assoc attrs attr-name value)))))))

(defn- skip-misc
  "Skip the XML declaration (<?...?>), comments (<!--...-->) and DOCTYPE
  (<!...>, no internal subset support), returning the next content index."
  [s i]
  (loop [i (skip-ws s i)]
    (cond
      (and (<= (+ i 2) (count s)) (= (subs s i (+ i 2)) "<?"))
      (recur (skip-ws s (+ 2 (find-str s i "?>"))))

      (and (<= (+ i 4) (count s)) (= (subs s i (+ i 4)) "<!--"))
      (recur (skip-ws s (+ 3 (find-str s i "-->"))))

      (and (<= (+ i 2) (count s)) (= (subs s i (+ i 2)) "<!"))
      (recur (skip-ws s (inc (find-char s i \>))))

      :else i)))

(declare parse-element)

(defn- parse-children [s i]
  (loop [i (skip-ws s i) children []]
    (let [i (skip-misc s i)]
      (cond
        (>= i (count s)) [children i]
        (and (<= (+ i 2) (count s)) (= (subs s i (+ i 2)) "</")) [children i]
        (= (ch s i) \<)
        (let [[el j] (parse-element s i)]
          (recur (skip-ws s j) (conj children el)))
        :else
        (let [text-end (or (find-char s i \<) (count s))
              text (unescape-text (str/trim (subs s i text-end)))]
          (recur (skip-ws s text-end) (if (seq text) (conj children text) children)))))))

(defn- parse-element [s i]
  (let [i (inc i) ;; skip '<'
        [tag j] (read-name s i)
        [attrs j] (read-attrs s j)]
    (if (= (ch s j) \/)
      [{:tag tag :attrs attrs :children []} (+ j 2)] ;; self-closing '/>'
      (let [j (inc j) ;; skip '>'
            [children j] (parse-children s j)
            close-end (inc (find-char s j \>))]
        [{:tag tag :attrs attrs :children children} close-end]))))

(defn parse
  "Parse an XML document string into {:tag ... :attrs {...} :children
  [...]}, where children are element maps or trimmed non-blank text
  strings. Skips the XML declaration, DOCTYPE and comments."
  [s]
  (first (parse-element s (skip-misc s 0))))

(defn find-child [el tag]
  (first (filter #(and (map? %) (= (:tag %) tag)) (:children el))))

(defn find-children [el tag]
  (filterv #(and (map? %) (= (:tag %) tag)) (:children el)))

(defn text-content [el]
  (apply str (filter string? (:children el))))
