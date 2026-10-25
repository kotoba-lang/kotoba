(ns iso-10303.part21
  "Generic ISO 10303-21 physical-file serialization shared by STEP and IFC."
  (:require [kotoba.lang.text :as string]))

(defn- token [value]
  (string/upper (string/replace (name value) "-" "_")))

(defn- step-real [value]
  (let [s (str (double value))]
    (if (string/ends-with? s ".0") (subs s 0 (dec (count s))) s)))

(declare value)
(defn value [v]
  (cond
    (string? v) (str "'" (string/replace v "'" "''") "'")
    (and (vector? v) (= :typed (first v)))
    (str (token (second v)) "(" (value (nth v 2)) ")")
    (and (vector? v) (= :ref (first v))) (str "#" (second v))
    (and (vector? v) (= :list (first v)))
    (str "(" (string/join ", " (map value (rest v))) ")")
    (= :$ v) "$"
    (= :* v) "*"
    (true? v) ".T."
    (false? v) ".F."
    (keyword? v) (str "." (token v) ".")
    (integer? v) (str v)
    (number? v) (step-real v)
    :else (str v)))

(defn entity [[id entity-type & args]]
  (str "#" id " = " (token entity-type) "("
       (string/join ", " (map value args)) ");"))

(defn file
  [{:keys [description name schema author org] :or {schema "AUTOMOTIVE_DESIGN"}}
   & entities]
  (str "ISO-10303-21;\nHEADER;\n"
       "FILE_DESCRIPTION(('" (or description "") "'), '2;1');\n"
       "FILE_NAME('" (or name "") "', '', ('" (or author "") "'), ('"
       (or org "") "'), '', '', '');\n"
       "FILE_SCHEMA(('" schema "'));\nENDSEC;\nDATA;\n"
       (string/join "\n" (map entity entities))
       "\nENDSEC;\nEND-ISO-10303-21;\n"))

(defn split-top-level
  "Split a Part 21 parameter list without splitting nested aggregates or strings."
  [text]
  (loop [remaining (seq text) depth 0 quoted? false current [] result []]
    (if-let [c (first remaining)]
      (let [next-c (second remaining)]
        (cond
          (and quoted? (= c \') (= next-c \'))
          (recur (nnext remaining) depth quoted? (conj current c next-c) result)

          (= c \')
          (recur (next remaining) depth (not quoted?) (conj current c) result)

          quoted?
          (recur (next remaining) depth quoted? (conj current c) result)

          (= c \()
          (recur (next remaining) (inc depth) quoted? (conj current c) result)

          (= c \))
          (recur (next remaining) (dec depth) quoted? (conj current c) result)

          (and (= c \,) (zero? depth))
          (recur (next remaining) depth quoted? [] (conj result (string/join current)))

          :else
          (recur (next remaining) depth quoted? (conj current c) result)))
      (cond-> result (seq current) (conj (string/join current))))))

(declare parse-value)

(defn- parse-hex [text]
  #?(:clj (Integer/parseInt text 16)
     :cljs (js/parseInt text 16)))

(defn- code-unit-string [hex]
  (apply str
         (map (fn [digits]
                #?(:clj (char (parse-hex (apply str digits)))
                   :cljs (js/String.fromCharCode (parse-hex (apply str digits)))))
              (partition 4 hex))))

(defn- code-point-string [hex]
  (apply str
         (map (fn [digits]
                (let [point (parse-hex (apply str digits))]
                  #?(:clj (String. (Character/toChars point))
                     :cljs (js/String.fromCodePoint point))))
              (partition 8 hex))))

(defn decode-string
  "Decode ISO 10303-21 extended-string directives in a quoted payload."
  [text]
  (-> text
      (string/replace #"\\X4\\([0-9A-Fa-f]+)\\X0\\"
                      (fn [[_ hex]] (code-point-string hex)))
      (string/replace #"\\X2\\([0-9A-Fa-f]+)\\X0\\"
                      (fn [[_ hex]] (code-unit-string hex)))
      (string/replace "''" "'")))

