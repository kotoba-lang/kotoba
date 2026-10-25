(ns newsfeed.article
  "Feed item + its source → an article datom.

   Attribute names are `:news/*` and `:news.source/*`, taken verbatim from
   `cloud-itonami/news`'s `news.schema` — including its `art-<sha256hex(url)>`
   id convention. That A-layer's Worker is unreachable today (news.gftd.ai
   times out; see ADR-2608031500), but its schema is the workspace's existing
   vocabulary for this data and inventing a parallel one would mean a
   translation layer the day it or a successor comes back.

   The sha-256 is injected rather than required: a digest is host IO in nbb
   (`node:crypto`) and on the JVM (`MessageDigest`), and this namespace stays
   pure so the mapping is testable without either.

   Pure `.cljc`."
  (:require [kotoba.lang.text :as str]
            [newsfeed.instant :as instant]))

;; ── canonical url ────────────────────────────────────────────────────────────

(def ^:private tracking-params
  #{"utm_source" "utm_medium" "utm_campaign" "utm_term" "utm_content" "utm_id"
    "fbclid" "gclid" "mc_cid" "mc_eid" "ref" "ref_src" "s" "at_medium"
    "at_campaign" "cmp" "sh" "share" "__twitter_impression" "guccounter"})

(defn canonical-url
  "The dedupe key. Lower-cases scheme and host, drops the fragment and the
   tracking parameters, and keeps everything else byte-for-byte — path case and
   trailing slashes are load-bearing on enough sites that normalising them
   would merge two genuinely different articles under one id."
  [url]
  (when-let [u (some-> url str/trim not-empty)]
    (let [u (first (str/split u #"#" 2))
          [base query] (str/split u #"\?" 2)
          [scheme rest] (if-let [i (str/index-of base "://")]
                          [(str/lower (subs base 0 i)) (subs base (+ i 3))]
                          [nil base])
          [host path] (if scheme
                        (let [i (str/index-of rest "/")]
                          (if i [(str/lower (subs rest 0 i)) (subs rest i)]
                              [(str/lower rest) ""]))
                        [nil rest])
          kept (when query
                 (->> (str/split query #"&")
                      (remove str/blank?)
                      (remove #(tracking-params (str/lower (first (str/split % #"=" 2)))))
                      (str/join "&")
                      not-empty))]
      (str (when scheme (str scheme "://")) host path (when kept (str "?" kept))))))

(defn host
  "Registrable-ish host of a url, for provenance display. No PSL — the full
   host is the honest answer and `www.` is the only prefix worth dropping."
  [url]
  (when-let [u (some-> url str/trim not-empty)]
    (let [after (if-let [i (str/index-of u "://")] (subs u (+ i 3)) u)
          h (first (str/split after #"[/?]"))
          h (str/lower (or h ""))]
      (not-empty (if (str/starts-with? h "www.") (subs h 4) h)))))

;; ── mapping ──────────────────────────────────────────────────────────────────

(defn ->article
  "item (newsfeed.parse/item) + source (a `:news.source/*` map) + `sha256-hex`
   → a `:news/*` article datom, or nil when the item has no usable url.

   An item without a url is dropped rather than given a synthetic id: the id IS
   the url hash, so a synthesised one would make the same article re-enter the
   ledger under a new id on every run, and the dedupe that the whole ingest
   depends on would silently stop working."
  [item source sha256-hex]
  (when-let [url (canonical-url (:link item))]
    (let [title (some-> (:title item) str/trim not-empty)]
      (cond-> {:news/id         (str "art-" (sha256-hex url))
               :news/url        url
               :news/title      (or title url)
               :news/lang       (or (:news.source/lang source) "en")
               :news/sourceId   (:news.source/sourceId source)
               :news/sourceName (:news.source/name source)
               :news/sourceType (or (:news.source/sourceType source) "rss")
               :news/rightsPolicy (or (:news.source/rightsPolicy source) "unknown")
               :news/credibility  (or (:news.source/credibility source) 0.5)
               :news/authority    (host url)
               :source/dataset  "newsfeed"}
        ;; A snapshot of the catalog's editorial fields at ingest time. Reads
        ;; go through newsfeed.catalog/enrich, which re-joins the CURRENT
        ;; catalog over these — an append-only ledger cannot be revised, and
        ;; these fields get revised.
        (:news.source/class source) (assoc :news/sourceClass (:news.source/class source))
        (:summary item)     (assoc :news/summary (:summary item))
        (:published item)   (assoc :news/publishedAt (:published item))
        (:published-raw item) (assoc :news/pubDate (:published-raw item))
        (:guid item)        (assoc :news/guid (:guid item))
        (seq (:categories item)) (assoc :news/categories (pr-str (:categories item)))
        (seq (:authors item))    (assoc :news/author (str/join ", " (:authors item)))))))

;; ── dedupe ───────────────────────────────────────────────────────────────────

(defn dedupe-articles
  "Collapse to one article per `:news/id`, keeping the first seen.

   First rather than best on purpose: sources are ordered by credibility in the
   catalog, so first-seen is the most credible telling of a story that several
   feeds carry, and the rule stays stable across runs. Aggregators that republish
   a vendor post therefore lose to the vendor's own feed."
  [articles]
  (->> articles
       (remove nil?)
       (reduce (fn [{:keys [seen out] :as acc} a]
                 (if (seen (:news/id a))
                   acc
                   {:seen (conj seen (:news/id a)) :out (conj out a)}))
               {:seen #{} :out []})
       :out))

(defn fresh?
  "Was this article published within `days` of `now-iso`?

   An article with no parseable date is NOT fresh. Feeds that omit dates would
   otherwise dominate every window forever, and a story that cannot be placed
   in time cannot be called news."
  [article now-iso days]
  (when-let [d (instant/days-between (:news/publishedAt article) now-iso)]
    (and (>= d 0) (<= d days))))
