(ns kotoba.lang.katex.mathml
  "Render a `kotoba.lang.katex.parse` AST to MathML: first to a Hiccup-like
  EDN shape (`[:mfrac ...]`, `[:msup ...]`, `[:mi ...]`, ...), then to a
  MathML XML string. Rendering through MathML — rather than doing
  glyph-level layout ourselves — is the pragmatic native, dependency-free
  choice for v1: any MathML-capable renderer (browsers, Word/OOXML import,
  etc.) performs the actual glyph layout.

  ## EDN shape

  Each node is `[tag & children]` where `tag` is a MathML element keyword.
  Leaf tags (`:mi :mn :mo :mtext`) carry a single string child; structural
  tags (`:mrow :mfrac :msup :msub :msubsup :msqrt :mroot :mover`) carry
  child nodes. No attribute map is threaded through — v1 needs none of the
  optional MathML attributes to render the supported AST subset (an
  accent's `<mover>` relies on the accent character itself falling in
  MathML's own operator-dictionary combining-diacritic range for
  renderers to infer `accent=\"true\"` positioning, rather than this
  library emitting the attribute explicitly)."
  (:require [kotoba.lang.text :as str]))

(def ^:private leaf-tags #{:mi :mn :mo :mtext})

(defn ast->mathml
  "Convert a `kotoba.lang.katex.parse` AST node into the MathML EDN shape
  documented above."
  [node]
  (when node
    (let [[tag a b c] node]
      (case tag
        (:row :group) (into [:mrow] (map ast->mathml a))
        :num [:mn a]
        :sym [:mi a]
        :op [:mo a]
        :unknown [:mtext (str "\\" a)]
        :frac [:mfrac (ast->mathml a) (ast->mathml b)]
        :sup [:msup (ast->mathml a) (ast->mathml b)]
        :sub [:msub (ast->mathml a) (ast->mathml b)]
        :supsub [:msubsup (ast->mathml a) (ast->mathml b) (ast->mathml c)]
        :sqrt (if (nil? a)
                [:msqrt (ast->mathml b)]
                [:mroot (ast->mathml b) (ast->mathml a)])
        :accent [:mover (ast->mathml b) [:mo a]]
        (throw (ex-info "kotoba.lang.katex.mathml: unrecognized AST node"
                         {:node node}))))))

(defn esc
  "Escape &, <, >, \" for safe MathML/XML text content."
  [s]
  ;; One pass, not a chain. The chain was correct only because `&` happened to
  ;; come first: any other order double-escapes the `&` that `&lt;` introduces.
  ;; `escape` never re-reads what it has emitted, so the order of the map
  ;; cannot matter.
  (str/escape (str s) {\& "&amp;" \< "&lt;" \> "&gt;" \" "&quot;"}))

(defn mathml->str
  "Render MathML EDN (as produced by `ast->mathml`) to an XML string,
  without the enclosing `<math>` root — see `ast->mathml-string` for that."
  [[tag & rest-children :as node]]
  (if (nil? node)
    ""
    (let [tag-name (name tag)]
      (if (contains? leaf-tags tag)
        (str "<" tag-name ">" (esc (first rest-children)) "</" tag-name ">")
        (str "<" tag-name ">" (apply str (map mathml->str rest-children)) "</" tag-name ">")))))

(defn ast->mathml-string
  "Convert a `kotoba.lang.katex.parse` AST node directly into a full
  `<math>...</math>` MathML XML string."
  [node]
  (str "<math xmlns=\"http://www.w3.org/1998/Math/MathML\">"
       (mathml->str (ast->mathml node))
       "</math>"))
