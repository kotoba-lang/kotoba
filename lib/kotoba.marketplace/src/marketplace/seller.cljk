(ns marketplace.seller
  "Portable seller credential — the federated-marketplace answer to
  'who is allowed to sell here, and can that survive leaving here?'

  A seller credential is a self-contained record asserting that a seller
  cleared onboarding at some ISSUING instance. It carries the evidence
  *references* (eKYC session completion + AML screening status) that the
  issuer relied on, so a RECEIVING instance can make its own admission
  decision without re-running the whole identity check and without
  calling back to the issuer. That is what makes this a protocol rather
  than a platform: an issuer cannot hold a seller hostage, because the
  credential is verifiable outside it (ADR-2607264000 D1 invariant 1).

  Composition, not reinvention:
    - `ekyc.core/completion` decides whether the identity session is
      evidentially complete (kotoba-lang/ekyc, modelling the ten
      non-face-to-face methods of 犯収法施行規則 6条1項).
    - `aml.core/status` reduces screening results to
      :clear / :review / :hold / :not-run (kotoba-lang/aml).

  NON-ADJUDICATING. Both upstream libraries stamp `:non-adjudicating
  true` on their records and this namespace preserves that discipline:
  nothing here *decides* that a person is who they claim to be, or that
  they are sanction-free. It decides only the much narrower question
  'given evidence the issuer already gathered, is this credential
  structurally admissible?' — and any answer other than a clean
  `:admissible` routes to a human. The onboarding actor's governor
  treats finalizing a KYC determination as a permanent scope exclusion.

  Pure: no clock, no network, no randomness. Every time-dependent
  function takes `now` (an ISO-8601 UTC string) from the caller, the
  same discipline `kotoba.omise` uses for opening hours — lexicographic
  compare on ISO-8601 UTC is chronological compare."
  (:require [aml.core :as aml]
            [kotoba.lang.text :as str]
            [ekyc.core :as ekyc]))

;; ───────────────────────────── vocabulary ─────────────────────────────

