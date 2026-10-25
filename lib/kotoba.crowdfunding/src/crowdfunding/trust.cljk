(ns crowdfunding.trust
  "Campaign review — what must be checked before a campaign may take
  money, and where the checking stops.

  This namespace has one function that could be dangerous and is
  deliberately not written: there is no `approve`. `review` produces
  FINDINGS. A finding is an observation with a rule id, a severity and a
  citation; it is not a verdict. Deciding that a campaign may launch is a
  named human's act, recorded by the reviewing actor's governor — the same
  boundary `marketplace.crossborder` keeps for customs disputes.

  The reason is specific to this domain rather than general caution. A
  crowdfunding review is a judgement about whether a stranger can build a
  thing they have not built yet. No rule set decides that. What a rule set
  can do is guarantee that the reviewer was shown the things that most
  often turn out to matter afterwards — an undisclosed risk, a
  prototype-versus-render ambiguity, a goal too large for the creator's
  verification level, a category that is not a project at all. That is
  what these rules are: a floor under human attention, not a substitute
  for it.

  Verification evidence comes from `kotoba-lang/ekyc` and
  `kotoba-lang/aml` outcomes, passed IN. This namespace never performs a
  check, and never treats a self-reported status as evidence — the
  'ground truth, not self-report' rule the whole fleet's governors share.

  Pure: no clock, no network, no randomness."
  (:require [kotoba.lang.text :as str]
            [crowdfunding.campaign :as campaign]
            [crowdfunding.reward :as reward]))

;; ───────────────────────────── policy data ─────────────────────────────

(def prohibited-categories
  "Categories that are not rewards-crowdfunding projects at all. Financial
  instruments are absent from this domain by construction: a reward is a
  thing, and the moment a 'reward' is a share of future revenue the
  transaction is a security and belongs in `kotoba-lang/securities` under
  a completely different regime. Listing it as merely prohibited here,
  rather than routing it, would invite someone to fix it by editing this
  set."
  #{:equity :revenue-share :loan :lottery :prize-draw
    :medical-claim :weapon :drug :recalled-good :counterfeit
    :charity-solicitation})

(def restricted-categories
  "Not prohibited, but never auto-eligible: each requires a specific
  disclosure or licence a human must see.

  Keys are drawn from the SAME taxonomy `crowdfunding.discovery/categories`
  uses. A restriction keyed on a category no campaign can be filed under is
  a rule that never fires, and is worse than no rule because it reads like
  coverage."
  {:food       :requires-food-safety-disclosure
   :fashion    :requires-materials-and-cosmetics-disclosure
   :technology :requires-radio-compliance-disclosure
   :games      :requires-toy-safety-disclosure
   :design     :requires-product-safety-disclosure})

(def required-disclosures
  "The disclosures every campaign owes its backers regardless of category.

  `:risks` is separately validated by `campaign/campaign-errors`; it is
  repeated here because a campaign can pass structural validation with a
  one-word risks section, and this rule is about substance."
  #{:risks :production-stage :fulfilment-experience :who-is-making-it})

(def ^:private min-risks-chars
  "A risks section shorter than this is a formality, not a disclosure."
  120)

(def verification-floors
  "How much verification a goal size requires, ascending. A creator asking
  for a small amount from people who probably know them is a different
  risk from one asking for a large amount from strangers, and requiring
  the same evidence for both either blocks the first or under-checks the
  second.

  Thresholds are in minor units and are DATA — a deployment states its own
  numbers rather than inheriting these."
  [{:floor/up-to-minor 500000    :floor/requires #{:email :payment-method}}
   {:floor/up-to-minor 5000000   :floor/requires #{:email :payment-method :identity-document}}
   {:floor/up-to-minor nil       :floor/requires #{:email :payment-method :identity-document
                                                   :address-proof :sanctions-screen}}])

(defn floor-for
  "The verification floor a goal of this size falls under."
  [goal-minor]
  (or (first (filter #(let [u (:floor/up-to-minor %)]
                        (or (nil? u) (<= goal-minor u)))
                     verification-floors))
      (last verification-floors)))

;; ───────────────────────────── findings ─────────────────────────────

(defn finding
  "One observation. `:severity` is `:blocking` (a human must resolve it
  before launch), `:advisory` (a human should see it) or `:info`."
  [{:keys [rule severity detail cites]}]
  {:finding/rule     rule
   :finding/severity severity
   :finding/detail   detail
   :finding/cites    (vec (or cites []))})

(defn- disclosure-findings [c disclosures]
  (concat
   (keep (fn [d]
           (when-not (contains? (set disclosures) d)
             (finding {:rule :missing-disclosure :severity :blocking
                       :detail d :cites [:required-disclosures]})))
         required-disclosures)
   (when (and (:campaign/risks c)
              (< (count (str (:campaign/risks c))) min-risks-chars))
     [(finding {:rule :risks-section-too-thin :severity :blocking
                :detail (str (count (str (:campaign/risks c))) "<" min-risks-chars " chars")
                :cites [:campaign/risks]})])))

(defn- category-findings [c]
  (let [cat (:campaign/category c)]
    (concat
     (when (contains? prohibited-categories cat)
       [(finding {:rule :prohibited-category :severity :blocking
                  :detail cat :cites [:prohibited-categories]})])
     (when-let [req (get restricted-categories cat)]
       [(finding {:rule :restricted-category :severity :advisory
                  :detail req :cites [:restricted-categories]})]))))