(defn parse-value [raw]
  (let [value (string/trim raw)]
    (cond
      (= "$" value) :$
      (= "*" value) :*
      (= ".T." value) true
      (= ".F." value) false
      (re-matches #"#\d+" value) [:ref (#?(:clj Long/parseLong :cljs js/parseInt) (subs value 1))]
      (and (string/starts-with? value "'") (string/ends-with? value "'"))
      (decode-string (subs value 1 (dec (count value))))
      (and (string/starts-with? value "(") (string/ends-with? value ")"))
      (into [:list] (map parse-value (split-top-level (subs value 1 (dec (count value))))))
      (re-matches #"\.[A-Z0-9_]+\." value)
      (-> value (subs 1 (dec (count value))) string/lower
          (string/replace "_" "-") keyword)
      (re-matches #"[A-Z][A-Z0-9_]*\(.*\)" value)
      (let [[_ type body] (re-matches #"(?s)([A-Z][A-Z0-9_]*)\((.*)\)" value)]
        [:typed (-> type string/lower (string/replace "_" "-") keyword)
         (parse-value body)])
      (re-matches #"[+-]?\d+" value)
      (#?(:clj Long/parseLong :cljs js/parseInt) value)
      (re-matches #"[+-]?(?:\d+\.?\d*|\.\d+)(?:[Ee][+-]?\d+)?" value)
      (#?(:clj Double/parseDouble :cljs js/parseFloat) value)
      :else value)))

(defn parse-entity [statement]
  (when-let [[_ id type body]
             (re-matches #"(?s)\s*#(\d+)\s*=\s*([A-Z0-9_]+)\s*\((.*)\)\s*;?\s*"
                         statement)]
    {:id (#?(:clj Long/parseLong :cljs js/parseInt) id)
     :type (-> type string/lower (string/replace "_" "-") keyword)
     :args (mapv parse-value (split-top-level body))}))

(defn- data-text [text]
  (when-let [[_ body] (re-find #"(?s)\bDATA\s*;(.*)ENDSEC\s*;\s*END-ISO-10303-21" text)]
    body))

(defn- strip-exchange-comments
  "Remove ISO 10303-21 block comments without treating comment delimiters in
  quoted strings as syntax. Whitespace is retained at each removed comment so
  adjacent lexical tokens cannot be joined accidentally."
  [text]
  (loop [remaining (seq text) quoted? false comment? false result []]
    (if-let [c (first remaining)]
      (let [next-c (second remaining)]
        (cond
          (and comment? (= c \*) (= next-c \/))
          (recur (nnext remaining) quoted? false (conj result \space))

          comment?
          (recur (next remaining) quoted? true result)

          (and quoted? (= c \') (= next-c \'))
          (recur (nnext remaining) quoted? false (conj result c next-c))

          (= c \')
          (recur (next remaining) (not quoted?) false (conj result c))

          (and (not quoted?) (= c \/) (= next-c \*))
          (recur (nnext remaining) quoted? true (conj result \space))

          :else
          (recur (next remaining) quoted? false (conj result c))))
      (string/join result))))

(defn- statements [text]
  (loop [remaining (seq text) depth 0 quoted? false current [] result []]
    (if-let [c (first remaining)]
      (let [next-c (second remaining)]
        (cond
          (and quoted? (= c \') (= next-c \'))
          (recur (nnext remaining) depth quoted? (conj current c next-c) result)
          (= c \') (recur (next remaining) depth (not quoted?) (conj current c) result)
          quoted? (recur (next remaining) depth quoted? (conj current c) result)
          (= c \() (recur (next remaining) (inc depth) quoted? (conj current c) result)
          (= c \)) (recur (next remaining) (dec depth) quoted? (conj current c) result)
          (and (= c \;) (zero? depth))
          (recur (next remaining) depth quoted? [] (conj result (str (string/join current) ";")))
          :else (recur (next remaining) depth quoted? (conj current c) result)))
      result)))

(defn- header-value [text entity-name]
  (when-let [statement
             (some #(when (re-find (re-pattern (str "(?i)\\b" entity-name "\\s*\\(")) %)
                      %)
                   (statements (strip-exchange-comments text)))]
    (let [start (string/index-of statement "(")
          end (string/last-index-of statement ")")]
      (parse-value (subs statement start (inc end))))))

(defn parse-file [text]
  (let [schema (second (re-find #"FILE_SCHEMA\s*\(\s*\(\s*'([^']+)'" text))
        description (header-value text "FILE_DESCRIPTION")
        file-name (header-value text "FILE_NAME")
        entities (if-let [body (data-text text)]
                   (vec (keep parse-entity (statements (strip-exchange-comments body)))) [])]
    {:part21/schema schema
     :part21/file-description (vec (rest (second description)))
     :part21/implementation-level (nth description 2 nil)
     :part21/file-name {:name (nth file-name 1 nil)
                        :timestamp (nth file-name 2 nil)
                        :authors (vec (rest (nth file-name 3 [:list])))
                        :organizations (vec (rest (nth file-name 4 [:list])))
                        :preprocessor-version (nth file-name 5 nil)
                        :originating-system (nth file-name 6 nil)
                        :authorization (nth file-name 7 nil)}
     :part21/entities entities
     :part21/entity-by-id (into {} (map (juxt :id identity)) entities)}))
