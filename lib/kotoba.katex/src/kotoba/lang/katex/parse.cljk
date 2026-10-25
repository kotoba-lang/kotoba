(ns kotoba.lang.katex.parse
  "Recursive-descent parser from a TeX-math-like string into a pure EDN math
  AST. This is a native v1 subset of TeX math, NOT full TeX/KaTeX parity —
  see the namespace-level docstring below for exactly what is supported.

  ## AST shape (the real deliverable — callers may also build this directly
  without going through the string parser)

  Every node is a vector `[tag & args]`:

    [:row    [node ...]]        ; top-level sequence of sibling nodes
    [:group  [node ...]]        ; a `{...}` grouped sequence of sibling nodes
    [:num    \"123.45\"]        ; a number literal (digits, optional single '.')
    [:sym    \"x\"]             ; an identifier: a single ASCII letter, or a
                                 ; Greek letter spelled out as its unicode char
                                 ; (e.g. \\alpha -> [:sym \"α\"])
    [:op     \"+\"]             ; an operator/relation/large-operator, spelled
                                 ; out as its unicode char where one exists
                                 ; (e.g. \\leq -> [:op \"≤\"], \\sum -> [:op \"∑\"])
    [:frac   num den]           ; \\frac{num}{den}
    [:sqrt   index-or-nil rad]  ; \\sqrt{rad} (index nil) or \\sqrt[index]{rad}
    [:sup    base exp]          ; base^exp
    [:sub    base sub]          ; base_sub
    [:supsub base sub exp]      ; base^exp_sub and base_sub^exp (either input
                                 ; order collapses to this single node)
    [:accent char base]        ; \\hat{base}/\\bar{base}/\\vec{base}/etc --
                                 ; char is the combining Unicode diacritic
    [:unknown \"cmdname\"]      ; an unrecognized \\cmdname (v1 fallback —
                                 ; rendered as literal text by the renderer,
                                 ; never dropped silently)

  `num`/`den`/`base`/`exp`/`sub`/`rad`/index args are themselves AST nodes:
  when a `{...}` group parses to exactly one child node, that child is used
  directly (unwrapped) rather than wrapping it in a redundant `[:group [x]]`.

  ## Supported v1 subset

  - Fractions: `\\frac{a}{b}` (braces required; TeX's brace-less
    `\\frac12` single-token shorthand is also accepted since sup/sub/frac
    arguments each parse exactly one atom).
  - Superscript `^` and subscript `_`, in either order, combining into a
    single `:supsub` node when both are present on the same base.
  - `\\sqrt{x}` and `\\sqrt[n]{x}`.
  - Accents: `\\hat \\bar \\vec \\dot \\tilde \\ddot`, each a single-argument
    command (same brace-or-single-token argument grabbing as `\\sqrt`'s
    radicand) rendered as MathML `<mover>` with the accent's own combining
    Unicode diacritic as the over-script.
  - Grouping with `{ ... }`.
  - Greek letters: the common lowercase set (alpha..omega) plus the
    uppercase letters that have a distinct glyph from Latin (Gamma, Delta,
    Theta, Lambda, Xi, Pi, Sigma, Upsilon, Phi, Psi, Omega).
  - Common operators/relations: `\\sum \\int \\prod \\leq \\geq \\neq
    \\times \\cdot \\pm \\mp \\infty \\to \\rightarrow \\leftarrow \\in
    \\forall \\exists \\partial \\nabla \\approx \\equiv \\subset \\supset
    \\cup \\cap \\cdots \\ldots`.
  - Numbers (digit runs with an optional single decimal point) and single
    ASCII-letter identifiers; adjacency in a row is implicit
    multiplication/juxtaposition — there is no dedicated AST node for it,
    sibling atoms in a `:row`/`:group` are simply typeset next to each
    other, exactly as TeX itself does.
  - Ordinary single-character operators not covered above (`+ - = < > ( )
    [ ] , .` etc.) pass through as `[:op \"<char>\"]`.
  - Unrecognized `\\command` names become `[:unknown \"command\"]` rather
    than throwing or being dropped — the renderer falls back to literal
    text so information is never silently lost.

  ## Explicitly NOT supported in v1

  Matrices/arrays (`\\begin{matrix}`...), `\\left`/`\\right` auto-sizing
  delimiters, `\\overline` (a variable-width line over a whole expression,
  distinct from the fixed-width `\\bar` accent above), text mode (`\\text{}`),
  spacing commands (`\\, \\; \\quad`), font commands (`\\mathbf` etc.),
  multi-letter identifiers via `\\mathrm{abc}`, and the long tail of TeX
  math symbols beyond the list above. Full glyph-level layout (font
  metrics) is out of scope entirely — this library renders through
  MathML instead (see `kotoba.lang.katex.mathml`), letting a MathML-capable
  renderer do glyph layout."
  (:require [kotoba.lang.text :as str]))

;; ---------------------------------------------------------------------------
;; command tables

(def greek
  "TeX Greek-letter control words -> unicode character."
  {"alpha" "α" "beta" "β" "gamma" "γ" "delta" "δ" "epsilon" "ε" "zeta" "ζ"
   "eta" "η" "theta" "θ" "iota" "ι" "kappa" "κ" "lambda" "λ" "mu" "μ"
   "nu" "ν" "xi" "ξ" "omicron" "ο" "pi" "π" "rho" "ρ" "sigma" "σ" "tau" "τ"
   "upsilon" "υ" "phi" "φ" "chi" "χ" "psi" "ψ" "omega" "ω"
   "Gamma" "Γ" "Delta" "Δ" "Theta" "Θ" "Lambda" "Λ" "Xi" "Ξ" "Pi" "Π"
   "Sigma" "Σ" "Upsilon" "Υ" "Phi" "Φ" "Psi" "Ψ" "Omega" "Ω"})

(def ops
  "TeX operator/relation control words -> unicode character."
  {"sum" "∑" "int" "∫" "prod" "∏"
   "leq" "≤" "geq" "≥" "neq" "≠" "approx" "≈" "equiv" "≡"
   "times" "×" "cdot" "⋅" "pm" "±" "mp" "∓" "infty" "∞"
   "to" "→" "rightarrow" "→" "leftarrow" "←"
   "in" "∈" "forall" "∀" "exists" "∃"
   "partial" "∂" "nabla" "∇"
   "subset" "⊂" "supset" "⊃" "cup" "∪" "cap" "∩"
   "cdots" "⋯" "ldots" "…"})

(def accents
  "TeX single-character accent control words -> the combining Unicode
  diacritic (written as \\uXXXX escapes, not the literal invisible
  character, so the source stays legible) used as the MathML <mover>'s
  own over-script. Each takes one argument (same brace-or-single-token
  grabbing as \\sqrt's radicand): combining circumflex U+0302 (hat),
  macron U+0304 (bar), right arrow above U+20D7 (vec), dot above U+0307
  (dot), tilde U+0303 (tilde), diaeresis U+0308 (ddot)."
  {"hat" "\u0302" "bar" "\u0304" "vec" "\u20D7"
   "dot" "\u0307" "tilde" "\u0303" "ddot" "\u0308"})

;; ---------------------------------------------------------------------------
;; character predicates (portable across clj/cljs; no java.lang.Character)

(def ^:private ws-chars #{\space \tab \newline \return \formfeed})

(defn- whitespace? [c] (contains? ws-chars c))
(defn- digit? [c] (and c (<= (int \0) (int c) (int \9))))
(defn- letter? [c] (and c (or (<= (int \a) (int c) (int \z))
                               (<= (int \A) (int c) (int \Z)))))

;; ---------------------------------------------------------------------------
;; parser state: a mutable cursor over an immutable string, held in an atom
;; so the recursive-descent functions below can share/advance one position.

(defn- make-state [s] (atom {:s s :i 0 :n (count s)}))
(defn- eof? [st] (let [{:keys [i n]} @st] (>= i n)))
(defn- peek-ch [st] (let [{:keys [s i n]} @st] (when (< i n) (nth s i))))
(defn- advance! [st] (swap! st update :i inc) nil)
(defn- skip-ws! [st] (while (and (not (eof? st)) (whitespace? (peek-ch st))) (advance! st)))

(defn- expect! [st c]
  (if (= (peek-ch st) c)
    (advance! st)
    (throw (ex-info (str "katex parse error: expected '" c "'")
                     {:expected c :found (peek-ch st) :at (:i @st) :input (:s @st)}))))

(defn- read-while! [st pred]
  (loop [acc []]
    (if (and (not (eof? st)) (pred (peek-ch st)))
      (let [c (peek-ch st)]
        (advance! st)
        (recur (conj acc c)))
      (apply str acc))))

(defn- read-number! [st]
  "Digit run with an optional single '.' followed by more digits."
  (let [int-part (read-while! st digit?)]
    (if (and (= (peek-ch st) \.)
             (let [{:keys [s i n]} @st] (and (< (inc i) n) (digit? (nth s (inc i))))))
      (do (advance! st) ; consume '.'
          (str int-part "." (read-while! st digit?)))
      int-part)))

(defn- read-word! [st]
  "Consecutive ASCII letters, e.g. the command name after a backslash."
  (read-while! st letter?))

;; forward declarations
(declare parse-row! parse-term! parse-atom!)

(defn- wrap-row
  "A parsed `{...}`/bracketed sequence: a single child is unwrapped, more
  than one is wrapped in `[:group [...]]`, zero children is an empty group."
  [nodes]
  (cond
    (= 1 (count nodes)) (first nodes)
    :else [:group (vec nodes)]))

(defn- parse-braced-arg!
  "Parse a `{ ... }` argument (required by \\frac / \\sqrt) OR, if the
  brace is absent, a single TeX \"token\" (TeX's brace-less shorthand,
  e.g. \\frac12 — note this is exactly one character/command, not a
  whole digit run, matching real TeX argument-grabbing semantics)."
  [st]
  (skip-ws! st)
  (let [c (peek-ch st)]
    (cond
      (= c \{)
      (do (advance! st)
          (let [row (parse-row! st #{\}})]
            (expect! st \})
            (wrap-row row)))

      (digit? c) (do (advance! st) [:num (str c)])
      (letter? c) (do (advance! st) [:sym (str c)])
      :else (parse-atom! st))))

(defn- parse-command! [st]
  (let [word (read-word! st)]
    (cond
      (empty? word)
      ;; \<non-letter>: e.g. "\\{" — treat the escaped char as a literal op.
      (let [c (peek-ch st)]
        (if c (do (advance! st) [:op (str c)])
            [:unknown ""]))

      (= word "frac")
      (let [n (parse-braced-arg! st)
            d (parse-braced-arg! st)]
        [:frac n d])

      (= word "sqrt")
      (do (skip-ws! st)
          (let [idx (when (= (peek-ch st) \[)
                      (do (advance! st)
                          (let [row (parse-row! st #{\]})]
                            (expect! st \])
                            (wrap-row row))))
                rad (parse-braced-arg! st)]
            [:sqrt idx rad]))

      (contains? accents word) [:accent (get accents word) (parse-braced-arg! st)]

      (contains? greek word) [:sym (get greek word)]
      (contains? ops word) [:op (get ops word)]
      :else [:unknown word])))

(defn- parse-atom!
  "Parse a single primary atom (no ^ / _ handling — see `parse-term!`)."
  [st]
  (skip-ws! st)
  (let [c (peek-ch st)]
    (cond
      (nil? c) nil

      (= c \{)
      (do (advance! st)
          (let [row (parse-row! st #{\}})]
            (expect! st \})
            (wrap-row row)))

      (= c \\)
      (do (advance! st) (parse-command! st))

      (digit? c) [:num (read-number! st)]

      (letter? c) (do (advance! st) [:sym (str c)])

      :else (do (advance! st) [:op (str c)]))))

(defn- parse-term!
  "Parse one atom plus any trailing ^ / _ scripts, collapsing both into a
  single :supsub node regardless of which order they appear in."
  [st]
  (let [base (parse-atom! st)]
    (loop [sub nil sup nil]
      (skip-ws! st)
      (cond
        (and (= (peek-ch st) \_) (nil? sub))
        (do (advance! st) (recur (parse-atom! st) sup))

        (and (= (peek-ch st) \^) (nil? sup))
        (do (advance! st) (recur sub (parse-atom! st)))

        :else
        (cond
          (and sub sup) [:supsub base sub sup]
          sup [:sup base sup]
          sub [:sub base sub]
          :else base)))))

(defn- parse-row!
  "Parse a sequence of terms until eof or a char in `stop-set` is next."
  [st stop-set]
  (loop [acc []]
    (skip-ws! st)
    (if (or (eof? st) (contains? stop-set (peek-ch st)))
      acc
      (recur (conj acc (parse-term! st))))))

(defn parse
  "Parse a TeX-math-like string `s` into a `[:row [node ...]]` AST. See the
  namespace docstring for the supported subset and exact AST shape."
  [s]
  (let [st (make-state s)
        row (parse-row! st #{})]
    [:row row]))