(defn- verification-findings [c evidence]
  (let [floor    (floor-for (:campaign/goal-minor c 0))
        required (:floor/requires floor)
        held     (set (keep (fn [[k v]] (when (true? v) k)) evidence))
        missing  (remove held required)]
    (concat
     (map (fn [m]
            (finding {:rule :insufficient-verification :severity :blocking
                      :detail m
                      :cites [:verification-floors (:floor/up-to-minor floor)]}))
          missing)
     ;; An AML outcome is never inferred from its absence. `:not-run` is a
     ;; finding, not a pass — the distinction `kotoba-lang/aml` itself draws.
     (when (contains? required :sanctions-screen)
       (case (:aml/status evidence)
         :clear  nil
         :review [(finding {:rule :aml-review-pending :severity :blocking
                            :detail :review :cites [:aml/status]})]
         :hold   [(finding {:rule :aml-hold :severity :blocking
                            :detail :hold :cites [:aml/status]})]
         [(finding {:rule :aml-not-run :severity :blocking
                    :detail (:aml/status evidence :absent) :cites [:aml/status]})])))))

(defn- reward-findings [c rewards]
  (concat
   (when (empty? (remove :reward/add-on? rewards))
     [(finding {:rule :no-reward-tiers :severity :blocking
                :detail :a-rewards-campaign-needs-a-reward})])
   (mapcat (fn [r]
             (map (fn [e] (finding {:rule (:reward.error/code e) :severity :blocking
                                    :detail (:reward/id r)
                                    :cites [:reward (:reward/id r)]}))
                  (reward/reward-errors r)))
           rewards)
   ;; A tier promising delivery before the campaign even closes is either
   ;; a typo or an existing product being sold as a project.
   (keep (fn [r]
           (when (and (:campaign/deadline c) (:reward/estimated-delivery r)
                      (neg? (compare (str (:reward/estimated-delivery r))
                                     (str (:campaign/deadline c)))))
             (finding {:rule :delivery-before-deadline :severity :advisory
                       :detail (:reward/id r)
                       :cites [:reward/estimated-delivery]})))
         rewards)))

(defn- structural-findings [c]
  (map (fn [e] (finding {:rule (:campaign.error/code e) :severity :blocking
                         :detail (:campaign.error/detail e)
                         :cites [:campaign]}))
       (campaign/campaign-errors c)))

(defn- presentation-findings [{:keys [prototype-exists? imagery]}]
  (concat
   (when (false? prototype-exists?)
     [(finding {:rule :no-working-prototype :severity :advisory
                :detail :backers-must-be-told :cites [:prototype-exists?]})])
   ;; Renders presented as photographs is the single most reliably
   ;; regretted thing in this domain. It is advisory rather than blocking
   ;; because only a human can look at an image and say which it is.
   (when (and (false? prototype-exists?) (contains? (set imagery) :photoreal-render))
     [(finding {:rule :render-may-read-as-product :severity :advisory
                :detail :label-renders-as-renders :cites [:imagery]})])))

;; ───────────────────────────── review ─────────────────────────────

(defn review
  "Review a campaign for launch. Returns findings and counts — NEVER a
  decision.

  `evidence` carries verification outcomes established elsewhere
  (`{:email true :identity-document true :aml/status :clear}`), `context`
  carries what the creator asserted about their project. Both are inputs
  because this namespace does not fetch, and does not get to decide what
  counts as proof.

  `:review/human-required?` is unconditionally true. Not 'true when there
  are blocking findings' — a clean review is still a decision to let a
  stranger take money from the public, and that decision has an author."
  [{:keys [campaign rewards disclosures evidence context]}]
  (let [fs (vec (concat (structural-findings campaign)
                        (category-findings campaign)
                        (disclosure-findings campaign disclosures)
                        (verification-findings campaign evidence)
                        (reward-findings campaign rewards)
                        (presentation-findings context)))
        by-sev (frequencies (map :finding/severity fs))]
    {:review/campaign        (:campaign/id campaign)
     :review/findings        fs
     :review/blocking-count  (get by-sev :blocking 0)
     :review/advisory-count  (get by-sev :advisory 0)
     :review/clean?          (zero? (get by-sev :blocking 0))
     :review/verification-floor (floor-for (:campaign/goal-minor campaign 0))
     :review/human-required? true
     :review/adjudicated?    false}))

(defn launch-blocked-by
  "The blocking findings only, in a stable order — what a creator is told
  to fix. Sorted by rule then detail so the same review reads the same
  way twice."
  [r]
  (->> (:review/findings r)
       (filter #(= :blocking (:finding/severity %)))
       (sort-by (juxt (comp str :finding/rule) (comp str :finding/detail)))
       vec))

(defn decision
  "Record a human's launch decision over a review. This does not review
  anything; it attaches an author to an outcome, and refuses (nil) without
  one, or when a blocking finding is being waived without an explicit
  waiver list.

  Waiving a blocking finding is ALLOWED — a reviewer who cannot override a
  rule will eventually route around the system — but each waiver must name
  the rule. A blanket override is not expressible here."
  [r {:keys [outcome decided-by decided-at rationale waived]}]
  (let [waived (set waived)
        unwaived (remove #(contains? waived (:finding/rule %)) (launch-blocked-by r))]
    (when (and (contains? #{:approved :rejected :changes-requested} outcome)
               (not (str/blank? (str decided-by)))
               (or (not= :approved outcome) (empty? unwaived)))
      {:decision/outcome    outcome
       :decision/campaign   (:review/campaign r)
       :decision/decided-by decided-by
       :decision/decided-at decided-at
       :decision/rationale  rationale
       :decision/waived     (vec (sort (map str waived)))
       :decision/human?     true})))
