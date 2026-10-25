(ns crowdfunding.discovery
  "Discovery — which campaigns a visitor is shown, and why.

  On a crowdfunding platform, placement IS funding. A campaign on the
  front page raises money a campaign on page nine does not, which makes
  the ranking function the platform's most consequential and most opaque
  power. `marketplace.catalog/buy-box` established the answer this fleet
  uses: make the ranking key a pure function of observable facts, return
  the exclusions with reasons alongside the ranking, and have no paid
  placement to hide.

  So `rank` here takes no 'boost' parameter, has no seller-supplied
  weight, and returns `:ranking/exclusions` with a reason per excluded
  campaign. A creator who was not shown can reproduce the result and see
  why. `:ranking/key-fields` names the key's components on the result
  itself, so a future change to the ranking is visible in the output
  rather than only in a diff.

  Pure: no clock (the caller passes `now`), no network, no randomness —
  a randomised carousel would make the whole guarantee unverifiable."
  (:require [crowdfunding.campaign :as campaign]
            [crowdfunding.funding :as funding]))

(def categories
  "The project taxonomy. A closed set, because 'other' is where
  unclassifiable-and-therefore-unreviewable campaigns collect."
  #{:art :comics :crafts :dance :design :fashion :film :food :games
    :journalism :music :photography :publishing :technology :theater})

(defn category-valid? [c] (contains? categories c))

;; ───────────────────────────── card ─────────────────────────────

(defn card
  "The projection a campaign is shown as. Derived from the campaign and
  its tally rather than stored, so a card can never drift from the numbers
  it summarises — the drift that turns a funding bar into a lie."
  [c t now]
  (let [pct (funding/percent-funded c t)]
    {:card/campaign      (:campaign/id c)
     :card/title         (:campaign/title c)
     :card/creator       (:campaign/creator c)
     :card/category      (:campaign/category c)
     :card/currency      (:campaign/currency c)
     :card/goal-minor    (:campaign/goal-minor c)
     :card/pledged-minor (:funding/pledged-minor t 0)
     :card/percent-bps   pct
     :card/backers       (:funding/backers t 0)
     :card/state         (:campaign/state c)
     :card/deadline      (:campaign/deadline c)
     :card/closed?       (campaign/deadline-passed? c now)
     :card/funding-model (:campaign/funding-model c)}))

;; ───────────────────────────── eligibility ─────────────────────────────

(def listable-states
  "Only a live campaign is discoverable. A draft is not public, a
  suspended one must not be promoted while under review, and a finished
  one belongs in an archive view rather than in the funding feed."
  #{:live})

(defn- exclusion [c reason] {:card/campaign (:campaign/id c) :reason reason})

(defn eligible
  "Split entries (`{:c campaign :t tally :card card}`) into
  `[listable excluded]`. Every exclusion carries a reason; a campaign that
  vanishes without one is indistinguishable from a shadow-ban.

  A campaign with no pledges yet is NOT excluded — excluding it would make
  the feed a rich-get-richer loop in which nothing new can ever start,
  which on a crowdfunding platform is the difference between a market and
  a leaderboard."
  [entries]
  (reduce (fn [[in out] {:keys [c card] :as e}]
            (cond
              (not (contains? listable-states (:campaign/state c)))
              [in (conj out (exclusion c :not-live))]

              (:card/closed? card)
              [in (conj out (exclusion c :window-closed))]

              (not (category-valid? (:campaign/category c)))
              [in (conj out (exclusion c :unknown-category))]

              :else [(conj in e) out]))
          [[] []]
          entries))

;; ───────────────────────────── ranking ─────────────────────────────

(def sorts
  "The orderings a visitor may ask for. Each is a total order over
  observable fields — there is no `:recommended`, because a ranking whose
  key cannot be named is a ranking that cannot be audited."
  #{:ending-soon :newly-launched :most-funded :closest-to-goal :most-backers})

(defn- descending [f] (fn [a b] (compare (f b) (f a))))

(defn- order
  "Apply a sort to entries.

  Implemented as a STABLE sort layered over an id-ordered base rather than
  as one composite key. That is what makes `:campaign/id` the tie-break for
  every ordering, including the descending ones — a composite key cannot
  hold 'this field descending, that field ascending' without inventing a
  numeric proxy for a timestamp, and an invented proxy is exactly where an
  unaccountable thumb hides."
  [entries by]
  (let [by-id (sort-by #(str (:campaign/id (:c %))) entries)]
    (case by
      :ending-soon     (sort-by #(str (:campaign/deadline (:c %))) by-id)
      :newly-launched  (sort (descending #(str (:campaign/launched-at (:c %)))) by-id)
      :most-funded     (sort-by #(- (:funding/pledged-minor (:t %) 0)) by-id)
      :closest-to-goal (sort-by #(- (or (funding/percent-funded (:c %) (:t %)) 0)) by-id)
      :most-backers    (sort-by #(- (:funding/backers (:t %) 0)) by-id)
      by-id)))

(defn rank
  "Rank campaigns for a feed.

  `entries` is a seq of `{:c campaign :t tally}`. Returns the ranking, the
  exclusions with reasons, and the key fields the order was computed from.

  Ties break on `:campaign/id` — a total order, so the same inputs produce
  the same feed for every visitor. Two campaigns with identical observable
  facts are not silently ordered by whichever the database returned first,
  which is where an unaccountable thumb most easily rests."
  [entries {:keys [sort category now limit]
            :or   {sort :ending-soon}}]
  (let [with-cards (map (fn [e] (assoc e :card (card (:c e) (:t e) now))) entries)
        scoped     (if category
                     (filter #(= category (:campaign/category (:c %))) with-cards)
                     with-cards)
        [listable excluded] (eligible scoped)
        ordered    (mapv :card (order listable sort))]
    {:ranking/sort        sort
     :ranking/category    category
     :ranking/cards       (if limit (vec (take limit ordered)) ordered)
     :ranking/truncated?  (boolean (and limit (> (count ordered) limit)))
     :ranking/exclusions  (vec (sort-by (comp str :card/campaign) excluded))
     :ranking/key-fields  (case sort
                            :ending-soon     [:campaign/deadline :campaign/id]
                            :newly-launched  [:campaign/launched-at :campaign/id]
                            :most-funded     [:funding/pledged-minor :campaign/id]
                            :closest-to-goal [:funding/percent-bps :campaign/id]
                            :most-backers    [:funding/backers :campaign/id]
                            [:campaign/id])
     :ranking/paid-placement? false}))

;; ───────────────────────────── search ─────────────────────────────

(defn search-doc
  "The projection handed to `kotoba-lang/search` for indexing. Only public
  campaign text — a backer list is never an index field, because an index
  is a query surface and 'who backed what' is not a public fact."
  [c]
  {:doc/id       (:campaign/id c)
   :doc/title    (:campaign/title c)
   :doc/story    (:campaign/story c)
   :doc/category (:campaign/category c)
   :doc/creator  (:campaign/creator c)
   :doc/state    (:campaign/state c)})
