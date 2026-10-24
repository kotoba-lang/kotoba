(ns toshokan-patents.sources.google-patents
  "Google Patents bibliographic source — worldwide patent metadata from
  `patents.google.com/patent/<id>/en`.

  ## Why this source (ADR-2607251552)

  USPTO ODP is mid-migration (search.patentsview.org sunset 2026-03) and EPO OPS
  needs OAuth registration. Google Patents pages are public, server-rendered HTML
  carrying Dublin Core (`DC.title` / `DC.date` / `DC.contributor` /
  `DC.relation scheme=references`) and `citation_patent_number`, and they cover
  the WORLDWIDE space (US/EP/JP/WO/CN/KR/…) in one source — effectively a free,
  no-auth mirror of the EPO DOCDB bibliographic set.

  `DC.relation scheme=references` is why this source is worth more than a lookup
  table: each page names the patents it cites, so a consumer can walk the
  citation graph and grow its own seed set.

  ## Discipline (metadata-only, not a scraper)

  Bibliographic fields extracted from the page's OWN structured metadata —
  never the claims or specification text, never a paywall or bot-detection
  bypass. Identifying User-Agent, sequential, polite rate. The rate and the
  residency are the CONSUMER's to set; this namespace does one request when
  asked and has no loop of its own.

  ## Pure vs. effectful

  `parse-html` and everything above it are PURE and identical on every platform
  — the same HTML gives the same field-map on the JVM and on nbb, which is what
  makes a parity test possible. Only `fetch-page` / `lookup` touch the network,
  and they are reader-conditional: **the JVM leg is synchronous and returns the
  value, the ClojureScript leg returns a Promise.** That asymmetry is deliberate
  and not hidden behind a fake uniform API."
  (:require [kotoba.lang.text :as str]
            [toshokan-patents.quad :as quad])
  #?(:clj (:import (java.net URI)
                   (java.net.http HttpClient HttpClient$Redirect HttpRequest
                                  HttpResponse$BodyHandlers)
                   (java.time Duration))))

(def ^:const page-endpoint "https://patents.google.com/patent/")
(def ^:const source-key :google-patents)

(def ^:const ua
  (str "toshokan-patents-harvester/0.2 (kotoba-lang/toshokan-patents; "
       "worldwide patent bibliographic metadata preservation; "
       "+https://github.com/kotoba-lang/toshokan-patents)"))

;; ── HTML meta-tag extraction (regex; no cheerio/jsoup dependency) ────────────
;;
;; `(?i)` is written at the START of every pattern on purpose: ClojureScript's
;; `re-pattern` lifts a leading `(?flags)` group into real RegExp flags, so this
;; is the one inline-flag form that means the same thing on both platforms.
;; An inline `(?i)` anywhere else would compile on the JVM and silently fail to
;; be case-insensitive on JS.

