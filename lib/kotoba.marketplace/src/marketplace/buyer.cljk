(ns marketplace.buyer
  "Buyer accounts — and a deliberate asymmetry with sellers.

  ## Why this is not `marketplace.seller` with the names changed

  A seller credential carries eKYC evidence and an AML screening because
  a seller RECEIVES money, and admitting one is a regulated act. A buyer
  SPENDS their own money on a book. Applying the same machinery to them
  would be both useless and harmful: useless because nothing in
  sanctions law requires identity-proofing a consumer purchase of
  household goods, and harmful because every field collected is a field
  that can leak.

  So this namespace is built the other way round — the question is not
  *how much can we verify?* but *how little do we need?*

  ## Levels, and what each is actually for

  `:guest` is a real, first-class level, not a degraded one. A buyer who
  never creates an account can still order: an operator that forces
  registration to sell someone a bottle of cola is collecting data it
  has no use for.

  Higher levels exist for specific, stated reasons — age-restricted
  goods, high-value orders, cross-border shipments needing a real
  consignee — and `purchase-errors` takes the REQUIRED level as an
  operator input rather than assuming one. There is no
  `:identity-verified` requirement baked in anywhere.

  ## Redaction is a first-class operation

  `redact` exists because this record will end up in audit ledgers,
  proposals and LLM context, and a buyer's address has no business being
  in any of them. Every actor that logs a buyer is expected to log
  `(redact buyer)`.

  Pure: no clock, no network, no randomness."
  (:require [kotoba.lang.text :as str]))

;; ───────────────────────────── levels ─────────────────────────────

