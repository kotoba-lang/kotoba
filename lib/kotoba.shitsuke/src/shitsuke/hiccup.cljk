(ns shitsuke.hiccup
  "Hiccup → HTML string renderer (.cljc, babashka-safe).

  This is the SSR twin of the reagent view contract: the SAME hiccup data that
  reagent renders live in the browser is rendered to an HTML string here for the
  static build (the kami-mangaka-reader dual-render pattern). It unifies the two
  near-identical emitters that previously lived in kami.mangaka.hiccup and
  slides.hiccup.

  Tag/attribute/style primitives and the RAWTEXT (script/style) breakout-guard
  are delegated to kotoba-lang/html (html.core) — the standalone substrate repo
  this implementation was originally extracted into (see that repo's README) —
  instead of duplicating them here, so fixes land once. The tree-walk itself
  stays local: html.core's own ->html additionally pretty-prints block-only
  element children (adds newlines/indentation), which would be a breaking
  output-format change for this namespace's many downstream consumers that
  depend on ->html's exact compact-string contract, so shitsuke.hiccup keeps
  its own compact (no added whitespace) walk and only reuses html.core's
  primitives + guard logic.

  Supported:
    [:tag attrs? & children]            vector node
    keyword tags with .class/#id sugar  :div.a.b#id
    attribute maps                      :class as string/vec, boolean attrs
    strings/numbers                     strings escaped, numbers str'd
    nil / seqs                          nil skipped, seqs flattened
    :key                                dropped (reagent-only; not HTML)
    [:hiccup/raw \"<svg/>\"]            trusted markup, not escaped
    <script>/<style> children           RAWTEXT semantics: emitted verbatim
                                         (not HTML-escaped), [:hiccup/raw ...]
                                         children unwrapped to their payload,
                                         and content containing a
                                         case-insensitive \"</tag\" breakout
                                         sequence is rejected."
  (:require [kotoba.lang.text :as str]
            [html.core :as html]
            [shitsuke.kotoba-oracle :as oracle]))

(def esc
  "Escape &, <, >, \" for safe inclusion in HTML text/attribute context.
  Delegates to kotoba-lang/html (html.core/esc)."
  html/esc)

(def ^:private void-tags html/void-tags)
(def ^:private raw-text-tags html/raw-text-tags)
(def ^:private parse-tag html/parse-tag)
(def ^:private class-str html/class-str)
(def ^:private render-attrs html/render-attrs)

(declare ->html)

(defn- raw-text-content
  "Flatten <script>/<style> children to their verbatim RAWTEXT payload,
  unwrapping [:hiccup/raw ...] children to their string content -- the
  long-standing convention wrapped-content callers (css.core/style-node,
  kototama/web, etc.) already rely on."
  [children]
  (apply str (map (fn [c]
                     (if (and (vector? c) (= :hiccup/raw (first c)))
                       (str (second c))
                       (str c)))
                   children)))

;; --- the RAWTEXT breakout decision, which this namespace no longer makes ----
;;
;; The rule lives in `kotoba/hiccup_core.kotoba` and RUNS from
;; `resources/shitsuke/oracle/hiccup-core.kir.edn`. What stays here is the half
;; that is not a decision: flattening children to a payload, windowing a long
;; one, and throwing. There is deliberately no `re-find` left in this
;; namespace — a security rule that exists twice is a security rule that can be
;; fixed once and stay broken in the copy that runs (ADR-2608112100).

(def ^:private rawtext-window
  "Characters per guest call.

  A guest string argument is capped at 65536 UTF-8 bytes and this is well under
  the always-safe character bound for that (`oracle/chars-that-always-fit`,
  21845), so a window never has to be encoded to know it will be accepted."
  16384)

(def ^:private rawtext-overlap
  "Characters each window shares with the previous one.

  A terminator that straddles a window boundary must still land wholly inside
  ONE window, so the overlap has to be at least one less than the longest run
  of input characters that can fold to `</tag`. No character case-folds to the
  empty string, so such a run is never longer than the terminator itself — 8
  characters for `</script`. 256 is that bound with room for a longer raw-text
  tag than HTML5 has ever had, and it costs nothing: it only shortens the
  stride."
  256)

(defn- breaks-out?
  "Ask the shipped core whether `content` breaks out of `<tag>`.

  Every call goes to the guest — there is no size below which this namespace
  answers for itself, because that would be the second implementation again.
  Long content is WINDOWED rather than declined: the guest decides each window,
  and a payload breaks out exactly when some window does."
  [tag content]
  (let [schema (oracle/only-param-type :hiccup-core 'rawtext-breakout?)
        ask (fn [chunk]
              (oracle/call :hiccup-core 'rawtext-breakout?
                           [(oracle/record-of schema {:tag tag :content chunk})]))
        n (count content)]
    (if (<= n rawtext-window)
      (ask content)
      (let [stride (- rawtext-window rawtext-overlap)]
        (loop [start 0]
          (cond
            (>= start n) false
            (ask (subs content start (min n (+ start rawtext-window)))) true
            :else (recur (+ start stride))))))))

(defn- assert-no-rawtext-breakout!
  "HTML5 RAWTEXT parsing: a <script>/<style> element terminates at the FIRST
  literal, case-insensitive \"</tag\" sequence in its content, regardless of
  surrounding quotes/strings/comments in the raw text -- emitting that
  sequence verbatim lets a raw payload break out of the element and inject
  markup after it (a script-context XSS vector).

  The predicate is `kotoba/hiccup_core.kotoba`; the throw is here. Kotoba's
  permanent `:explicit-errors` invariant means the guest cannot throw, and it
  should not: signalling is an effect and effects stay with the host."
  [tag content]
  (when (breaks-out? tag content)
    (throw (ex-info (str "shitsuke.hiccup: raw-text content for <" tag "> must not contain \"</" tag "\" "
                          "case-insensitively -- that sequence terminates the element early "
                          "per HTML5's RAWTEXT rule and can break out into injected markup")
                     {:tag tag}))))

(defn- render-node [node sb]
  (cond
    (nil? node) sb
    (string? node) (conj! sb (esc node))
    (number? node) (conj! sb (str node))
    (and (vector? node) (= :hiccup/raw (first node)))
    (conj! sb (str (second node)))
    ;; vector of nodes: [[:p "a"] [:p "b"]] — first child is itself a vector.
    (and (vector? node) (not (empty? node)) (vector? (first node)))
    (reduce (fn [s c] (render-node c s)) sb node)
    (vector? node)
    (let [[t & body] node
          [tag base] (parse-tag t)
          [attrs children] (if (map? (first body))
                             [(first body) (rest body)]
                             [{} body])
          ;; tag-sugar classes/id + attr :class merge (space-joined, both win)
          attrs (merge-with (fn [a b] (str (class-str a) " " (class-str b))) base attrs)
          ;; <textarea> special case: real HTML has no value attribute on
          ;; textarea — the pre-filled text is the element *content*. The live
          ;; (reagent/React) side of the dual-render contract needs :value as
          ;; an attribute (value-as-child is read only at mount), so the SSR
          ;; twin translates: render :value as escaped content, emit no value=.
          textarea-value (when (= tag "textarea") (:value attrs))
          attrs (cond-> attrs (= tag "textarea") (dissoc :value))
          ;; :key is the same shape of translation as :value above, in the
          ;; other direction. reagent/React requires it on elements produced
          ;; from a seq (without it, every such render logs a warning), so it
          ;; belongs in the shared hiccup. HTML has no `key` attribute, so the
          ;; SSR twin must drop it rather than emit `key="0"` — measured
          ;; 2026-08-04 in kobo's served console, where every output span
          ;; carried one.
          attrs (dissoc attrs :key)]
      (conj! sb (str "<" tag (render-attrs attrs) ">"))
      (when-not (contains? void-tags tag)
        (if (contains? raw-text-tags tag)
          (let [content (raw-text-content children)]
            (assert-no-rawtext-breakout! tag content)
            (conj! sb content))
          (do
            (when (some? textarea-value)
              (conj! sb (esc textarea-value)))
            (reduce (fn [s c] (render-node c s)) sb children)))
        (conj! sb (str "</" tag ">")))
      sb)
    (seq? node) (reduce (fn [s c] (render-node c s)) sb node)
    :else (conj! sb (esc node))))

(defn ->html
  "Render a hiccup node (or seq of nodes) to an HTML string."
  [node]
  (str/join (persistent! (render-node node (transient [])))))
