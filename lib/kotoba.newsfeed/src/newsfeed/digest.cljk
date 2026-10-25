(ns newsfeed.digest
  "Ranked articles → the brief a video episode is produced from.

   This is the last stop before the LLM. Everything here is deterministic, so
   the same ledger and the same day produce the same brief, and a bad episode
   can be traced to either the brief (data) or the storyboard (the model) —
   never to an ambiguous mix of both.

   The brief carries its citations as data. `newscaster`'s EditorialGovernor
   enforces `cites ⊆ ingested`, and a brief whose citations are article ids
   from the ledger satisfies that by construction rather than by the model
   being careful.

   Pure `.cljc`."
  (:require [kotoba.lang.text :as str]
            [newsfeed.article :as article]
            [newsfeed.catalog :as catalog]
            [newsfeed.score :as score]))

;; ── near-duplicate clustering ────────────────────────────────────────────────

(def ^:private stop-words
  #{"a" "an" "the" "and" "or" "of" "to" "in" "on" "for" "with" "at" "by" "from"
    "as" "is" "are" "was" "were" "be" "it" "its" "that" "this" "new" "now"
    "has" "have" "will" "can" "how" "why" "what" "you" "your" "we" "our"})

(defn title-tokens
  "Content words of a title, lower-cased, punctuation dropped. Used only for
   near-duplicate detection, so precision matters more than recall."
  [title]
  (->> (-> (str title) str/lower (str/replace #"[^a-z0-9 ]" " ") (str/split #"\s+"))
       (remove str/blank?)
       (remove stop-words)
       (remove #(< (count %) 3))
       set))

(defn similar?
  "Jaccard overlap of two title token sets over `threshold`.

   Titles rather than bodies because most feeds here ship no body at all
   (measured: Blocks & Files and Hugging Face send empty descriptions), and a
   rule that only works on the feeds with summaries would cluster
   inconsistently depending on which source carried the story."
  [a b threshold]
  (let [ta (title-tokens a) tb (title-tokens b)]
    (and (seq ta) (seq tb)
         (let [inter (count (filter ta tb))
               union (count (into ta tb))]
           (>= (/ (double inter) union) threshold)))))

(def default-threshold
  "0.45, chosen by sweeping the real 261-article week of 2026-08-03.

     0.55  0 merges           — the initial guess; merged nothing at all
     0.45  1 merge, 0 false   — Kioxia liquid-cooled SSD, Tom's Hardware +
                                StorageReview. The only true cross-outlet
                                duplicate in the corpus.
     0.35  2 merges, 1 false  — merged two unrelated long-context papers
     0.30  3 merges, 2 false  — also merged two different Dell laptop reviews
     0.25  6 merges, 4 true / 2 false

   0.25 finds three more genuine duplicates (an AM5 firmware launch, a MinIO
   announcement, a Nutanix/Dell integration) and that is tempting. It is
   refused because the errors are not symmetric: under-merging shows one story
   twice, which a viewer sees and forgives, while over-merging DELETES a story
   by filing it as corroboration of an unrelated one, where nobody sees it
   again. Redundancy is visible; suppression is not."
  0.45)

(defn cluster
  "Group articles that tell the same story. The highest-scoring member leads
   and the rest become corroboration, which is what a news brief wants: three
   outlets covering one launch is one story with three citations, not three
   stories.

   Two articles from the SAME source never merge. A publisher does not run the
   same story twice, so a high title overlap within one outlet means related
   coverage, not duplication — measured: two Dell laptop reviews from one site,
   and two different Kioxia product launches. This holds the line structurally
   even if someone later lowers the threshold."
  ([articles] (cluster articles default-threshold))
  ([articles threshold]
   (reduce (fn [clusters a]
             (if-let [i (first (keep-indexed
                                (fn [i c]
                                  (let [l (:lead c)]
                                    (when (and (not= (:news/sourceId l) (:news/sourceId a))
                                               (similar? (:news/title l) (:news/title a) threshold))
                                      i)))
                                clusters))]
               (update-in clusters [i :also] conj a)
               (conj clusters {:lead a :also []})))
           []
           articles)))

;; ── editorial spread ─────────────────────────────────────────────────────────

(defn take-spread
  "Take `n` clusters in rank order, but no more than the channel allows from
   one source or one source class.

   Ranking alone does not make a running order. Measured on the first real
   ingest: without this the GPU/AI channel led with four arXiv preprints (their
   abstracts are keyword-dense by construction) and the storage channel took
   five of six items from a single trade outlet. Neither is a false positive —
   every item was on-topic and correctly scored — which is exactly why the
   scorer is the wrong place to fix it. A digest of one publisher is a press
   review, not a news bulletin.

   A skipped cluster is not discarded: it stays available as corroboration and
   as a citation. `:class` falls back to the source id, so a catalog entry that
   declares no class is capped on its own."
  [clusters n {:keys [max-per-source max-per-class class-of]
               :or {max-per-source 2 max-per-class {}}}]
  (let [limit (fn [cls] (get max-per-class cls (get max-per-class :default 2)))]
    (loop [[c & more] clusters, out [], by-src {}, by-cls {}]
      (cond
        (or (nil? c) (>= (count out) n)) out
        :else
        (let [src (:news/sourceId (:lead c))
              cls (or (class-of (:lead c)) src)]
          (if (and (< (get by-src src 0) max-per-source)
                   (< (get by-cls cls 0) (limit cls)))
            (recur more (conj out c) (update by-src src (fnil inc 0)) (update by-cls cls (fnil inc 0)))
            (recur more out by-src by-cls)))))))

;; ── the brief ────────────────────────────────────────────────────────────────

(defn- citation [a]
  (cond-> {:cite/id (:news/id a)
           :cite/title (:news/title a)
           :cite/url (:news/url a)
           :cite/source (:news/sourceName a)
           :cite/rights (:news/rightsPolicy a)}
    (:news/publishedAt a) (assoc :cite/published (:news/publishedAt a))))

(defn topic-line
  "The one-line topic handed to the storyboard actor.

   Deterministic on purpose: the lead headline, trimmed. Letting a model write
   this would put a second, unaudited generative step upstream of the one the
   pipeline already accounts for, and the headline is what the citation says
   anyway — inventing a punchier phrasing here is how a video ends up claiming
   something no cited source does."
  [lead]
  (-> (str (:news/title lead)) (str/replace #"\s+" " ") str/trim))

(defn brief
  "articles (already in the ledger) + channel + now → the episode brief.

   `:brief/status` is `:ok` or `:no-story`. A day with nothing above threshold
   is a real outcome and gets said plainly — the alternative, lowering the bar
   until something qualifies, is how a channel starts publishing filler."
  [articles channel now-iso & [{:keys [top] :or {top 6}}]]
  (let [window (or (:channel/window-days channel) 7)
        pool (catalog/for-channel articles channel)
        fresh (filter #(article/fresh? % now-iso window) pool)
        {:keys [selected rejected]} (score/rank fresh channel)
        clusters (cluster selected)
        chosen (vec (take-spread clusters top
                                 {:max-per-source (or (:channel/max-per-source channel) 2)
                                  :max-per-class (or (:channel/max-per-class channel) {})
                                  :class-of :news/sourceClass}))
        lead (:lead (first chosen))]
    (cond-> {:brief/channel (:channel/id channel)
             :brief/site (:channel/site channel)
             :brief/generated-at now-iso
             :brief/window-days window
             :brief/pool {:total (count articles)
                          :declared-sources (count pool)
                          :in-window (count fresh)
                          :above-threshold (count selected)
                          :clusters (count clusters)}
             :brief/status (if lead :ok :no-story)}
      lead
      (assoc :brief/topic (topic-line lead)
             :brief/lead (citation lead)
             :brief/items
             (vec (for [{:keys [lead also]} chosen]
                    {:item/title (:news/title lead)
                     :item/url (:news/url lead)
                     :item/source (:news/sourceName lead)
                     :item/published (:news/publishedAt lead)
                     :item/summary (:news/summary lead)
                     :item/score (:score/total lead)
                     :item/matched (:score/matched lead)
                     :item/corroboration (mapv citation also)}))
             :brief/citations
             (vec (distinct (mapcat (fn [{:keys [lead also]}] (map citation (cons lead also))) chosen))))

      ;; What just missed the cut, so a threshold can be tuned from evidence.
      true
      (assoc :brief/near-misses
             (vec (for [a (take 5 rejected)]
                    {:item/title (:news/title a)
                     :item/score (:score/total a)
                     :item/matched (:score/matched a)}))))))
