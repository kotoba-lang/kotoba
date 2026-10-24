(ns scad.parser
  "Zero-dep portable CLJC. Restored from the legacy kami-engine/kami-scad Rust crate
  (`kami-scad/src/parser.rs`, deleted in kotoba-lang/kami-engine PR #82 \"Remove Rust
  workspace from kami-engine\") as part of the clj-wgsl migration (ADR-2607010930,
  com-junkawasaki/root).

  Hand-rolled tokenizer + recursive-descent parser for a small OpenSCAD subset:
  sphere/cube/cylinder primitives, translate/rotate/scale/color transform blocks,
  union/difference/intersection groups, and zero-arg module def/call. Produces an
  AST of tagged maps (`{:type :sphere :r ...}` etc, mirroring the original
  `ScadNode` enum 1:1)."
  (:require [kotoba.lang.text :as str]))

;; ---------------------------------------------------------------------------
;; Lexer
;; ---------------------------------------------------------------------------
;; Tokens are tagged vectors: [:ident s] [:number n] [:lparen] [:rparen]
;; [:lbracket] [:rbracket] [:lbrace] [:rbrace] [:comma] [:semi] [:eq] [:eof]

#?(:clj
   (defn- alpha? [c] (Character/isLetter ^char c))
   :cljs
   (defn- alpha? [c] (re-matches #"[A-Za-z]" (str c))))

#?(:clj
   (defn- alnum? [c] (or (Character/isLetterOrDigit ^char c) (= c \_)))
   :cljs
   (defn- alnum? [c] (or (re-matches #"[A-Za-z0-9]" (str c)) (= c \_))))

#?(:clj
   (defn- digit? [c] (Character/isDigit ^char c))
   :cljs
   (defn- digit? [c] (re-matches #"[0-9]" (str c))))

#?(:clj
   (defn- whitespace? [c] (Character/isWhitespace ^char c))
   :cljs
   (defn- whitespace? [c] (re-matches #"\s" (str c))))

(defn- parse-float [s]
  #?(:clj  (try (Double/parseDouble s) (catch Exception _ 0.0))
     :cljs (let [n (js/parseFloat s)] (if (js/isNaN n) 0.0 n))))

(defn- str->chars [src]
  (vec (seq src)))

(defn- lexer-new [src]
  {:chars (str->chars src) :pos 0})

(defn- peek-char [{:keys [chars pos]}]
  (get chars pos))

(defn- advance-char [lex]
  ;; returns [char new-lexer]
  (let [c (peek-char lex)]
    [c (update lex :pos inc)]))

(defn- skip-ws-comments [lex]
  (loop [lex lex]
    (let [c (peek-char lex)]
      (cond
        (nil? c) lex

        (whitespace? c)
        (recur (update lex :pos inc))

        (and (= c \/) (= (get (:chars lex) (inc (:pos lex))) \/))
        (recur (loop [lex lex]
                 (let [[c lex] (advance-char lex)]
                   (if (or (nil? c) (= c \newline))
                     lex
                     (recur lex)))))

        (and (= c \/) (= (get (:chars lex) (inc (:pos lex))) \*))
        (recur (loop [lex (update (update lex :pos inc) :pos inc)]
                 (let [[c lex] (advance-char lex)]
                   (cond
                     (nil? c) lex
                     (and (= c \*) (= (peek-char lex) \/)) (update lex :pos inc)
                     :else (recur lex)))))

        :else lex))))

(declare skip-unknown-char)

(defn- next-token [lex]
  ;; returns [token new-lexer]
  (let [lex (skip-ws-comments lex)
        c (peek-char lex)]
    (cond
      (nil? c) [[:eof] lex]

      (= c \() [[:lparen] (update lex :pos inc)]
      (= c \)) [[:rparen] (update lex :pos inc)]
      (= c \[) [[:lbracket] (update lex :pos inc)]
      (= c \]) [[:rbracket] (update lex :pos inc)]
      (= c \{) [[:lbrace] (update lex :pos inc)]
      (= c \}) [[:rbrace] (update lex :pos inc)]
      (= c \,) [[:comma] (update lex :pos inc)]
      (= c \;) [[:semi] (update lex :pos inc)]
      (= c \=) [[:eq] (update lex :pos inc)]

      (or (= c \-) (= c \.) (digit? c))
      (let [start (:pos lex)
            lex (if (= c \-) (update lex :pos inc) lex)
            lex (loop [lex lex]
                  (let [c (peek-char lex)]
                    (if (and c (or (digit? c) (= c \.)))
                      (recur (update lex :pos inc))
                      lex)))
            s (apply str (subvec (:chars lex) start (:pos lex)))]
        [[:number (parse-float s)] lex])

      (or (alpha? c) (= c \_) (= c \#))
      (let [start (:pos lex)
            lex (loop [lex lex]
                  (let [c (peek-char lex)]
                    (if (and c (alnum? c))
                      (recur (update lex :pos inc))
                      lex)))
            s (apply str (subvec (:chars lex) start (:pos lex)))]
        [[:ident s] lex])

      (= c \")
      (let [lex (update lex :pos inc)
            start (:pos lex)
            lex (loop [lex lex]
                  (let [c (peek-char lex)]
                    (if (and c (not= c \"))
                      (recur (update lex :pos inc))
                      lex)))
            s (apply str (subvec (:chars lex) start (:pos lex)))
            lex (update lex :pos inc)] ;; closing quote
        [[:ident s] lex])

      :else
      (skip-unknown-char lex))))

;; fallback: skip unknown char, retry
(defn- skip-unknown-char [lex]
  (next-token (update lex :pos inc)))

(defn- tokenize [src]
  (loop [lex (lexer-new src)
         toks []]
    (let [[tok lex] (next-token lex)]
      (if (= tok [:eof])
        (conj toks [:eof])
        (recur lex (conj toks tok))))))

;; ---------------------------------------------------------------------------
;; Parser
;; ---------------------------------------------------------------------------
;; Parser state is `{:tokens [...] :pos (atom idx)}`; mutation via atom mirrors
;; the original `&mut self` recursive-descent structure closely.

(defn- parser-new [tokens]
  {:tokens tokens :pos (atom 0)})

(defn- peek-tok [{:keys [tokens pos]}]
  (get tokens @pos [:eof]))

(defn- advance-tok! [{:keys [tokens pos] :as st}]
  (let [t (get tokens @pos [:eof])]
    (swap! pos inc)
    t))

(defn- expect! [st expected-tag]
  ;; lenient: always advances (matches original "lenient: skip" behavior)
  (advance-tok! st))

(defn- parse-number! [st]
  (let [t (advance-tok! st)]
    (if (= (first t) :number) (second t) 0.0)))

(defn- parse-vec3! [st]
  (expect! st :lbracket)
  (let [x (parse-number! st)]
    (expect! st :comma)
    (let [y (parse-number! st)]
      (expect! st :comma)
      (let [z (parse-number! st)]
        (expect! st :rbracket)
        [x y z]))))

(defn- color-name->rgba [name]
  (case (str/lower name)
    "red" [1.0 0.0 0.0 1.0]
    "green" [0.0 1.0 0.0 1.0]
    "blue" [0.0 0.0 1.0 1.0]
    "white" [1.0 1.0 1.0 1.0]
    "black" [0.0 0.0 0.0 1.0]
    "yellow" [1.0 1.0 0.0 1.0]
    "cyan" [0.0 1.0 1.0 1.0]
    "magenta" [1.0 0.0 1.0 1.0]
    "orange" [1.0 0.5 0.0 1.0]
    "purple" [0.5 0.0 0.5 1.0]
    ("gray" "grey") [0.5 0.5 0.5 1.0]
    "pink" [1.0 0.75 0.8 1.0]
    [0.5 0.5 0.5 1.0]))

(defn- parse-color-arg! [st]
  (let [t (peek-tok st)]
    (cond
      (= t [:lbracket])
      (do (advance-tok! st)
          (let [r (parse-number! st)]
            (expect! st :comma)
            (let [g (parse-number! st)]
              (expect! st :comma)
              (let [b (parse-number! st)
                    a (if (= (peek-tok st) [:comma])
                        (do (advance-tok! st) (parse-number! st))
                        1.0)]
                (expect! st :rbracket)
                [r g b a]))))

      (= (first t) :ident)
      (color-name->rgba (second (advance-tok! st)))

      :else [0.5 0.5 0.5 1.0])))

(declare parse-statement! parse-children!)

(defn- skip-semi! [st]
  (when (= (peek-tok st) [:semi])
    (advance-tok! st)))

(defn- parse-children! [st]
  (if (= (peek-tok st) [:lbrace])
    (do
      (advance-tok! st)
      (let [children (loop [acc []]
                        (if (or (= (peek-tok st) [:rbrace]) (= (peek-tok st) [:eof]))
                          acc
                          (let [node (parse-statement! st)]
                            (recur (if node (conj acc node) acc)))))]
        (expect! st :rbrace)
        children))
    (if-let [node (parse-statement! st)]
      [node]
      [])))

(defn- parse-sphere! [st]
  (advance-tok! st)
  (expect! st :lparen)
  (loop [r 0.5]
    (let [t (peek-tok st)]
      (if (or (= t [:rparen]) (= t [:eof]))
        (do (expect! st :rparen) (skip-semi! st) {:type :sphere :r r})
        (let [r (cond
                  (= t [:ident "r"]) (do (advance-tok! st) (expect! st :eq) (parse-number! st))
                  (= (first t) :number) (parse-number! st)
                  :else (do (advance-tok! st) r))]
          (when (= (peek-tok st) [:comma]) (advance-tok! st))
          (recur r))))))

(defn- parse-cube! [st]
  (advance-tok! st)
  (expect! st :lparen)
  (loop [size [1.0 1.0 1.0] center false]
    (let [t (peek-tok st)]
      (if (or (= t [:rparen]) (= t [:eof]))
        (do (expect! st :rparen) (skip-semi! st) {:type :cube :size size :center center})
        (let [[size center]
              (cond
                (= t [:lbracket]) [(parse-vec3! st) center]
                (= (first t) :number) (let [s (parse-number! st)] [[s s s] center])
                (= t [:ident "center"])
                (do (advance-tok! st) (expect! st :eq)
                    [size (= (advance-tok! st) [:ident "true"])])
                (= t [:ident "size"])
                (do (advance-tok! st) (expect! st :eq) [(parse-vec3! st) center])
                :else (do (advance-tok! st) [size center]))]
          (when (= (peek-tok st) [:comma]) (advance-tok! st))
          (recur size center))))))

(defn- parse-cylinder! [st]
  (advance-tok! st)
  (expect! st :lparen)
  (loop [h 1.0 r1 0.5 r2 0.5 center false]
    (let [t (peek-tok st)]
      (if (or (= t [:rparen]) (= t [:eof]))
        (do (expect! st :rparen) (skip-semi! st)
            {:type :cylinder :h h :r1 r1 :r2 r2 :center center})
        (let [[h r1 r2 center]
              (cond
                (= t [:ident "h"]) (do (advance-tok! st) (expect! st :eq) [(parse-number! st) r1 r2 center])
                (= t [:ident "r"]) (do (advance-tok! st) (expect! st :eq)
                                        (let [r (parse-number! st)] [h r r center]))
                (= t [:ident "r1"]) (do (advance-tok! st) (expect! st :eq) [h (parse-number! st) r2 center])
                (= t [:ident "r2"]) (do (advance-tok! st) (expect! st :eq) [h r1 (parse-number! st) center])
                (= t [:ident "center"])
                (do (advance-tok! st) (expect! st :eq)
                    [h r1 r2 (= (advance-tok! st) [:ident "true"])])
                (= (first t) :number) [(parse-number! st) r1 r2 center]
                :else (do (advance-tok! st) [h r1 r2 center]))]
          (when (= (peek-tok st) [:comma]) (advance-tok! st))
          (recur h r1 r2 center))))))

(defn- parse-transform-block! [st node-type]
  (advance-tok! st)
  (expect! st :lparen)
  (let [v (parse-vec3! st)]
    (expect! st :rparen)
    (let [children (parse-children! st)]
      {:type node-type :v v :children children})))

(defn- parse-color! [st]
  (advance-tok! st)
  (expect! st :lparen)
  (let [rgba (parse-color-arg! st)]
    (expect! st :rparen)
    (let [children (parse-children! st)]
      {:type :color :rgba rgba :children children})))

(defn- parse-group! [st node-type]
  (advance-tok! st)
  (expect! st :lparen)
  (expect! st :rparen)
  (let [children (parse-children! st)]
    {:type node-type :children children}))

(defn- parse-module! [st]
  (advance-tok! st)
  (let [mname (let [t (advance-tok! st)]
                (if (= (first t) :ident) (second t) "unnamed"))]
    (expect! st :lparen)
    (expect! st :rparen)
    (let [body (parse-children! st)]
      {:type :module-def :name mname :body body})))

(defn- parse-module-call! [st name]
  (advance-tok! st)
  (if (= (peek-tok st) [:lparen])
    (do (advance-tok! st) (expect! st :rparen) (skip-semi! st)
        {:type :module-call :name name})
    (do (skip-semi! st) nil)))

(defn- parse-statement! [st]
  (let [t (peek-tok st)]
    (cond
      (= (first t) :ident)
      (let [name (second t)]
        (case name
          "sphere" (parse-sphere! st)
          "cube" (parse-cube! st)
          "cylinder" (parse-cylinder! st)
          "translate" (parse-transform-block! st :translate)
          "rotate" (parse-transform-block! st :rotate)
          "scale" (parse-transform-block! st :scale)
          "color" (parse-color! st)
          "union" (parse-group! st :union)
          "difference" (parse-group! st :difference)
          "intersection" (parse-group! st :intersection)
          "module" (parse-module! st)
          (parse-module-call! st name)))

      (= t [:eof]) nil

      :else (do (advance-tok! st) nil))))

(defn parse
  "Parse OpenSCAD source `src` (subset: sphere/cube/cylinder,
  translate/rotate/scale/color, union/difference/intersection,
  zero-arg module def/call) into a vector of AST nodes (tagged maps)."
  [src]
  (let [tokens (tokenize src)
        st (parser-new tokens)]
    (loop [acc []]
      (if (= (peek-tok st) [:eof])
        acc
        (let [node (parse-statement! st)]
          (recur (if node (conj acc node) acc)))))))