(def kinds
  "What legal kind of party is selling. Drives which eKYC method set
  applies upstream (natural-person vs corporate sub-items)."
  #{:individual :company})

(def statuses
  "Credential lifecycle. `:issued` is the only state that can trade;
  everything else is a refusal with a different reason."
  #{:draft :issued :suspended :revoked :expired})

(def admission-outcomes
  "The receiving instance's decision about a credential.

   :admissible — structurally clean; the actor may still escalate.
   :review     — usable only after a human looks at it.
   :refused    — structurally inadmissible; no human override at the
                 library level (the governor decides whether its own
                 hard-block applies)."
  #{:admissible :review :refused})

(def ^:private required-checks-for
  "The eKYC check set a seller credential must carry per party kind.
  A SUBSET of `ekyc.model/checks` — deliberately not the full set,
  because requiring e.g. `:liveness` of a corporate applicant is
  meaningless. Issuers may require MORE (a stricter jurisdiction);
  they may never require less, and `credential-errors` enforces that
  floor rather than trusting the issuer's own claim."
  {:individual #{:document-authenticity :liveness :sanctions}
   :company    #{:document-authenticity :sanctions}})

(defn required-checks
  "The minimum eKYC check set for `kind`, or nil for an unknown kind."
  [kind]
  (get required-checks-for kind))

;; ───────────────────────────── ids ─────────────────────────────

(def ^:private seller-id-re
  ;; `merchant.<apex>` and `did:web:*` are already accepted party ids in
  ;; kotoba.product-party/valid-party-id?, so a seller id that reaches
  ;; the catalog layer can be used as a party id directly with no
  ;; translation table. Keep these two shapes in sync with that lib.
  #"^(merchant\.[a-z0-9][a-z0-9.-]*|did:web:[a-z0-9][a-z0-9.:%-]*)$")

(defn valid-seller-id?
  "True for a seller id this protocol can carry end-to-end into the
  catalog layer (`merchant.<apex>` or `did:web:<host>`)."
  [id]
  (boolean (and (string? id) (re-matches seller-id-re id))))

(def ^:private instance-id-re
  ;; The issuing/receiving marketplace instance. Same did:web shape —
  ;; an instance is itself a web-resolvable party.
  #"^did:web:[a-z0-9][a-z0-9.:%-]*$")

(defn valid-instance-id?
  "True for a marketplace-instance id (`did:web:<host>`)."
  [id]
  (boolean (and (string? id) (re-matches instance-id-re id))))

;; ───────────────────────────── evidence summary ─────────────────────────────

(defn evidence-summary
  "Reduce an eKYC session + its append-only evidence log, and an AML
  result set, to the compact summary a credential carries.

  Delegates entirely: `ekyc.core/completion` handles supersession (a
  later re-screen overrides an earlier :verified for the same check),
  `aml.core/status` handles level precedence (:deny dominates). This
  function adds no judgement of its own — it only pairs the two and
  records which checks were actually verified, so a receiving instance
  can compare that set against its OWN floor rather than trusting the
  issuer's floor."
  [{:keys [ekyc-session ekyc-evidence aml-results]}]
  (let [completion (ekyc/completion ekyc-session (or ekyc-evidence []))]
    {:evidence/ekyc-id         (:ekyc/id completion)
     :evidence/ekyc-complete?  (:ekyc/complete? completion)
     :evidence/verified-checks (:ekyc/verified-checks completion)
     :evidence/missing-checks  (:ekyc/missing-checks completion)
     :evidence/aml-status      (aml/status (or aml-results []))
     :evidence/non-adjudicating true}))

;; ───────────────────────────── credential ─────────────────────────────

(defn credential
  "Build a seller credential.

  Required: `:id` (seller id), `:kind`, `:legal-name`, `:country`
  (ISO-3166 alpha-3), `:issuer` (instance did), `:issued-at` and
  `:expires-at` (ISO-8601 UTC), and `:evidence` (from
  `evidence-summary`).

  A credential is DATA, not an assertion of truth — building one never
  validates it. Call `credential-errors` (or `admission`) to find out
  whether it is usable. This split is deliberate: it lets an actor
  construct a candidate credential from a draft proposal and hand the
  *whole thing* to its governor, so the governor censors a complete
  record rather than a half-built one."
  [{:keys [id kind legal-name country issuer issued-at expires-at
           evidence status payout-bound? note]
    :or   {status :draft payout-bound? false}}]
  (cond-> {:seller/id            (str id)
           :seller/kind          kind
           :seller/legal-name    legal-name
           :seller/country       (some-> country str/upper)
           :seller/issuer        issuer
           :seller/issued-at     issued-at
           :seller/expires-at    expires-at
           :seller/status        status
           :seller/evidence      evidence
           ;; A seller may hold a valid identity credential and still be
           ;; unable to receive money — the settlement layer binds a
           ;; payout destination separately, and `sellable?` requires
           ;; both. This mirrors ISIC 4791's own
           ;; `:payment-processor-linked?` gate, which HARD-holds a
           ;; verified-but-unlinked merchant exactly like an unverified
           ;; one.
           :seller/payout-bound? (boolean payout-bound?)
           :seller/non-adjudicating true}
    note (assoc :seller/note note)))

(defn- missing-field-errors [c]
  (for [[k label] [[:seller/legal-name "legal-name"]
                   [:seller/country    "country"]
                   [:seller/issuer     "issuer"]
                   [:seller/issued-at  "issued-at"]
                   [:seller/expires-at "expires-at"]]
        :when (str/blank? (str (get c k)))]
    {:seller.error/code :missing-field :seller.error/field label}))

(defn credential-errors
  "Structural errors on a credential, `[]` when structurally sound.

  This is the ISSUER-INDEPENDENT floor: it re-derives the required
  check set from `:seller/kind` and compares it against the evidence's
  own `:evidence/verified-checks`, rather than believing an
  `:evidence/ekyc-complete?` flag the issuer computed against whatever
  floor the issuer chose. An issuer that required fewer checks than
  this protocol's floor produces a credential that fails HERE, at the
  receiving instance — which is the entire point of making the
  credential externally verifiable."
  [c]
  (let [kind      (:seller/kind c)
        needed    (required-checks kind)
        ;; Accept the summary either inlined on the credential or nested
        ;; under :seller/evidence — an actor building a proposal often
        ;; has only the flat summary in hand.
        verified  (set (or (:evidence/verified-checks c)
                           (get-in c [:seller/evidence :evidence/verified-checks])))
        aml-status (or (:evidence/aml-status c)
                       (get-in c [:seller/evidence :evidence/aml-status]))]
    (vec
     (concat
      (when-not (valid-seller-id? (:seller/id c))
        [{:seller.error/code :invalid-seller-id
          :seller.error/detail "merchant.<apex> または did:web:<host> のみ"}])
      (when-not (contains? kinds kind)
        [{:seller.error/code :invalid-kind :seller.error/detail (pr-str kind)}])
      (when-not (contains? statuses (:seller/status c))
        [{:seller.error/code :invalid-status :seller.error/detail (pr-str (:seller/status c))}])
      (when-not (valid-instance-id? (:seller/issuer c))
        [{:seller.error/code :invalid-issuer :seller.error/detail "did:web:<host> のみ"}])
      (missing-field-errors c)
      (when (and (:seller/country c)
                 (not (re-matches #"^[A-Z]{3}$" (str (:seller/country c)))))
        [{:seller.error/code :invalid-country :seller.error/detail "ISO-3166 alpha-3"}])
      ;; Evidence floor — re-derived, never trusted from the issuer.
      (when (and needed (seq (remove verified needed)))
        [{:seller.error/code :insufficient-evidence
          :seller.error/detail (str "未検証の必須チェック: "
                                    (pr-str (set (remove verified needed))))}])
      (when (= :not-run aml-status)
        [{:seller.error/code :aml-not-run}])
      (when (= :hold aml-status)
        [{:seller.error/code :aml-hold}])
      ;; An issuer that omitted the non-adjudicating stamp is asserting
      ;; something this protocol never permits an automated party to
      ;; assert.
      (when (false? (:seller/non-adjudicating c))
        [{:seller.error/code :adjudicating-credential}])))))

;; ───────────────────────────── lifecycle ─────────────────────────────

(defn expired?
  "True when `now` (ISO-8601 UTC) is at or past the credential's
  `:seller/expires-at`. Caller supplies the clock.

  Expiry is inclusive at the boundary: a credential whose `expires-at`
  equals `now` is already expired, so a stale credential can never be
  used for exactly one more transaction on the boundary tick."
  [c now]
  (boolean (and (:seller/expires-at c) now
                (not (neg? (compare (str now) (str (:seller/expires-at c))))))))

(defn active?
  "True when the credential is `:issued` and not yet expired at `now`.
  Defined in terms of `expired?` so the boundary rule cannot drift
  between the two."
  [c now]
  (and (= :issued (:seller/status c))
       (not (expired? c now))))

;; ───────────────────────────── admission ─────────────────────────────

(defn admission
  "The receiving instance's decision about a credential at time `now`.

  Returns {:admission/outcome kw :admission/reasons [..]}.

  Three-valued on purpose. `:refused` is a structural fact (bad id,
  missing evidence, AML hold, revoked, expired) that no human approval
  at this layer can wave through. `:review` means the credential is
  structurally fine but something about it needs eyes — an AML
  `:review` level, a foreign issuer, or a credential that is merely
  `:draft`/`:suspended`. `:admissible` means a governor may proceed to
  its own checks.

  `:home-instance` is optional: when supplied, a credential issued by a
  DIFFERENT instance is downgraded to `:review` rather than accepted
  outright. Federation means a foreign credential is *usable*, not that
  it is *automatically trusted* — the receiving operator still owns the
  decision to honour another instance's onboarding."
  ([c now] (admission c now nil))
  ([c now home-instance]
   (let [errs   (credential-errors c)
         aml-st (or (:evidence/aml-status c)
                    (get-in c [:seller/evidence :evidence/aml-status]))
         reasons
         (vec
          (concat
           (map :seller.error/code errs)
           (when (= :revoked (:seller/status c)) [:revoked])
           (when (= :expired (:seller/status c)) [:expired])
           (when (and (:seller/expires-at c) now
                      (not (neg? (compare (str now) (str (:seller/expires-at c))))))
             [:expired])
           (when (= :suspended (:seller/status c)) [:suspended])
           (when (= :draft (:seller/status c)) [:not-yet-issued])
           (when (= :review aml-st) [:aml-review])
           (when (and home-instance
                      (not= home-instance (:seller/issuer c)))
             [:foreign-issuer])))
         refusing #{:invalid-seller-id :invalid-kind :invalid-status :invalid-issuer
                    :missing-field :invalid-country :insufficient-evidence
                    :aml-not-run :aml-hold :adjudicating-credential
                    :revoked :expired}
         reviewing #{:suspended :not-yet-issued :aml-review :foreign-issuer}]
     {:admission/outcome (cond
                           (some refusing reasons)  :refused
                           (some reviewing reasons) :review
                           :else                    :admissible)
      :admission/reasons reasons
      :admission/non-adjudicating true})))

(defn sellable?
  "The single question the listing layer asks before a seller may have
  a live offer: cleanly admissible AND bound to a payout destination.

  Identity and money are separate gates — a seller can be fully
  identity-verified and still not be able to receive funds. Both must
  hold, matching ISIC 4791's `:payment-processor-linked?` discipline."
  ([c now] (sellable? c now nil))
  ([c now home-instance]
   (and (= :admissible (:admission/outcome (admission c now home-instance)))
        (active? c now)
        (true? (:seller/payout-bound? c)))))

;; ───────────────────────────── portability ─────────────────────────────

(defn portability-envelope
  "Everything a seller needs to take their standing to ANOTHER instance,
  in one self-contained map.

  This is the anti-lock-in mechanism made concrete (ADR-2607264000 D1).
  It deliberately carries evidence *references and outcomes*, never
  document images or provider secrets — the same boundary
  kotoba-lang/ekyc draws ('this repo stores lifecycle and evidence
  references, not document images or provider secrets').

  `exported-at` is supplied by the caller; this namespace has no clock."
  [c exported-at]
  {:portability/version   1
   :portability/seller    (:seller/id c)
   :portability/issuer    (:seller/issuer c)
   :portability/exported-at exported-at
   :portability/credential (dissoc c :seller/note)
   :portability/verifiable-without-issuer? true
   :portability/carries-documents? false})

(defn accept-envelope
  "A receiving instance's view of an incoming portability envelope at
  `now`. Returns the admission decision plus the credential, with the
  foreign-issuer downgrade applied when `home-instance` differs.

  Returns `{:accept/credential .. :accept/admission .. :accept/errors ..}`;
  `:accept/errors` is non-empty for an envelope that is malformed as an
  envelope (wrong version, missing credential), which is distinct from a
  well-formed envelope carrying a refusable credential."
  [envelope now home-instance]
  (let [c (:portability/credential envelope)
        env-errs (vec (concat
                       (when (not= 1 (:portability/version envelope))
                         [{:seller.error/code :unsupported-envelope-version
                           :seller.error/detail (pr-str (:portability/version envelope))}])
                       (when-not (map? c)
                         [{:seller.error/code :missing-credential}])))]
    {:accept/credential c
     :accept/errors     env-errs
     :accept/admission  (when (and (empty? env-errs) (map? c))
                          (admission c now home-instance))}))
