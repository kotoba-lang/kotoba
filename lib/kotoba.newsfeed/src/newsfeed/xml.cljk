(ns newsfeed.xml
  "A minimal XML reader — exactly enough for RSS 2.0, Atom 1.0 and RDF/RSS 1.0.

   Pure `.cljc`, no dependency. Syndication feeds are a small, well-behaved
   corner of XML: elements, attributes, text, CDATA, entities, comments, an
   optional declaration and DOCTYPE. Everything else (namespaces as scoping,
   processing instructions, DTD-defined entities) a feed either does not use or
   uses only as a tag prefix, which is kept verbatim in `:tag`.

   Namespace prefixes are NOT stripped at parse time. `<content:encoded>` and a
   hypothetical `<content>` are different elements and collapsing them here
   would lose that. `local-name` and the accessors below match on the local
   part, so callers can ask for \"encoded\" without knowing the prefix.

   Scanning is by `str/index-of` rather than per-character, because per-char
   `subs` on a 500 KB feed allocates once per character in both runtimes. The
   char-wise helpers are used only inside tag headers, which are short."
  (:require [kotoba.lang.text :as str]))

;; ── character helpers (short spans only) ─────────────────────────────────────

(defn- ch
  "The 1-char string at i, or nil past the end. Portable: `nth` on a string
   yields a char in Clojure and a 1-char string in ClojureScript."
  [^String s i]
  (when (< i (count s)) (subs s i (inc i))))

