(ns newsfeed.score
  "Rank the shared article pool for one channel.

   The catalog deliberately lets channels share feeds — The Register publishes
   one all-sections feed and both channels read it — so the gate that decides
   what belongs to a channel lives here rather than in the source list. Without
   it a storage channel leads with a story about Windows activation errors.

   Three signals, all cheap and all inspectable:

     keywords   weighted terms, counted in the title at double weight because a
                headline is written to say what the article is about
     url-hints  substrings of the article url, positive and negative. The
                strongest available signal on a section-organised publisher:
                `/storage/` in the path is an editor's own classification,
                which beats any guess made from prose.
     source     the catalog's editorial credibility, as a small tiebreak

   Recency is applied last and only as a tiebreak, never as a gate — the
   freshness window is a separate, explicit decision in `newsfeed.article`.

   The result carries `:score/matched`, so a ranking can be explained rather
   than trusted. Pure `.cljc`."
  (:require [kotoba.lang.text :as str]))

(defn- haystack [article]
  (str/lower (str (:news/title article) " " (:news/summary article))))

(defn- title-hay [article]
  (str/lower (str (:news/title article))))

(defn keyword-hits
  "→ [{:term :weight :in} …] for every catalog term present.

   A term is matched as a substring, not a token: the catalog carries phrases
   (\"object storage\", \"flash attention\") that tokenising would split, and
   the false positives substring matching invites (\"ai\" inside \"chain\")
   are what the phrase-heavy high-weight tiers and `:min-score` exist to
   absorb. Terms are matched against title and summary separately so a
   headline hit can count double."
  [article keywords]
  (let [hay (haystack article)
        ttl (title-hay article)]
    (->> keywords
         (mapcat (fn [[w terms]]
                   (keep (fn [t]
                           (let [t (str/lower t)]
                             (cond
                               (str/includes? ttl t) {:term t :weight (* 2 w) :in :title}
                               (str/includes? hay t) {:term t :weight w :in :summary}
                               :else nil)))
                         terms)))
         vec)))

(defn url-hint-score
  "Sum of the hints whose substring appears in the article url."
  [article hints]
  (let [u (str/lower (str (:news/url article)))]
    (reduce-kv (fn [acc frag w] (if (str/includes? u (str/lower frag)) (+ acc w) acc))
               0 (or hints {}))))

(defn score
  "article + channel → the article with `:score/*` attached.

   Keyword weight is capped: an article that says \"gpu\" eleven times is not
   eleven times more relevant, and without a cap a listicle outranks a
   substantive piece every time. The cap is per-term-tier via `distinct`
   on the term, plus an overall ceiling."
  [article channel]
  (let [hits (keyword-hits article (:channel/keywords channel))
        ;; one count per distinct term — repetition is not relevance
        kw (->> hits (group-by :term) vals (map #(apply max (map :weight %))) (reduce + 0))
        kw (min kw 18)
        url (url-hint-score article (:channel/url-hints channel))
        cred (* 2 (double (or (:news/credibility article) 0.5)))
        bias (double (get (:channel/source-bias channel) (:news/sourceId article) 0))
        total (+ kw url cred bias)]
    (assoc article
           ;; Every :score/* is in integer hundredths of a point. One unit
           ;; throughout means components can be summed and compared without
           ;; float equality, and without remembering which fields were scaled.
           :score/keywords (Math/round (* 100.0 kw))
           :score/url (Math/round (* 100.0 url))
           :score/bias (Math/round (* 100.0 bias))
           :score/source (Math/round (* 100.0 cred))
           :score/total (Math/round (* 100.0 total))
           :score/matched (vec (distinct (map :term hits))))))

(defn rank
  "Score every article for the channel, drop those under `:channel/min-score`,
   and order by score then recency.

   Returns ALL scored articles under `:rejected` as well. A ranking that
   silently discards is impossible to tune — the first real ingest needed to
   see what scored 3 to know whether the threshold was right."
  [articles channel]
  (let [scored (map #(score % channel) articles)
        floor (* 100 (or (:channel/min-score channel) 0))
        ;; descending score, then descending date. Written out rather than as a
        ;; `sort-by` key because the date is a string and cannot be negated.
        cmp (fn [a b]
              (let [c (compare (:score/total b) (:score/total a))]
                (if (zero? c)
                  (compare (str (:news/publishedAt b)) (str (:news/publishedAt a)))
                  c)))]
    {:selected (vec (sort cmp (filter #(>= (:score/total %) floor) scored)))
     :rejected (vec (sort cmp (remove #(>= (:score/total %) floor) scored)))}))
