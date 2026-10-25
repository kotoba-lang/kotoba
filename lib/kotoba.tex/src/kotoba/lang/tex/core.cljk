(ns kotoba.lang.tex.core
  "EDN-first LaTeX *document generator* — the sibling of `kotoba.lang.html` /
  `kotoba.lang.css` / `svg.core` for LaTeX source text. This is a generator,
  not a TeX engine: it turns an EDN AST into valid `.tex` source text
  deterministically. It does not run pdflatex, compute font metrics, or lay
  out pages — pipe the returned string to your own TeX toolchain for that.

  The canonical element shape is Hiccup-like:

    [:section {} \"Introduction\"]          => \\section{Introduction}
    [:frac {} \"1\" \"2\"]                  => \\frac{1}{2}
    [:documentclass {:opt \"12pt\"} \"article\"] => \\documentclass[12pt]{article}

  and for environments:

    [:env \"itemize\" {} [:item {} \"a\"] [:item {} \"b\"]]
      => \\begin{itemize}\\item a\\item b\\end{itemize}

  Rules:
  - A **command** node `[tag opts & args]`: `tag` is a keyword whose `name` is
    the literal LaTeX control word (no leading backslash). `opts` is always a
    (possibly empty) map; `:opt` renders as a `[...]` optional-argument group.
    Each remaining `arg` becomes its own `{...}` required-argument group — a
    command with zero args (and no `:opt`) renders bare, e.g. `[:newpage {}]`
    => `\\newpage`. `:item` is special-cased (LaTeX's `\\item` does not take a
    braced argument): `[:item {} \"a\"]` => `\\item a` (a single separating
    space, not braces).
  - An **environment** node `[:env name opts & body]`: `name` is the plain
    string environment name. `opts` supports `:opt` (`[...]`) and `:arg`
    (a single `{...}` required group right after `\\begin{name}`, e.g. the
    column spec of `tabular`). The `body` children are rendered and
    concatenated directly (not each wrapped in its own `{...}` group) — they
    are sibling content, not command arguments.
  - Plain strings are escaped automatically (`# $ % & _ { } ~ ^ \\`) so
    callers never have to hand-escape body text. Use `[:raw s]` to emit `s`
    verbatim (no escaping) when you already have literal TeX source (e.g.
    math-mode content).
  - A vector whose first element is itself a vector is a *fragment*: its
    children are rendered and concatenated as siblings, with no wrapping tag.
    `document` returns a fragment (`\\documentclass{...}` followed by a
    sibling `document` environment)."
  (:require [kotoba.lang.text :as str]))

;; ---------------------------------------------------------------------------
;; Escaping

(def ^:private escapes
  "Character -> LaTeX-safe replacement. Backslash is included so escaping a
  string is safe even if it already contains a literal backslash — it becomes
  visible text (\\textbackslash{}), not a stray active character."
  {\# "\\#"
   \$ "\\$"
   \% "\\%"
   \& "\\&"
   \_ "\\_"
   \{ "\\{"
   \} "\\}"
   \~ "\\textasciitilde{}"
   \^ "\\textasciicircum{}"
   \\ "\\textbackslash{}"})

(defn escape
  "Escape LaTeX special characters (# $ % & _ { } ~ ^ \\) in plain text `s` so
  it is safe to place in a LaTeX document body. Single left-to-right pass
  over `s`'s characters — never re-scans its own output, so it cannot
  double-escape."
  [s]
  (apply str (map #(get escapes % %) (str s))))

;; ---------------------------------------------------------------------------
;; Rendering

(declare render)

(defn- fragment? [node]
  (and (vector? node) (vector? (first node))))

(defn- raw-node? [node]
  (and (vector? node) (= :raw (first node))))

(defn- env-node? [node]
  (and (vector? node) (= :env (first node))))

(defn- command-node? [node]
  (and (vector? node) (keyword? (first node))))

(defn- render-opt-group [opt]
  (if (some? opt) (str "[" (render opt) "]") ""))

(defn- render-command [[tag opts & args]]
  (let [nm (name tag)]
    ;; \item is the one common command that does not take a braced
    ;; argument: its content is plain following text (e.g. "\item a"), so it
    ;; is special-cased here rather than wrapped in "{...}".
    (if (= nm "item")
      (str "\\item"
           (render-opt-group (:opt opts))
           (when (seq args) (str " " (apply str (map render args)))))
      (str "\\" nm
           (render-opt-group (:opt opts))
           (apply str (map #(str "{" (render %) "}") args))))))

(defn- render-env [[_ ename opts & body]]
  (str "\\begin{" ename "}"
       (render-opt-group (:opt opts))
       (if (some? (:arg opts)) (str "{" (render (:arg opts)) "}") "")
       (apply str (map render body))
       "\\end{" ename "}"))

(defn render
  "Render a `tex` EDN node (or a whole document) to a LaTeX source string.
  Deterministic: the same AST always renders to the same string."
  [node]
  (cond
    (nil? node) ""
    (string? node) (escape node)
    (fragment? node) (apply str (map render node))
    (raw-node? node) (apply str (rest node))
    (env-node? node) (render-env node)
    (command-node? node) (render-command node)
    :else (escape (str node))))

;; ---------------------------------------------------------------------------
;; Generic escape hatch

(defn command
  "Generic escape hatch: build a `\\name[opt]{arg}...` command node. `name` is
  the plain command name (no backslash), e.g. `(command \"textbf\" \"hi\")`
  => `[:textbf {} \"hi\"]` => `\\textbf{hi}`. An optional leading map argument
  supplies `:opt` for the `[...]` group, e.g.
  `(command \"documentclass\" {:opt \"12pt\"} \"article\")`."
  [name & args]
  (let [[opts args] (if (map? (first args))
                       [(first args) (rest args)]
                       [{} args])]
    (into [(keyword name) opts] args)))

(defn env
  "Generic escape hatch: build an `[:env name opts & body]` node directly.
  `opts` supports `:opt` and `:arg` (see namespace docstring)."
  [name opts & body]
  (into [:env name opts] body))

(defn raw
  "Wrap a literal TeX source string so `render` emits it verbatim, bypassing
  automatic escaping. Use for content that is already TeX (e.g. math mode)."
  [s]
  [:raw s])

;; ---------------------------------------------------------------------------
;; Document helpers

(defn document
  "Build a full document fragment: `\\documentclass[opt]{class}`, any
  `preamble` command nodes (e.g. `\\usepackage{...}`), then a sibling
  `document` environment wrapping `body`.

  `opts` keys: `:class` (default \"article\"), `:opt` (documentclass options
  string, e.g. \"12pt,a4paper\"), `:preamble` (a seq of command nodes emitted
  between `\\documentclass` and `\\begin{document}`)."
  [{:keys [class opt preamble] :or {class "article"}} & body]
  (into [[:documentclass (if (some? opt) {:opt opt} {}) class]]
        (concat preamble [(into [:env "document" {}] body)])))

(defn section
  "`\\section{title}`, or `\\section*{title}` when `:star? true`."
  ([title] (section title {}))
  ([title {:keys [star?]}] [(keyword (str "section" (when star? "*"))) {} title]))

(defn subsection
  "`\\subsection{title}`, or `\\subsection*{title}` when `:star? true`."
  ([title] (subsection title {}))
  ([title {:keys [star?]}] [(keyword (str "subsection" (when star? "*"))) {} title]))

(defn subsubsection
  "`\\subsubsection{title}`, or `\\subsubsection*{title}` when `:star? true`."
  ([title] (subsubsection title {}))
  ([title {:keys [star?]}] [(keyword (str "subsubsection" (when star? "*"))) {} title]))

(defn item
  "`\\item content` (an `itemize`/`enumerate` list entry). `\\item` takes no
  braced argument in LaTeX — `content` nodes are rendered and concatenated as
  plain following text after a single separating space, e.g.
  `(item \"a\")` => `\\item a`."
  [& content]
  (into [:item {}] content))

(defn- as-item [x]
  (if (and (vector? x) (= :item (first x))) x (item x)))

(defn itemize
  "`\\begin{itemize}...\\end{itemize}`. Each of `items` is either an already
  built `item` node or a bare value, which is coerced via `item`."
  [& items]
  (into [:env "itemize" {}] (map as-item items)))

(defn enumerate
  "`\\begin{enumerate}...\\end{enumerate}`. See `itemize` for item coercion."
  [& items]
  (into [:env "enumerate" {}] (map as-item items)))

;; ---------------------------------------------------------------------------
;; Math

(defn math
  "Inline math mode: `$content$`. `content` is emitted verbatim (raw TeX) —
  math source is not text to be escaped, since it legitimately contains `^`,
  `_`, `\\`, etc."
  [content]
  [:raw (str "$" content "$")])

(defn display-math
  "Display math mode: `\\[content\\]`. See `math` re: verbatim content."
  [content]
  [:raw (str "\\[" content "\\]")])

(defn frac
  "`\\frac{num}{denom}`."
  [num denom]
  [:frac {} num denom])

(defn sqrt
  "`\\sqrt{x}`, or `\\sqrt[n]{x}` when the two-arg form is used."
  ([x] [:sqrt {} x])
  ([n x] [:sqrt {:opt n} x]))

;; ---------------------------------------------------------------------------
;; Tables

(defn tabular
  "`\\begin{tabular}{colspec}row1cell1 & row1cell2 \\\\\\n...\\end{tabular}`.
  `colspec` is the plain column-spec string (e.g. \"c|c|c\"). `rows` is a seq
  of rows, each a seq of cells; cells are rendered individually (so plain
  string cells are escaped) and joined with `&`, rows joined with `\\\\`."
  [colspec rows]
  (let [render-row (fn [row] (str/join " & " (map render row)))]
    [:env "tabular" {:arg colspec}
     [:raw (str/join " \\\\\n" (map render-row rows))]]))
