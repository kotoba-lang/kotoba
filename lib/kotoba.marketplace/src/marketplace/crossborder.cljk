(ns marketplace.crossborder
  "Cross-border landed cost, HS classification PROPOSALS, and dispute
  intake — the layer that lets a marketplace ship across a border
  without any automated party ever claiming to have decided a customs
  or dispute question.

  ## What this namespace refuses to do

  It ships NO duty-rate table. Tariff schedules are jurisdiction-,
  product-, treaty- and date-specific, they change constantly, and a
  wrong rate is a financially consequential fabrication — a buyer
  quoted a landed cost that under-states duty pays the difference at
  the border. So every rate is an INPUT. When a rate for a
  (destination, HS heading) pair is absent, `landed-cost` returns
  `:landed/computable? false` with the missing input named, rather than
  a plausible-looking number. This is the same discipline
  `kotoba-lang/dynamics` states for pool-tap interventions
  (`:uncomputable-until-measured`) and `pricing-oracle` states for
  price bands (never predict from a prior, only from comparables
  actually present in the input).

  Likewise it never CLASSIFIES. `hs-proposal` builds a candidate HS
  heading with its basis and confidence, for a human to accept or
  reject. Customs classification is a legal act; an actor that recorded
  itself as having classified goods would be asserting an authority it
  does not have. `cloud-itonami-marketplace-crossborder`'s governor
  makes 'finalizing a customs declaration' a permanent scope exclusion,
  the same shape ISIC 4791 uses for fraud determinations.

  ## Disputes

  Disputes are INTAKE ONLY (ADR-2607264000 D5). This namespace records
  that a dispute exists, what evidence each side filed, and what a
  HUMAN decided — it contains no function that decides one. The fleet
  holds the invariant that no actor adjudicates a dispute, and this
  namespace does not break it.

  Pure: no clock, no network, no randomness."
  (:require [kotoba.lang.text :as str]))

;; ───────────────────────────── HS classification ─────────────────────────────

