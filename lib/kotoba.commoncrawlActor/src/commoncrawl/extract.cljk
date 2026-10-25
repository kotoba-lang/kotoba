(ns commoncrawl.extract
  "Minimal, honest, regex-based HTML -> title/text extraction. NOT a real
  HTML parser (no DOM, no encoding sniffing beyond a handful of named
  entities) — this is a best-effort fallback so the actor has SOME title/
  text to hand `commoncrawl.llm`/`web.ingest` even before the LLM extraction
  step runs, in the same pragmatic style as `kenchi.commoncrawl`'s regex-
  based JSON-LD price extraction (no HTML-parsing library dependency taken
  for a small, bounded extraction need). Pure string transforms, no IO —
  portable .cljc, runs identically under :clj and :cljs/nbb."
  (:require [kotoba.lang.text :as str]))

(def ^:private max-text-chars
  "Matches net-kotobase web.ingest's own `text` field cap
  (kotobase.web/max-text-chars) — truncate here so a giant page never
  produces a payload the edge would reject anyway."
  200000)

(defn- decode-entities
  "A small, fixed table of the entities actually common in crawled HTML —
  not a full HTML5 named-entity table (that would need a real parser/large
  data table this ns deliberately doesn't take on)."
  [s]
  (-> s
      (str/replace "&nbsp;" " ")
      (str/replace "&amp;" "&")
      (str/replace "&lt;" "<")
      (str/replace "&gt;" ">")
      (str/replace "&quot;" "\"")
      (str/replace "&#39;" "'")
      (str/replace "&apos;" "'")))

(defn title-of
  "First `<title>...</title>` in `html`, entity-decoded and trimmed. nil
  when absent/blank."
  [html]
  (when (string? html)
    (when-let [m (re-find #"(?is)<title[^>]*>(.*?)</title>" html)]
      (let [t (-> (second m) decode-entities str/trim (str/replace #"\s+" " "))]
        (when (seq t) t)))))

(defn strip-html
  "`html` -> plain text: drop `<script>`/`<style>` blocks (their contents
  are never page text), drop every remaining tag, entity-decode, collapse
  runs of whitespace, and cap at `max-text-chars`. \"\" (never nil) on
  non-string input — a caller always gets a string it can hand straight to
  web.ingest's `text` field."
  [html]
  (if-not (string? html)
    ""
    (let [no-script (-> html
                        (str/replace #"(?is)<script[^>]*>.*?</script>" " ")
                        (str/replace #"(?is)<style[^>]*>.*?</style>" " ")
                        (str/replace #"(?is)<!--.*?-->" " "))
          no-tags (str/replace no-script #"(?s)<[^>]+>" " ")
          decoded (decode-entities no-tags)
          collapsed (-> decoded (str/replace #"[ \t\f\v]+" " ") (str/replace #"\n\s*\n+" "\n") str/trim)]
      (subs collapsed 0 (min (count collapsed) max-text-chars)))))

(defn extracted-page
  "html -> {:title :text}, both ready to hand to `commoncrawl.llm`'s
  extraction prompt and, as a fallback, straight to web.ingest if the LLM
  step is ever skipped."
  [html]
  {:title (or (title-of html) "")
   :text (strip-html html)})