(def ^:private meta-tag-re #"(?i)<meta\b[^>]*>")

(defn- attr-value
  "The value of attribute `attr` inside a single tag string, or nil."
  [tag attr]
  (second (re-find (re-pattern (str "(?i)" attr "=[\"']([^\"']*)[\"']")) tag)))

(defn- meta-tags [html] (re-seq meta-tag-re html))

(defn meta-by-name
  "All `content` values of `<meta name=NAME content=...>`, in any attribute order."
  [html name]
  (->> (meta-tags html)
       (filter #(= name (attr-value % "name")))
       (keep #(attr-value % "content"))
       distinct))

(defn meta-by-name-scheme
  "All `content` values of `<meta name=NAME ... scheme=SCHEME ...>`, any order.

  Google Patents distinguishes filing date from grant date, and inventor from
  assignee, ONLY by the `scheme` attribute — the `name` is `DC.date` /
  `DC.contributor` for both. Reading `name` alone conflates them."
  [html name scheme]
  (->> (meta-tags html)
       (filter #(and (= name (attr-value % "name"))
                     (= scheme (attr-value % "scheme"))))
       (keep #(attr-value % "content"))
       distinct))

(defn meta-first [html name] (first (meta-by-name html name)))

;; ── patent-id helpers ────────────────────────────────────────────────────────

(defn normalize-patent-id [id]
  (-> id str/trim str/upper (str/replace #"\s+" "")))

(defn page-url [id]
  (str page-endpoint (normalize-patent-id id) "/en"))

(defn country-code
  "The 2-letter jurisdiction prefix of a patent id, or nil."
  [id]
  (second (re-find #"^([A-Z]{2})" (normalize-patent-id id))))

(defn cited-patent-ids
  "Cited patents from `DC.relation scheme=references`.

  Google writes them colon-separated (`JP:2004224907:A`); the citation graph and
  the journal both key on the compact form (`JP2004224907A`). Values that do not
  start with a country code are dropped — the same meta name also carries
  non-patent references."
  [html]
  (->> (meta-by-name-scheme html "DC.relation" "references")
       (map #(str/replace % ":" ""))
       (filter #(re-find #"^[A-Z]{2}\d" %))
       distinct
       vec))

;; ── parse (PURE) ─────────────────────────────────────────────────────────────

(defn parse-html
  "Google Patents page HTML → field-map. PURE.

  nil fields are dropped downstream by `quad/record->quads`, so a page missing a
  given meta tag costs nothing and never writes a null into the journal."
  [html id]
  (let [pid (normalize-patent-id id)]
    {:entity (str "gp:" pid)
     :source-url (page-url id)
     :patent-id pid
     :country (country-code pid)
     :title (or (meta-first html "DC.title")
                (second (re-find #"(?i)<title>\s*([^<]+?)\s*-\s*Google Patents" html)))
     :number (meta-first html "citation_patent_number")
     :app-number (meta-first html "citation_patent_application_number")
     :filed-at (first (meta-by-name-scheme html "DC.date" "dateSubmitted"))
     :granted-at (first (meta-by-name-scheme html "DC.date" "issue"))
     :inventors (vec (meta-by-name-scheme html "DC.contributor" "inventor"))
     :assignees (vec (meta-by-name-scheme html "DC.contributor" "assignee"))
     :citations (cited-patent-ids html)}))

(defn ->quads
  "field-map → journal quads. PURE — `tx` and `retrieved-at` are supplied by the
  caller, so a harvest is reproducible and carries no hidden clock."
  [tx retrieved-at m]
  (quad/record->quads
   (:entity m) tx
   {:patent/source source-key
    :patent/source-url (:source-url m)
    :patent/title (:title m)
    :patent/number (:number m)
    :patent/patent-id (:patent-id m)
    :patent/country (:country m)
    :patent/application-number (:app-number m)
    :patent/filed-at (:filed-at m)
    :patent/granted-at (:granted-at m)
    :patent/inventor (:inventors m)
    :patent/applicant (:assignees m)
    :patent/cites (:citations m)          ; cardinality-many → citation graph
    :patent/retrieved-at retrieved-at}))

;; ── network leg (reader-conditional; SYNC on JVM, Promise on cljs) ───────────

#?(:clj
   (def ^:private ^HttpClient client
     (delay (-> (HttpClient/newBuilder)
                (.connectTimeout (Duration/ofSeconds 20))
                (.followRedirects HttpClient$Redirect/NORMAL)
                (.build)))))

#?(:clj
   (defn fetch-page
     "SYNC (JVM): GET the patent page. Returns the HTML string, or nil on 404
     (a dead id is a normal outcome of walking a citation graph, not an error).
     Any other non-2xx throws."
     [patent-id]
     (let [req (-> (HttpRequest/newBuilder (URI/create (page-url patent-id)))
                   (.header "User-Agent" ua)
                   (.timeout (Duration/ofSeconds 30))
                   (.GET)
                   (.build))
           resp (.send @client req (HttpResponse$BodyHandlers/ofString))
           status (.statusCode resp)]
       (cond
         (= 404 status) nil
         (<= 200 status 299) (.body resp)
         :else (throw (ex-info (str "Google Patents HTTP " status " for " patent-id)
                               {:status status :patent-id patent-id})))))

   :cljs
   (defn fetch-page
     "ASYNC (cljs): returns a Promise of the HTML string, or nil on 404."
     [patent-id]
     (-> (js/fetch (page-url patent-id) #js {:headers #js {"User-Agent" ua}})
         (.then (fn [^js r]
                  (cond
                    (.-ok r) (.text r)
                    (= 404 (.-status r)) nil
                    :else (throw (ex-info (str "Google Patents HTTP " (.-status r)
                                               " for " patent-id)
                                          {:status (.-status r) :patent-id patent-id}))))))))

#?(:clj
   (defn lookup
     "SYNC (JVM): one patent id → field-map, or nil if the page does not exist."
     [patent-id]
     (when-let [html (fetch-page patent-id)]
       (parse-html html patent-id)))

   :cljs
   (defn lookup
     "ASYNC (cljs): Promise of a field-map, or nil if the page does not exist."
     [patent-id]
     (-> (fetch-page patent-id)
         (.then (fn [html] (when html (parse-html html patent-id)))))))