(def ^:private hs6-re #"^\d{6}$")

(defn valid-hs6?
  "True for a 6-digit HS subheading — the internationally harmonised
  part. Digits beyond 6 are national extensions and are deliberately
  not validated here, because their length and meaning vary by country
  and asserting a single rule would be wrong somewhere."
  [code]
  (boolean (and (string? code) (re-matches hs6-re code))))

(def classification-bases
  "How an HS candidate was arrived at. Recorded so a reviewer can weigh
  the proposal — a heading copied from a sibling product is a weaker
  basis than one a customs broker supplied."
  #{:seller-declared :broker-supplied :prior-ruling :sibling-product :operator-default})

(defn hs-proposal
  "A CANDIDATE HS subheading for a product — never a classification.

  `confidence` is the proposer's own stated confidence in [0,1]; the
  actor's governor applies its confidence floor to it exactly as every
  other governor in this fleet does. `:proposal/adjudicated? false` is
  stamped on the record so a downstream consumer cannot mistake it for
  a determination."
  [{:keys [product hs6 basis confidence rationale proposed-by]}]
  {:proposal/product      (str product)
   :proposal/hs6          hs6
   :proposal/basis        basis
   :proposal/confidence   confidence
   :proposal/rationale    rationale
   :proposal/proposed-by  proposed-by
   :proposal/adjudicated? false
   :proposal/non-adjudicating true})

(defn hs-proposal-errors [p]
  (vec
   (concat
    (when-not (valid-hs6? (:proposal/hs6 p))
      [{:crossborder.error/code :invalid-hs6 :crossborder.error/detail "6 桁の HS subheading"}])
    (when-not (contains? classification-bases (:proposal/basis p))
      [{:crossborder.error/code :unknown-basis :crossborder.error/detail (pr-str (:proposal/basis p))}])
    (when-not (and (number? (:proposal/confidence p))
                   (<= 0 (:proposal/confidence p) 1))
      [{:crossborder.error/code :invalid-confidence :crossborder.error/detail "0..1"}])
    (when (str/blank? (str (:proposal/proposed-by p)))
      [{:crossborder.error/code :missing-proposer}])
    ;; A proposal that claims to have been adjudicated is asserting the
    ;; exact authority this layer is defined not to have.
    (when (true? (:proposal/adjudicated? p))
      [{:crossborder.error/code :adjudicating-proposal}]))))

;; ───────────────────────────── duty / tax inputs ─────────────────────────────

(defn duty-rate
  "One operator-supplied rate row. `ad-valorem-bps` is duty as basis
  points of customs value; `vat-bps` is import consumption tax.

  `source` and `as-of` are REQUIRED by `duty-rate-errors` — an
  unattributed, undated rate is exactly the kind of number that is
  wrong later and cannot be audited. This matches the workspace rule
  that computed figures must rest on real data with a date and a
  citation."
  [{:keys [destination hs6 ad-valorem-bps vat-bps source as-of de-minimis-minor]}]
  {:rate/destination      (some-> destination str/upper)
   :rate/hs6              hs6
   :rate/ad-valorem-bps   ad-valorem-bps
   :rate/vat-bps          vat-bps
   :rate/de-minimis-minor de-minimis-minor
   :rate/source           source
   :rate/as-of            as-of})

(defn duty-rate-errors [r]
  (vec
   (concat
    (when-not (re-matches #"^[A-Z]{3}$" (str (:rate/destination r)))
      [{:crossborder.error/code :invalid-destination :crossborder.error/detail "ISO-3166 alpha-3"}])
    (when-not (valid-hs6? (:rate/hs6 r))
      [{:crossborder.error/code :invalid-hs6}])
    (when-not (and (integer? (:rate/ad-valorem-bps r)) (not (neg? (:rate/ad-valorem-bps r))))
      [{:crossborder.error/code :invalid-ad-valorem-bps}])
    (when-not (and (integer? (:rate/vat-bps r)) (not (neg? (:rate/vat-bps r))))
      [{:crossborder.error/code :invalid-vat-bps}])
    (when (str/blank? (str (:rate/source r)))
      [{:crossborder.error/code :missing-rate-source
        :crossborder.error/detail "出典の無い税率は監査できない"}])
    (when (str/blank? (str (:rate/as-of r)))
      [{:crossborder.error/code :missing-rate-date
        :crossborder.error/detail "適用日の無い税率は監査できない"}]))))

(defn rate-table
  "Index rate rows by [destination hs6]. Throws on an unattributed or
  malformed row rather than admitting it — a bad row in a rate table
  silently mis-quotes every order that hits it."
  [rows]
  (reduce (fn [t r]
            (if-let [errs (seq (duty-rate-errors r))]
              (throw (ex-info "invalid duty rate row"
                              {:crossborder/errors errs :rate/hs6 (:rate/hs6 r)}))
              (assoc t [(:rate/destination r) (:rate/hs6 r)] r)))
          {}
          rows))

;; ───────────────────────────── landed cost ─────────────────────────────

(defn landed-cost
  "Estimate what the buyer actually pays to receive goods across a
  border.

    goods + shipping + insurance  = customs value (CIF-shaped)
    duty  = customs value × ad-valorem-bps / 10000
    vat   = (customs value + duty) × vat-bps / 10000
    total = customs value + duty + vat

  All integer minor units; VAT is computed on the duty-inclusive base,
  which is the common (not universal) rule — `:landed/vat-base` records
  which base was used so a reviewer can see the assumption instead of
  having to infer it.

  Returns `:landed/computable? false` and names the missing input when
  no rate row exists for [destination, hs6], INSTEAD of guessing. A
  de-minimis threshold, when supplied on the rate row, zeroes duty and
  VAT and is recorded in `:landed/de-minimis-applied?`.

  This is an ESTIMATE, stamped `:landed/estimate? true`. The border
  decides the real number."
  [{:keys [goods-minor shipping-minor insurance-minor destination hs6 currency]
    :or   {shipping-minor 0 insurance-minor 0}}
   rates]
  (let [dest   (some-> destination str/upper)
        row    (get rates [dest hs6])
        cif    (+ goods-minor shipping-minor insurance-minor)]
    (if-not row
      {:landed/computable? false
       :landed/reason      :no-rate-for-destination-and-hs6
       :landed/missing     {:destination dest :hs6 hs6}
       :landed/customs-value-minor cif
       :landed/currency    currency
       :landed/estimate?   true}
      (let [de-min   (:rate/de-minimis-minor row)
            under?   (boolean (and de-min (< cif de-min)))
            duty     (if under? 0 (quot (* cif (:rate/ad-valorem-bps row)) 10000))
            vat-base (+ cif duty)
            vat      (if under? 0 (quot (* vat-base (:rate/vat-bps row)) 10000))]
        {:landed/computable?  true
         :landed/currency     currency
         :landed/goods-minor  goods-minor
         :landed/shipping-minor shipping-minor
         :landed/insurance-minor insurance-minor
         :landed/customs-value-minor cif
         :landed/duty-minor   duty
         :landed/vat-minor    vat
         :landed/vat-base     :duty-inclusive
         :landed/total-minor  (+ cif duty vat)
         :landed/de-minimis-applied? under?
         :landed/rate-source  (:rate/source row)
         :landed/rate-as-of   (:rate/as-of row)
         :landed/estimate?    true
         :landed/adjudicated? false}))))

;; ───────────────────────────── disputes ─────────────────────────────

(def dispute-reasons
  "Why a buyer opened a dispute. A closed set so reporting is
  comparable across instances."
  #{:not-received :not-as-described :damaged :counterfeit-suspected
    :unauthorised-charge :customs-cost-unexpected})

(def dispute-states
  "Dispute lifecycle. Like escrow, `:under-review` has no automatic
  exit — `record-decision` requires a named human."
  #{:opened :evidence-requested :under-review :resolved :withdrawn})

(def dispute-transitions
  {:opened             #{:evidence-requested :under-review :withdrawn}
   :evidence-requested #{:under-review :withdrawn}
   :under-review       #{:resolved :withdrawn}
   :resolved           #{}
   :withdrawn          #{}})

(defn dispute
  "Open a dispute record. INTAKE ONLY — creating this asserts that
  someone complained, never that they were right."
  [{:keys [id order buyer seller reason narrative opened-at]}]
  {:dispute/id        id
   :dispute/order     order
   :dispute/buyer     buyer
   :dispute/seller    seller
   :dispute/reason    reason
   :dispute/narrative narrative
   :dispute/opened-at opened-at
   :dispute/state     :opened
   :dispute/evidence  []
   :dispute/adjudicated-by-actor? false
   :dispute/non-adjudicating true})

(defn dispute-errors [d]
  (vec
   (concat
    (when (str/blank? (str (:dispute/id d)))
      [{:crossborder.error/code :missing-dispute-id}])
    (when (str/blank? (str (:dispute/order d)))
      [{:crossborder.error/code :missing-order}])
    (when-not (contains? dispute-reasons (:dispute/reason d))
      [{:crossborder.error/code :unknown-dispute-reason
        :crossborder.error/detail (pr-str (:dispute/reason d))}])
    (when-not (contains? dispute-states (:dispute/state d))
      [{:crossborder.error/code :invalid-dispute-state}])
    (when (true? (:dispute/adjudicated-by-actor? d))
      [{:crossborder.error/code :actor-adjudicated-dispute
        :crossborder.error/detail "actor が紛争を裁定したと主張するレコードは恒久的に禁止"}]))))

(defn add-evidence
  "Append one party's evidence. Append-only: evidence is never replaced
  or removed, so the record of what each side actually filed cannot be
  edited after the fact."
  [d {:keys [party kind ref filed-at note]}]
  (update d :dispute/evidence conj
          {:evidence/party  party
           :evidence/kind   kind
           :evidence/ref    ref
           :evidence/filed-at filed-at
           :evidence/note   note}))

(defn advance-dispute
  "Move a dispute along its lifecycle when the table allows; nil
  otherwise."
  [d to]
  (when (contains? (get dispute-transitions (:dispute/state d) #{}) to)
    (assoc d :dispute/state to)))

(defn record-decision
  "Record that a HUMAN resolved the dispute. Returns nil unless the
  dispute is `:under-review`, the outcome is known, and a human is
  named.

  This function RECORDS a decision; it never MAKES one. There is
  deliberately no counterpart that computes an outcome from the
  evidence — adding one would break the fleet-wide invariant that no
  actor adjudicates (ADR-2607264000 D5, ISIC 4791's original
  scope-exclusion)."
  [d {:keys [outcome decided-by decided-at rationale]}]
  (when (and (= :under-review (:dispute/state d))
             (contains? #{:buyer-favoured :seller-favoured :split :no-fault} outcome)
             (not (str/blank? (str decided-by))))
    (assoc d
           :dispute/state :resolved
           :dispute/decision {:decision/outcome    outcome
                              :decision/decided-by decided-by
                              :decision/decided-at decided-at
                              :decision/rationale  rationale
                              :decision/human?     true})))
