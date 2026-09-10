(ns kotoba.adl.reader
  "Lexical core shared by EDN and Kotoba ADL.

   Reads text into a concrete syntax tree (CST) whose nodes include comments
   and whitespace. A conversion built on this is a faithful transform of the
   text, not a read-then-print -- read-then-print silently drops every comment,
   and 423 of the 3,798 .edn files in this workspace carry them.

   Node shapes:
     {:t :ws      :s \"  \"}
     {:t :comment :s \";; ...\"}
     {:t :atom    :s \"...\" :v <value> :kind :nil|:bool|:int|:float|:string|:keyword|:symbol|:char}
     {:t :coll    :kind :list|:vector|:map|:set :children [...]}
     {:t :tagged  :tag \"uuid\" :children [...]}  ; trivia + exactly one form
     {:t :discard :children [...]}                ; #_ then trivia + one form
     {:t :meta    :children [...]}                ; ^ then two forms

   Every shape it cannot classify is REFUSED with ex-info carrying ::at, rather
   than guessed at. A reader that guesses returns the same value for text it
   understood and text it did not."
  (:require [clojure.string :as str]))

(defn- parse-int-radix [^String t radix]
  #?(:clj  (Long/parseLong t radix)
     :cljs (js/parseInt t radix)))

(defn- parse-float* [^String t]
  #?(:clj  (Double/parseDouble t)
     :cljs (js/parseFloat t)))

(def ^:dynamic *surface*
  "Which surface is being read.

   :data   -- a document. EDN's rules apply, and everything outside them is
              refused, because a data file that needs a reader extension is
              telling you something.
   :source -- a program. The full Clojure reader surface is legal here, so the
              reader stays faithful and `edn->adl` does the refusing instead.
              Refusing source constructs at read time would mean the source
              path could not read the very files it exists to move."
  :data)

(def ^:private ws-chars #{\space \tab \newline \return \, (char 12) (char 11)})

(defn- ws? [c] (contains? ws-chars c))

;; `'` is deliberately NOT here. It dispatches a quote only in FIRST position,
;; which read-form checks before it ever scans a token; inside a token it is an
;; ordinary symbol character, and Clojure source is full of `state'`. Treating
;; it as a terminator ended the symbol early and made the rest of the form read
;; as unbalanced -- 52 files in this tree.
(def ^:private delim-chars #{\( \) \[ \] \{ \} \" \; \^ \` \~ \@})

(defn- terminator? [c] (or (nil? c) (ws? c) (contains? delim-chars c)))

(defn- err
  ([i msg] (err i msg {}))
  ([i msg data]
   (throw (ex-info msg (merge {:kotoba.adl.reader/at i} data)))))

(defn- at [^String s i] (when (< i (count s)) (nth s i)))

;; ---------------------------------------------------------------- scalars

(def ^:private named-chars
  {"newline" \newline "space" \space "tab" \tab "return" \return
   "formfeed" (char 12) "backspace" (char 8)})

(defn- read-string-literal
  "Reads a \"...\" literal starting at i (which points at the opening quote).
   Returns [node next-index]."
  [^String s i]
  (loop [j (inc i) buf []]
    (let [c (at s j)]
      (cond
        (nil? c) (err i "unterminated string literal")
        (= c \") [{:t :atom :kind :string :v (apply str buf) :s (subs s i (inc j))} (inc j)]
        (= c \\)
        (let [e (at s (inc j))]
          (case e
            \" (recur (+ j 2) (conj buf \"))
            \\ (recur (+ j 2) (conj buf \\))
            \/ (recur (+ j 2) (conj buf \/))
            \n (recur (+ j 2) (conj buf \newline))
            \t (recur (+ j 2) (conj buf \tab))
            \r (recur (+ j 2) (conj buf \return))
            \b (recur (+ j 2) (conj buf (char 8)))
            \f (recur (+ j 2) (conj buf (char 12)))
            \u (let [hex (subs s (+ j 2) (min (count s) (+ j 6)))]
                 (when-not (re-matches #"[0-9a-fA-F]{4}" hex)
                   (err j "bad \\u escape in string" {:hex hex}))
                 (recur (+ j 6) (conj buf (char (parse-int-radix hex 16)))))
            (err j "unsupported escape in string" {:escape (str e)})))
        :else (recur (inc j) (conj buf c))))))

(defn- read-regex
  "#\"...\" -- scanned raw. Regex escapes are not string escapes (\\d is legal
   here and illegal there), so this keeps the source text and does not decode."
  [^String s i]
  (loop [j (+ i 2)]
    (let [c (at s j)]
      (cond
        (nil? c) (err i "unterminated regex literal")
        (= c \\) (recur (+ j 2))
        (= c \") [{:t :regex :s (subs s i (inc j))} (inc j)]
        :else (recur (inc j))))))

(defn- read-char-literal
  "Reads a \\c / \\newline / \\uXXXX literal starting at the backslash."
  [^String s i]
  (let [j (inc i)
        c (at s j)]
    (when (nil? c) (err i "unterminated character literal"))
    ;; The first character after \\ is taken literally even if it is a
    ;; terminator (\\( \; \\space are all legal), then any further
    ;; word characters belong to a named or numeric form.
    (let [end (loop [k (inc j)]
                (if (and (< k (count s)) (not (terminator? (at s k)))) (recur (inc k)) k))
          tok (subs s (inc i) end)
          v (cond
              (= 1 (count tok)) (nth tok 0)
              (contains? named-chars tok) (get named-chars tok)
              (and (str/starts-with? tok "u") (re-matches #"u[0-9a-fA-F]{4}" tok))
              (char (parse-int-radix (subs tok 1) 16))
              :else (err i "unsupported character literal" {:token (str "\\" tok)}))]
      [{:t :atom :kind :char :v v :s (subs s i end)} end])))

(def ^:private int-re #"^[+-]?(0|[1-9][0-9]*)$")
(def ^:private float-re #"^[+-]?(0|[1-9][0-9]*)(\.[0-9]+)?([eE][+-]?[0-9]+)?$")

(defn- classify-token
  "Turns a bare token into [kind value], or refuses."
  [tok i]
  (cond
    (= tok "nil") [:nil nil]
    (= tok "true") [:bool true]
    (= tok "false") [:bool false]

    (str/starts-with? tok ":")
    (let [body (subs tok 1)]
      (when (empty? body) (err i "empty keyword"))
      (when (and (str/starts-with? body ":") (= *surface* :data))
        (err i "auto-resolved keyword is not data" {:token tok}))
      [:keyword (keyword body)])

    (re-matches int-re tok) [:int (parse-int-radix tok 10)]
    (re-matches float-re tok) [:float (parse-float* tok)]

    ;; 0xFA and friends: Clojure's reader accepts these and this workspace has
    ;; them (MIDI status bytes). The atom keeps its original :s, so the written
    ;; form stays hex; only the decoded value is decimal.
    ;; Clojure reads a leading zero as octal: #js {:mode 0600} is 384, not 600.
    (re-matches #"^[+-]?0[0-7]+$" tok)
    [:int (let [neg? (str/starts-with? tok "-")
                digits (subs tok (if (re-matches #"^[+-].*" tok) 2 1))
                m (parse-int-radix digits 8)]
            (if neg? (- m) m))]

    (re-matches #"^[+-]?0[xX][0-9a-fA-F]+$" tok)
    [:int (let [neg? (str/starts-with? tok "-")
                digits (subs tok (if (re-matches #"^[+-].*" tok) 3 2))
                m (parse-int-radix digits 16)]
            (if neg? (- m) m))]

    ;; Refuse the numeric shapes this notation does not carry, rather than
    ;; letting them fall through to :symbol -- a ratio read as a symbol is a
    ;; silent change of meaning, which is the failure this reader exists to avoid.
    (re-matches #"^[+-]?[0-9]+/[0-9]+$" tok)
    (err i "ratio literal has no Kotoba ADL representation" {:token tok})
    (re-matches #"^[+-]?[0-9]+[NM]$" tok)
    (err i "bigint/bigdec literal has no Kotoba ADL representation" {:token tok})
    (re-matches #"^[+-]?[0-9].*$" tok)
    (err i "unrecognised numeric literal" {:token tok})

    ;; Symbol shape is validated rather than assumed. Without this, a
    ;; git-annex pointer file (its whole content is /annex/objects/MD5E-...)
    ;; parses as a "symbol" and converts cleanly -- destroying the annex link
    ;; while every check reports success. 31 .edn files in this workspace are
    ;; annex pointers.
    (re-matches #"^[a-zA-Z*+!_?$%&=<>.-][a-zA-Z0-9*+!_?$%&=<>.#'-]*(/[a-zA-Z*+!_?$%&=<>.-][a-zA-Z0-9*+!_?$%&=<>.#'-]*)?$" tok)
    [:symbol (symbol tok)]

    ;; Source symbols are wider than EDN's (-> , some->> , clojure.core//).
    ;; The strict form above stays the rule for data, where it is what stops a
    ;; git-annex pointer from parsing as a symbol and converting cleanly.
    (= *surface* :source) [:symbol (symbol tok)]

    :else (err i "not a valid EDN token" {:token tok})))

(defn- read-token [^String s i]
  (let [end (loop [k i] (if (and (< k (count s)) (not (terminator? (at s k)))) (recur (inc k)) k))]
    (when (= end i) (err i "empty token" {:char (str (at s i))}))
    (let [tok (subs s i end)
          [kind v] (classify-token tok i)]
      [{:t :atom :kind kind :v v :s tok} end])))

;; ---------------------------------------------------------------- forms

(declare read-form read-prefixed read-cst*)

(def ^:private closers {:list \) :vector \] :map \} :set \} :fn-literal \)})

(defn- read-coll [^String s i kind open-len]
  (let [close (get closers kind)]
    (loop [j (+ i open-len) kids []]
      (let [c (at s j)]
        (cond
          (nil? c) (err i "unterminated collection" {:kind kind})
          (= c close) [{:t :coll :kind kind :children kids} (inc j)]
          (contains? #{\) \] \}} c) (err j "mismatched closing delimiter"
                                        {:kind kind :found (str c)})
          :else (let [[node nj] (read-form s j)]
                  (recur nj (conj kids node))))))))

(defn- read-prefixed
  "A prefix macro and the one form it applies to, keeping any trivia between."
  [^String s i prefix]
  (loop [j (+ i (count prefix)) trivia []]
    (let [[node nj] (read-form s j)]
      (if (contains? #{:ws :comment} (:t node))
        (recur nj (conj trivia node))
        [{:t :macro :prefix prefix :children (conj trivia node)} nj]))))

(defn- read-form
  "Reads one node (which may be trivia) at i. Returns [node next-index]."
  [^String s i]
  (let [c (at s i)]
    (cond
      (nil? c) (err i "unexpected end of input")

      (ws? c) (let [end (loop [k i] (if (and (< k (count s)) (ws? (at s k))) (recur (inc k)) k))]
                [{:t :ws :s (subs s i end)} end])

      (= c \;) (let [end (loop [k i] (if (and (< k (count s)) (not= \newline (at s k))) (recur (inc k)) k))]
                 [{:t :comment :s (subs s i end)} end])

      (= c \") (read-string-literal s i)
      (= c \\) (read-char-literal s i)

      (= c \() (read-coll s i :list 1)
      (= c \[) (read-coll s i :vector 1)
      (= c \{) (read-coll s i :map 1)

      (= c \#)
      (let [d (at s (inc i))]
        (cond
          ;; ##Inf / ##-Inf / ##NaN -- Clojure's symbolic values.
          (= d \#)
          (let [end (loop [k (+ i 2)]
                      (if (and (< k (count s)) (not (terminator? (at s k)))) (recur (inc k)) k))
                name* (subs s (+ i 2) end)
                v (case name*
                    "Inf" #?(:clj Double/POSITIVE_INFINITY :cljs js/Infinity)
                    "-Inf" #?(:clj Double/NEGATIVE_INFINITY :cljs (- js/Infinity))
                    "NaN" #?(:clj Double/NaN :cljs js/NaN)
                    (err i "unknown symbolic value" {:token (str "##" name*)}))]
            [{:t :atom :kind :float :v v :s (subs s i end)} end])

          (= d \{) (read-coll s i :set 2)
          (= d \() (read-coll s i :fn-literal 2)
          (= d \") (read-regex s i)
          (= d \') (read-prefixed s i "#'")
          (= d \?) (if (= \@ (at s (+ i 2)))
                     (read-prefixed s i "#?@")
                     (read-prefixed s i "#?"))
          (= d \_) (let [[node nj] (read-form s (+ i 2))]
                     [{:t :discard :children [node]} nj])
          ;; #:ns{...} -- a namespaced map. Without this branch it reads as a
          ;; tagged literal whose tag happens to start with a colon, which
          ;; converts cleanly and silently drops the namespace off every key.
          ;; 179 files in this workspace use it.
          (= d \:)
          (let [end (loop [k (inc i)]
                      (if (and (< k (count s)) (not (terminator? (at s k)))) (recur (inc k)) k))
                nstok (subs s (inc i) end)]
            (when (str/starts-with? nstok "::")
              (err i "auto-resolved namespaced map is not data" {:token nstok}))
            (when (< (count nstok) 2) (err i "empty map namespace"))
            (loop [j end trivia []]
              (let [[node nj] (read-form s j)]
                (cond
                  (contains? #{:ws :comment} (:t node)) (recur nj (conj trivia node))
                  (and (= :coll (:t node)) (= :map (:kind node)))
                  [{:t :nsmap :ns (subs nstok 1) :children (conj trivia node)} nj]
                  :else (err i "#:ns must be followed by a map" {:ns nstok})))))
          (nil? d) (err i "dangling #")
          (terminator? d) (err i "unsupported dispatch macro" {:after (str d)})
          :else
          ;; #tag <form> -- a tagged literal.
          (let [_ (let [e (loop [k (inc i)]
                            (if (and (< k (count s)) (not (terminator? (at s k)))) (recur (inc k)) k))]
                    ;; #js is a ClojureScript reader extension, not EDN. It reads
                    ;; to a host array, which has no Kotoba ADL spelling; turning
                    ;; it into (tag "js" ...) would hand every downstream reader a
                    ;; Form where it expects an array. Refuse and say so.
                    (when (and (= "js" (subs s (inc i) e)) (= *surface* :data))
                      (err i "#js is a ClojureScript reader extension, not EDN"
                           {:token "#js"})))
                end (loop [k (inc i)]
                      (if (and (< k (count s)) (not (terminator? (at s k)))) (recur (inc k)) k))
                tag (subs s (inc i) end)]
            (loop [j end trivia []]
              (let [[node nj] (read-form s j)]
                (if (contains? #{:ws :comment} (:t node))
                  (recur nj (conj trivia node))
                  [{:t :tagged :tag tag :children (conj trivia node)} nj]))))))

      (= c \^)
      (let [[m jm] (loop [j (inc i) trivia []]
                     (let [[node nj] (read-form s j)]
                       (if (contains? #{:ws :comment} (:t node))
                         (recur nj (conj trivia node))
                         [(conj trivia node) nj])))]
        (loop [j jm trivia []]
          (let [[node nj] (read-form s j)]
            (if (contains? #{:ws :comment} (:t node))
              (recur nj (conj trivia node))
              [{:t :meta :children (vec (concat m trivia [node]))} nj]))))

      (contains? #{\) \] \}} c) (err i "unbalanced closing delimiter" {:found (str c)})

      ;; Reader macros. These are SOURCE, never data -- edn->adl refuses them.
      ;; The reader accepts them so a .clj/.cljs/.cljc file can be parsed and
      ;; checked before it is renamed; refusing here would mean the source path
      ;; could not read the very files it exists to move.
      (contains? #{\' \` \@} c) (read-prefixed s i (str c))
      (= c \~) (if (= \@ (at s (inc i)))
                 (read-prefixed s i "~@")
                 (read-prefixed s i "~"))

      :else (read-token s i))))

;; ---------------------------------------------------------------- API

(defn read-cst
  "Reads the whole of s into a vector of top-level CST nodes (including trivia).
   Throws ex-info on anything it cannot classify.

   surface is :data (default, EDN rules) or :source (full Clojure reader)."
  ([^String s] (read-cst s :data))
  ([^String s surface]
   (binding [*surface* surface] (read-cst* s))))

(defn- read-cst* [^String s]
  (loop [i 0 acc []]
    (if (>= i (count s))
      acc
      (let [[node nj] (read-form s i)]
        (when (<= nj i) (err i "reader made no progress"))
        (recur nj (conj acc node))))))

(defn trivia? [node] (contains? #{:ws :comment} (:t node)))

(defn forms
  "The non-trivia nodes of a CST node sequence."
  [nodes]
  (vec (remove trivia? nodes)))

(defn print-cst
  "Renders a CST back to text. For a CST produced by read-cst this is the
   identity on the original string -- which is what makes it usable as the
   fidelity check for a transform."
  [nodes]
  (apply str
         (map (fn [n]
                (case (:t n)
                  (:ws :comment) (:s n)
                  :atom (:s n)
                  :coll (str (case (:kind n)
                               :list "(" :vector "[" :map "{" :set "#{" :fn-literal "#(")
                             (print-cst (:children n))
                             (case (:kind n)
                               (:list :fn-literal) ")" :vector "]" (:map :set) "}"))
                  :regex (:s n)
                  :macro (str (:prefix n) (print-cst (:children n)))
                  :nsmap (str "#:" (:ns n) (print-cst (:children n)))
                  :tagged (str "#" (:tag n) (print-cst (:children n)))
                  :discard (str "#_" (print-cst (:children n)))
                  :meta (str "^" (print-cst (:children n)))
                  (err 0 "unknown CST node" {:node (pr-str n)})))
              nodes)))