(def levels
  "Buyer verification levels, weakest first. `:guest` is first-class —
  see the namespace docstring."
  #{:guest :contactable :phone-verified :identity-verified})

(def ^:private level-rank
  {:guest 0 :contactable 1 :phone-verified 2 :identity-verified 3})

(defn level>=
  "Does `have` meet or exceed `need`? Unknown levels never satisfy
  anything — an unrecognised level is treated as weaker than `:guest`,
  not stronger, so a typo in an operator's policy fails closed."
  [have need]
  (let [h (get level-rank have)
        n (get level-rank need)]
    (boolean (and h n (>= h n)))))

;; ───────────────────────────── address ─────────────────────────────

(def ^:private country-re #"^[A-Z]{3}$")

(defn address
  "A shipping address. `:retention` marks how long an operator intends
  to keep it — carried on the record so a retention sweep can act on the
  data itself rather than on a policy document that describes it.

  Deliberately NOT modelled: date of birth, gender, occupation. A
  courier does not need them and a marketplace should not hold them."
  [{:keys [line1 line2 city region postal-code country recipient phone retention]
    :or   {retention :order-lifetime}}]
  (cond-> {:address/line1     line1
           :address/city      city
           :address/postal-code postal-code
           :address/country   (some-> country str/upper)
           :address/recipient recipient
           :address/retention retention}
    line2  (assoc :address/line2 line2)
    region (assoc :address/region region)
    phone  (assoc :address/phone phone)))

(def retention-classes
  "How long an address is intended to be kept.

    :order-lifetime  deleted once the order is closed and the return
                     window has passed — the default, and the right one
                     for a guest checkout
    :account-saved   kept while the buyer keeps the account
    :legal-hold      kept because a dispute or tax rule requires it"
  #{:order-lifetime :account-saved :legal-hold})

(defn address-errors [a]
  (vec
   (concat
    (for [[k label] [[:address/line1 "line1"] [:address/city "city"]
                     [:address/postal-code "postal-code"]
                     [:address/recipient "recipient"]]
          :when (str/blank? (str (get a k)))]
      {:buyer.error/code :missing-address-field :buyer.error/field label})
    (when-not (re-matches country-re (str (:address/country a)))
      [{:buyer.error/code :invalid-country :buyer.error/detail "ISO-3166 alpha-3"}])
    (when-not (contains? retention-classes (:address/retention a))
      [{:buyer.error/code :invalid-retention
        :buyer.error/detail (pr-str (:address/retention a))}]))))

;; ───────────────────────────── account ─────────────────────────────

(defn account
  "A buyer account.

  `:contact` is a single opaque string — an email, a phone number, or a
  provider subject id. It is deliberately ONE field rather than a
  structured contact record: the marketplace needs a way to reach the
  buyer about their order and nothing more, and a schema with separate
  email/phone/alt-email slots is an invitation to fill them all in."
  [{:keys [id contact display-name level country created-at addresses]
    :or   {level :guest addresses []}}]
  {:buyer/id           (str id)
   :buyer/contact      contact
   :buyer/display-name display-name
   :buyer/level        level
   :buyer/country      (some-> country str/upper)
   :buyer/created-at   created-at
   :buyer/addresses    (vec addresses)
   ;; Stated on the record so no downstream reader has to infer it: a
   ;; buyer account is not, and never becomes, a KYC artefact.
   :buyer/kyc?         false})

(defn account-errors
  "Structural errors. Note what is NOT required: a display name, a
  country, an address, or any verification at all. A `:guest` account
  with only a contact string is valid, because that is enough to sell
  someone a book and tell them where it is."
  [b]
  (vec
   (concat
    (when (str/blank? (str (:buyer/id b)))
      [{:buyer.error/code :missing-id}])
    (when (str/blank? (str (:buyer/contact b)))
      [{:buyer.error/code :missing-contact
        :buyer.error/detail "注文について連絡が取れない買い手は受け付けられない"}])
    (when-not (contains? levels (:buyer/level b))
      [{:buyer.error/code :invalid-level :buyer.error/detail (pr-str (:buyer/level b))}])
    (when (and (:buyer/country b)
               (not (re-matches country-re (str (:buyer/country b)))))
      [{:buyer.error/code :invalid-country}])
    (when (true? (:buyer/kyc? b))
      [{:buyer.error/code :buyer-marked-as-kyc
        :buyer.error/detail "買い手アカウントを KYC 成果物として扱ってはならない"}])
    (mapcat address-errors (:buyer/addresses b)))))

(defn valid-account? [b] (empty? (account-errors b)))

;; ───────────────────────────── purchasing ─────────────────────────────

(defn purchase-errors
  "Can this buyer place THIS order?

  `opts`:
    `:require-level`   the operator's required level for this order
                       (default `:guest` — i.e. no requirement)
    `:needs-shipping?` true when the order has physical goods
    `:destination`     ISO-3166 alpha-3 the goods ship to

  The required level is an INPUT. There is no built-in rule that says a
  purchase over some amount needs identity verification, because that
  threshold is a jurisdiction- and product-specific operator decision
  and inventing one here would impose it on every deployment."
  ([b] (purchase-errors b {}))
  ([b {:keys [require-level needs-shipping? destination]
       :or   {require-level :guest}}]
   (vec
    (concat
     (account-errors b)
     (when-not (level>= (:buyer/level b) require-level)
       [{:buyer.error/code :insufficient-level
         :buyer.error/detail (str "必要: " (pr-str require-level)
                                  " / 現在: " (pr-str (:buyer/level b)))}])
     (when (and needs-shipping? (empty? (:buyer/addresses b)))
       [{:buyer.error/code :no-shipping-address}])
     (when (and needs-shipping? destination
                (seq (:buyer/addresses b))
                (not-any? #(= destination (:address/country %)) (:buyer/addresses b)))
       [{:buyer.error/code :no-address-in-destination
         :buyer.error/detail (str destination)}])))))

(defn can-purchase?
  ([b] (can-purchase? b {}))
  ([b opts] (empty? (purchase-errors b opts))))

(defn shipping-address
  "The address for a destination country, or the first one when no
  destination is given. nil when the buyer has none."
  ([b] (first (:buyer/addresses b)))
  ([b destination]
   (or (first (filter #(= destination (:address/country %)) (:buyer/addresses b)))
       nil)))

;; ───────────────────────────── redaction ─────────────────────────────

(defn redact
  "The buyer record as it may appear in an audit ledger, a proposal, or
  an LLM prompt.

  Keeps the id (so records join), the level and the country (so a
  governor can reason about eligibility), and DROPS contact details,
  display name and every address line. The destination country survives
  because a cross-border check needs it; the street does not, because
  nothing downstream of an order does.

  Actors are expected to log `(redact b)`, never `b`."
  [b]
  (-> (select-keys b [:buyer/id :buyer/level :buyer/country :buyer/kyc?])
      (assoc :buyer/redacted? true
             :buyer/address-countries (vec (distinct (keep :address/country
                                                           (:buyer/addresses b)))))))

(defn redacted?
  "True when a record has been through `redact`. Lets a governor refuse
  a proposal that embedded a raw buyer."
  [b]
  (true? (:buyer/redacted? b)))

(def pii-keys
  "Keys whose presence anywhere in a structure means it still carries
  personal data."
  #{:buyer/contact :buyer/display-name
    :address/line1 :address/line2 :address/phone :address/recipient})

(defn leaks-pii?
  "True when a structure still carries buyer contact details or address
  lines — the check a governor runs over a proposal before it is written
  to an append-only ledger nobody can later scrub.

  Walks the structure rather than searching `pr-str` output. A map whose
  keys all share a namespace prints as `#:buyer{:contact ...}`, so a
  substring search for `:buyer/contact` silently finds nothing and the
  check passes a record that is full of PII — which is worse than having
  no check, because it reads as a guarantee."
  [m]
  (boolean
   (some (fn [node] (and (map? node) (some pii-keys (keys node))))
         (tree-seq coll? seq m))))

;; ───────────────────────────── retention ─────────────────────────────

(defn purgeable-addresses
  "Addresses an operator may delete for a buyer whose orders are all
  closed. `:legal-hold` never purges; `:account-saved` purges only when
  the account itself is being closed.

  Returning the list rather than performing the deletion is deliberate:
  this library does not own the store, and a retention sweep is an
  operator action with its own audit trail."
  [b {:keys [orders-closed? closing-account?]}]
  (vec
   (for [a (:buyer/addresses b)
         :let [r (:address/retention a)]
         :when (or (and (= :order-lifetime r) orders-closed?)
                   (and (= :account-saved r) closing-account?))]
     a)))
