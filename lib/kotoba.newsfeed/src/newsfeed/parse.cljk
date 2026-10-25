(ns newsfeed.parse
  "Feed document → a uniform item sequence, across the three syndication
   dialects that are actually served: RSS 2.0, Atom 1.0 and RDF/RSS 1.0.

   The dialects disagree about where items live (`channel/item` vs `feed/entry`
   vs `RDF/item`) and about how a link is spelled (element text vs an `href`
   attribute on one of several `<link rel=…>`). Everything downstream —
   dedupe, scoring, digesting — works on the uniform shape produced here, so
   adding a fourth dialect touches this namespace alone.

   Pure `.cljc`."
  (:require [kotoba.lang.text :as str]
            [newsfeed.xml :as xml]
            [newsfeed.instant :as instant]))

(defn strip-tags
  "Remove HTML markup from a feed's description/summary. Feeds routinely carry
   escaped HTML there, and a headline-and-summary consumer wants the words.
   Block-ish tags become a space so `<p>a</p><p>b</p>` does not read as `ab`."
  [s]
  (when s
    (-> s
        (str/replace #"(?is)<(script|style)\b[^>]*>.*?</\1>" " ")
        (str/replace #"(?i)<(br|/p|/div|/li|/h[1-6]|/tr)\b[^>]*>" " ")
        (str/replace #"<[^>]*>" "")
        xml/decode-entities
        (str/replace #"\s+" " ")
        str/trim)))

(defn- clip
  "Trim to at most n characters on a word boundary, with an ellipsis."
  [s n]
  (when-let [s (some-> s not-empty)]
    (if (<= (count s) n)
      s
      (let [cut (subs s 0 n)
            sp  (str/last-index-of cut " ")]
        (str (str/trimr (if (and sp (> sp (quot n 2))) (subs cut 0 sp) cut)) "…")))))

;; ── dialect detection ────────────────────────────────────────────────────────

(defn dialect
  "→ :rss | :atom | :rdf | nil"
  [root]
  (case (xml/local-name (:tag root))
    "rss" :rss
    "feed" :atom
    "rdf" :rdf
    nil))

(defn- item-elements [root]
  (case (dialect root)
    :rss  (mapcat #(xml/elements % "item") (xml/elements root "channel"))
    :rdf  (xml/elements root "item")
    :atom (xml/elements root "entry")
    nil))

;; ── field extraction ─────────────────────────────────────────────────────────

(defn- atom-link
  "Atom puts the article URL on a <link> attribute. Prefer rel=alternate; a
   link with no rel defaults to alternate per RFC 4287. Never return an
   enclosure or a self link — those are the feed's own address, and using one
   would give every entry in the feed the same URL, collapsing them all to a
   single article under a URL-derived id."
  [el]
  (let [links (xml/elements el "link")
        rel   (fn [l] (or (get-in l [:attrs "rel"]) "alternate"))
        href  (fn [l] (some-> (get-in l [:attrs "href"]) str/trim not-empty))]
    (or (some href (filter #(= "alternate" (rel %)) links))
        (some href (remove #(#{"self" "enclosure" "edit" "replies"} (rel %)) links)))))

(defn- item-link [el]
  (or (some-> (xml/child-text el "link") str/trim not-empty (as-> t (when-not (str/starts-with? t "<") t))
              )
      (atom-link el)
      ;; RSS 2.0 permits a permalink guid as the only address
      (let [g (xml/element el "guid")]
        (when (not= "false" (get-in g [:attrs "ispermalink"]))
          (some-> (xml/text g) str/trim not-empty
                  (as-> t (when (str/starts-with? t "http") t)))))))

(defn- item-published [el]
  (some #(xml/child-text el %) ["pubdate" "published" "date" "updated" "modified" "created"]))

(defn- item-authors [el]
  (->> (concat (map xml/text (xml/elements el "author"))
               (map xml/text (xml/elements el "creator")))
       (map #(-> % strip-tags str/trim))
       (remove str/blank?)
       distinct
       vec))

(defn- item-categories [el]
  (->> (xml/elements el "category")
       (map #(or (get-in % [:attrs "term"]) (xml/text %)))
       (map #(some-> % str/trim))
       (remove str/blank?)
       distinct
       vec))

(defn- item-summary [el]
  (or (some-> (xml/child-text el "description") strip-tags not-empty)
      (some-> (xml/child-text el "summary") strip-tags not-empty)
      (some-> (xml/child-text el "encoded") strip-tags not-empty)
      (some-> (xml/child-text el "content") strip-tags not-empty)))

(defn item
  "One feed item element → the uniform shape. `:published` is normalised UTC
   when the raw value parsed; `:published-raw` is always kept so a date this
   parser cannot read is visible rather than absent."
  [el]
  (let [raw-date (item-published el)
        title (some-> (xml/child-text el "title") strip-tags not-empty)]
    {:title         title
     :link          (item-link el)
     :guid          (or (xml/child-text el "guid") (xml/child-text el "id"))
     :published     (instant/normalize raw-date)
     :published-raw raw-date
     :summary       (clip (item-summary el) 600)
     :authors       (item-authors el)
     :categories    (item-categories el)}))

(defn feed
  "Parsed feed document string → {:dialect :title :link :items [...]}.
   Items with neither a title nor a link are dropped: they carry nothing a
   reader or a dedupe key could use, and are usually a template artefact."
  [xml-string]
  (when-let [root (xml/parse xml-string)]
    (when-let [d (dialect root)]
      (let [head (or (xml/element root "channel") root)]
        {:dialect d
         :title   (some-> (xml/child-text head "title") strip-tags not-empty)
         :link    (or (some-> (xml/child-text head "link") str/trim not-empty
                              (as-> t (when (str/starts-with? t "http") t)))
                      (atom-link head))
         :items   (->> (item-elements root)
                       (map item)
                       (filter #(or (:title %) (:link %)))
                       vec)}))))
