(ns marketplace.support
  "The bridge between a customer-support contact and a marketplace
  dispute — without either side deciding anything.

  ## The problem this solves

  `cloud-itonami-isic-8220` (call centres) logs customer contacts.
  `cloud-itonami-marketplace-crossborder` owns dispute intake. Today a
  buyer who phones to say \"my parcel never arrived\" produces a call
  record in one actor and nothing at all in the other, so the complaint
  dies in a log.

  A REFERRAL is the join: a support agent asserts *this contact is about
  this order, and the caller is claiming X*. That is all it asserts.

  ## What a referral must never become

  It must not carry an outcome. A support agent is the person most
  likely to form a view (\"the seller is clearly at fault\"), the least
  equipped to be held to it, and the most trusted by the caller — which
  is exactly why the contract refuses to carry one. `referral-errors`
  rejects any referral with an `:outcome`/`:fault`/`:liable` field, and
  `->dispute` produces an ordinary `marketplace.crossborder` dispute
  stamped non-adjudicating like any other.

  The fleet invariant holds unchanged: no actor adjudicates. A referral
  only moves a complaint from the place it was heard to the place it can
  be worked.

  Pure: no clock, no network, no randomness."
  (:require [kotoba.lang.text :as str]
            [marketplace.crossborder :as cb]))

;; ───────────────────────────── ticket ─────────────────────────────

(def channels
  "How the customer made contact. A closed set so reporting is
  comparable across instances and operators."
  #{:voice :chat :email :web-form :postal})

(defn ticket
  "A support contact record, as the call-centre side already knows it.

  This is deliberately a THIN projection of whatever the call-centre
  actor stores — it exists so the referral has a stable shape to point
  at, not to become a second ticketing system."
  [{:keys [id channel campaign agent buyer order opened-at summary]}]
  {:ticket/id       id
   :ticket/channel  channel
   :ticket/campaign campaign
   :ticket/agent    agent
   :ticket/buyer    buyer
   :ticket/order    order
   :ticket/opened-at opened-at
   :ticket/summary  summary})

;; ───────────────────────────── referral ─────────────────────────────

(def ^:private forbidden-keys
  "Fields that would turn a referral into a verdict. Checked by key
  rather than by value so an agent cannot smuggle a conclusion in as
  `{:fault :seller}` or `{:outcome :refund}`."
  [:referral/outcome :referral/fault :referral/liable :referral/decision
   :outcome :fault :liable :decision])

(defn referral
  "Refer a support ticket to dispute intake.

  `reason` must be one of `marketplace.crossborder/dispute-reasons` —
  the SAME closed vocabulary disputes already use, so a referral cannot
  invent a category that dispute reporting has no bucket for.

  `:referral/claimed-by-caller` is the caller's own account, recorded as
  a claim and labelled as one. `:referral/agent-note` is the agent's
  observation. Neither is a finding."
  [{:keys [id ticket-id order buyer seller reason claimed-by-caller
           agent agent-note referred-at]}]
  {:referral/id                id
   :referral/ticket            ticket-id
   :referral/order             order
   :referral/buyer             buyer
   :referral/seller            seller
   :referral/reason            reason
   :referral/claimed-by-caller claimed-by-caller
   :referral/agent             agent
   :referral/agent-note        agent-note
   :referral/referred-at       referred-at
   :referral/adjudicated?      false
   :referral/non-adjudicating  true})

(defn referral-errors
  "Structural errors, `[]` when sound."
  [r]
  (vec
   (concat
    (when (str/blank? (str (:referral/id r)))
      [{:support.error/code :missing-referral-id}])
    (when (str/blank? (str (:referral/ticket r)))
      [{:support.error/code :missing-ticket
        :support.error/detail "どの応対から起票されたか辿れない照会は受け付けない"}])
    (when (str/blank? (str (:referral/order r)))
      [{:support.error/code :missing-order}])
    (when (str/blank? (str (:referral/agent r)))
      [{:support.error/code :missing-agent
        :support.error/detail "起票した担当者が特定できない照会は受け付けない"}])
    (when-not (contains? cb/dispute-reasons (:referral/reason r))
      [{:support.error/code :unknown-reason
        :support.error/detail (str (pr-str (:referral/reason r))
                                   " は紛争理由の語彙に無い")}])
    ;; The whole point of the contract.
    (for [k forbidden-keys
          :when (contains? r k)]
      {:support.error/code :referral-carries-a-verdict
       :support.error/detail (str (pr-str k) " -- 応対担当者は裁定しない")})
    (when (true? (:referral/adjudicated? r))
      [{:support.error/code :referral-carries-a-verdict
        :support.error/detail ":referral/adjudicated? true"}]))))

(defn valid-referral? [r] (empty? (referral-errors r)))

;; ───────────────────────────── hand-off ─────────────────────────────

(defn ->dispute
  "Turn a valid referral into an ordinary `marketplace.crossborder`
  dispute. Returns nil for an invalid referral — a malformed or
  verdict-carrying referral must not become a dispute by another route.

  The narrative deliberately keeps the caller's claim and the agent's
  note ATTRIBUTED and separate. Merging them into one paragraph is how
  an agent's inference quietly becomes part of the buyer's testimony."
  [r]
  (when (valid-referral? r)
    (-> (cb/dispute {:id        (str "disp." (:referral/id r))
                     :order     (:referral/order r)
                     :buyer     (:referral/buyer r)
                     :seller    (:referral/seller r)
                     :reason    (:referral/reason r)
                     :narrative (str "[caller] " (:referral/claimed-by-caller r)
                                     " | [agent " (:referral/agent r) "] "
                                     (:referral/agent-note r))
                     :opened-at (:referral/referred-at r)})
        (assoc :dispute/source :support-referral
               :dispute/referral (:referral/id r)
               :dispute/ticket (:referral/ticket r)))))

(defn referral-evidence
  "The support contact itself, as a piece of dispute evidence.

  Filed as the BUYER's evidence (it is their account of events, taken
  down by an agent), tagged with the ticket so a reviewer can pull the
  recording. Appending it via `marketplace.crossborder/add-evidence`
  keeps it in the same append-only log as everything else either side
  files."
  [r]
  {:party    :buyer
   :kind     :support-contact
   :ref      (:referral/ticket r)
   :filed-at (:referral/referred-at r)
   :note     (str "起票: " (:referral/agent r))})

(defn open-with-evidence
  "The full hand-off: referral -> dispute with the support contact
  already attached as the buyer's first evidence. nil for an invalid
  referral."
  [r]
  (when-let [d (->dispute r)]
    (cb/add-evidence d (referral-evidence r))))