(def ^:private ws #{" " "\t" "\r" "\n"})

(defn- skip-ws [s i]
  (loop [i i] (if (ws (ch s i)) (recur (inc i)) i)))

(def ^:private name-end (into #{nil "/" ">" "=" "?"} ws))

(defn- read-name
  "→ [name next-index] reading until whitespace or one of / > = ?"
  [s i]
  (loop [j i]
    (if (name-end (ch s j))
      [(subs s i j) j]
      (recur (inc j)))))

;; ── entities ─────────────────────────────────────────────────────────────────

(def ^:private named-entities
  {"amp" "&" "lt" "<" "gt" ">" "quot" "\"" "apos" "'" "nbsp" " "
   "mdash" "—" "ndash" "–" "hellip" "…" "laquo" "«" "raquo" "»"
   "lsquo" "‘" "rsquo" "’" "ldquo" "“" "rdquo" "”"
   "bull" "•" "middot" "·" "deg" "°" "times" "×" "trade" "™"
   "copy" "©" "reg" "®" "eacute" "é" "egrave" "è" "uuml" "ü" "ouml" "ö"})

(defn- code-point->str [n]
  (when (and (int? n) (pos? n) (<= n 0x10FFFF))
    #?(:clj (String. (Character/toChars (int n)))
       :cljs (js/String.fromCodePoint n))))

(defn- parse-int-radix [s radix]
  #?(:clj  (try (Long/parseLong s radix) (catch Exception _ nil))
     :cljs (let [n (js/parseInt s radix)] (when-not (js/isNaN n) n))))

(defn decode-entities
  "Expand the entity references a feed can actually carry. An unrecognised
   reference is left verbatim — dropping it would silently corrupt a title,
   and a stray `&` is the more honest failure."
  [s]
  (if (or (nil? s) (not (str/includes? s "&")))
    s
    (loop [out [] i 0]
      (let [amp (str/index-of s "&" i)]
        (if (nil? amp)
          (str/join (conj out (subs s i)))
          (let [semi (str/index-of s ";" amp)
                body (when (and semi (< (- semi amp) 12)) (subs s (inc amp) semi))
                rep  (cond
                       (nil? body) nil
                       (str/starts-with? body "#x") (code-point->str (parse-int-radix (subs body 2) 16))
                       (str/starts-with? body "#X") (code-point->str (parse-int-radix (subs body 2) 16))
                       (str/starts-with? body "#")  (code-point->str (parse-int-radix (subs body 1) 10))
                       :else (named-entities body))]
            (if rep
              (recur (conj out (subs s i amp) rep) (inc semi))
              (recur (conj out (subs s i (inc amp))) (inc amp)))))))))

;; ── attributes ───────────────────────────────────────────────────────────────

(defn- read-attrs
  "→ [attrs next-index self-closing?] starting just after the tag name.
   Quoted values are scanned to their matching quote, so a `>` inside a value
   does not end the tag early."
  [s i]
  (loop [i (skip-ws s i) attrs {}]
    (let [c (ch s i)]
      (cond
        (nil? c) [attrs i false]
        (= c ">") [attrs (inc i) false]
        (and (= c "/") (= (ch s (inc i)) ">")) [attrs (+ i 2) true]
        (= c "?") (recur (inc i) attrs)
        (= c "/") (recur (inc i) attrs)
        :else
        (let [[k j] (read-name s i)
              j (skip-ws s j)]
          (if (= (ch s j) "=")
            (let [j (skip-ws s (inc j))
                  q (ch s j)]
              (if (or (= q "\"") (= q "'"))
                (let [end (or (str/index-of s q (inc j)) (count s))]
                  (recur (skip-ws s (inc end))
                         (assoc attrs (str/lower k) (decode-entities (subs s (inc j) end)))))
                ;; unquoted value
                (let [[v j2] (read-name s j)]
                  (recur (skip-ws s j2) (assoc attrs (str/lower k) (decode-entities v))))))
            ;; valueless attribute
            (recur j (cond-> attrs (seq k) (assoc (str/lower k) "")))))))))

;; ── nodes ────────────────────────────────────────────────────────────────────

(declare parse-nodes)

(defn- parse-element [s i]
  (let [[tag j] (read-name s (inc i))
        [attrs j self?] (read-attrs s j)
        el {:tag (str/lower tag) :attrs attrs}]
    (if self?
      [(assoc el :children []) j]
      (let [[children j] (parse-nodes s j)
            ;; consume the matching `</tag>` if it is there
            j (if (and (= (ch s j) "<") (= (ch s (inc j)) "/"))
                (let [close (str/index-of s ">" j)] (if close (inc close) (count s)))
                j)]
        [(assoc el :children children) j]))))

(defn- parse-nodes
  "→ [children next-index]. Stops at a closing tag or end of input."
  [s i]
  (loop [i i children []]
    (let [lt (str/index-of s "<" i)]
      (cond
        (nil? lt)
        (let [txt (decode-entities (subs s i))]
          [(cond-> children (seq (str/trim txt)) (conj txt)) (count s)])

        :else
        (let [txt (when (> lt i) (decode-entities (subs s i lt)))
              children (cond-> children (and txt (seq (str/trim txt))) (conj txt))
              c1 (ch s (inc lt))]
          (cond
            ;; closing tag — belongs to the caller
            (= c1 "/") [children lt]

            (str/starts-with? (subs s lt (min (count s) (+ lt 9))) "<![CDATA[")
            (let [end (or (str/index-of s "]]>" lt) (count s))
                  txt (subs s (+ lt 9) end)]
              (recur (min (count s) (+ end 3))
                     (cond-> children (seq txt) (conj txt))))

            (str/starts-with? (subs s lt (min (count s) (+ lt 4))) "<!--")
            (recur (let [end (str/index-of s "-->" lt)] (if end (+ end 3) (count s))) children)

            (= c1 "!")                              ; DOCTYPE and friends
            (recur (let [end (str/index-of s ">" lt)] (if end (inc end) (count s))) children)

            (= c1 "?")                              ; <?xml ... ?>
            (recur (let [end (str/index-of s "?>" lt)] (if end (+ end 2) (count s))) children)

            :else
            (let [[el j] (parse-element s lt)]
              (recur j (conj children el)))))))))

(defn parse
  "Parse an XML document → its root element map {:tag :attrs :children}, or nil.
   Children are element maps and strings (text). A leading BOM is tolerated —
   several real feeds serve one."
  [s]
  (when (and (string? s) (seq s))
    (let [s (if (str/starts-with? s "﻿") (subs s 1) s)
          [nodes _] (parse-nodes s 0)]
      (first (filter map? nodes)))))

;; ── accessors ────────────────────────────────────────────────────────────────

(defn local-name
  "\"content:encoded\" → \"encoded\". The local part is what callers ask for."
  [tag]
  (if-let [i (str/index-of (str tag) ":")] (subs (str tag) (inc i)) (str tag)))

(defn elements
  "Child elements of el, optionally those whose local name is `name`."
  ([el] (filter map? (:children el)))
  ([el name] (filter #(= (local-name (:tag %)) name) (elements el))))

(defn element [el name] (first (elements el name)))

(defn text
  "All descendant text of el, concatenated and trimmed. Descendant rather than
   direct-child text because feeds put escaped or inline markup inside
   <description> and <summary>, and the words are what a caller wants."
  [el]
  (cond
    (string? el) el
    (map? el) (str/trim (str/join (map text (:children el))))
    :else ""))

(defn child-text
  "Trimmed text of the first child element with this local name, or nil."
  [el name]
  (some-> (element el name) text not-empty))

(defn find-all
  "Every descendant element with this local name, depth-first."
  [el name]
  (when (map? el)
    (concat (when (= (local-name (:tag el)) name) [el])
            (mapcat #(find-all % name) (elements el)))))
