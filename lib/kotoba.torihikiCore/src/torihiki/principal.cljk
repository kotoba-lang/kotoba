(ns torihiki.principal
  "Which Stable Principal an account belongs to, so a key can be replaced
  without the account being lost.

  ## The problem this exists for

  `torihiki.address/derive` makes the account id a FUNCTION OF THE KEY. That
  is what stops a proposer front-running a registration, and it is right. It
  also means a holder who rotates their key gets a different account —
  positions, collateral and open orders all stay behind on an id whose key is
  gone. There is no recovery, because there is nothing on the chain that says
  the two keys are the same person.

  A Stable Principal is that statement. `auth.kotoba.cloud` already issues one
  (`kotoba-lang/app-kotoba-cloud`): a Passkey ceremony, or an Ethereum wallet
  through `authentication`'s `:siwe` factor, resolves to a `principalId` that
  outlives any single credential. This namespace is the chain's side of it.

  ## Two signatures, because one authority would be too much

  Binding is deliberately a two-step handshake, and neither party can do it
  alone:

  - `:principal-claim` — the ACCOUNT OWNER says which principal they are. It
    records a pending claim and nothing else.
  - `:principal-confirm` — the CONTROLLER says the same, for the same account
    and principal. Only then is the binding written.

  The owner cannot bind a principal the controller will not confirm, so
  squatting somebody else's principal id buys nothing: the claim sits pending
  forever and the real holder's claim is still confirmable. The controller
  cannot bind an account that never claimed, so it cannot quietly enrol
  accounts that never asked for it.

  That matters because of what the binding then permits:

  - `:principal-rotate` — the CONTROLLER replaces an account's owner key.

  Rotation is real authority over somebody's money, and the two-step bind is
  what bounds it: **an account that never claimed a principal can never be
  rotated**, whatever the controller does. Opting in is the only way in, and
  it is a signature from the account itself.

  ## Why there is no new signature scheme here

  `:controller-authority` is an ACCOUNT ID, exactly as `:bridge-authority` is.
  The controller submits ordinary signed envelopes, so `torihiki.auth` does
  the verification, the controller's own nonce makes each attestation
  single-use, and `signing-payload` already binds it to the chain id. A
  separate attestation signature would have been a second scheme to keep
  correct, with its own replay window and its own way of being bound to the
  wrong chain.

  Pure: no crypto, no clock, no I/O. `torihiki.auth` has already established
  who signed by the time anything here is called."
  (:require [kotoba.lang.text :as str]
            [torihiki.address :as addr]))

(def reasons
  "Every refusal this namespace produces. Closed."
  #{:no-controller
    :not-the-controller
    :malformed-principal
    :reserved-account
    :principal-taken
    :account-taken
    :no-claim
    :claim-mismatch
    :not-bound
    :already-that-key
    :rotation-pending
    :no-rotation
    :not-the-holder})

(def ^:const max-principal-length
  "Matches `app-kotoba-cloud`'s own `identity-value`. The controller will not
  issue anything longer, and a chain that accepted more would be storing
  something the identity plane cannot mean."
  256)

(defn well-formed-principal?
  "The same shape `app-kotoba-cloud/session` accepts, restated rather than
  imported because the chain cannot depend on a Worker.

  Restating it is a real duplication and the alternative is worse: a principal
  the chain stores but the controller cannot resolve is an account bound to
  nothing. The two rules are pinned against each other by name in the test."
  [p]
  (boolean
   (and (string? p)
        (= p (str/trim p))
        (<= 1 (count p) max-principal-length)
        (not (re-find #"[\r\n]" p))
        (or (str/starts-with? p "did:")
            (str/starts-with? p "urn:kotoba:principal:")))))

(defn- controller [ex] (:controller-authority ex))

(defn- configured?
  "A `nil` controller closes the door rather than opening it.

  The opposite reading is the one that costs money: `:bridge-authority` is
  documented as leaving the faucet open when unset, because an unset MINT
  authority means the devnet mints freely. An unset IDENTITY authority means
  there is no identity plane at all — so `nil` here must refuse everything,
  not admit everyone. Reading it the other way would let any account rotate
  any other account's key on a chain whose operator simply had not configured
  this yet."
  [ex]
  (some? (controller ex)))

(defn check-claim
  "nil when `account` may record a pending claim to `principal`."
  [ex account principal]
  (cond
    (not (configured? ex)) :no-controller
    (not (well-formed-principal? principal)) :malformed-principal
    ;; The controller's own account, the backstop vault and the publishers are
    ;; configured at genesis and derive from no key. A principal bound to one
    ;; of them would be an identity claiming a role.
    (< account addr/floor) :reserved-account
    (some? (get-in ex [:principals account])) :account-taken
    (let [held (get-in ex [:principal-accounts principal])]
      (and (some? held) (not= held account)))
    :principal-taken
    :else nil))

(defn check-confirm
  "nil when `by` may promote `account`'s pending claim to a binding.

  The claim must still name the same principal the controller is confirming.
  Without that check the controller could confirm a DIFFERENT principal than
  the one the owner signed for, which is the whole handshake undone: the
  owner's signature would authorise a binding they never named."
  [ex by account principal]
  (cond
    (not (configured? ex)) :no-controller
    (not= by (controller ex)) :not-the-controller
    (not (well-formed-principal? principal)) :malformed-principal
    (nil? (get-in ex [:principal-claims account])) :no-claim
    (not= principal (get-in ex [:principal-claims account])) :claim-mismatch
    (some? (get-in ex [:principals account])) :account-taken
    (let [held (get-in ex [:principal-accounts principal])]
      (and (some? held) (not= held account)))
    :principal-taken
    :else nil))

(defn rotation-delay
  "Blocks between a rotation being proposed and taking effect.

  Genesis configuration, committed to the state root like every other
  authority. Zero is a legal value and it means the veto window does not
  exist — a chain may choose that, and `/head` can then say so, but it must be
  a choice somebody made rather than the default nobody noticed."
  [ex]
  (or (:rotation-delay-blocks ex) 0))

(defn check-rotate
  "nil when `by` may PROPOSE replacing `account`'s owner key with `pubkey`.

  Proposing, not doing. `rotate-propose` records it and `mature-rotations`
  applies it `rotation-delay` blocks later, and in between the account's own
  key can cancel.

  ## Why a controller that can take an account instantly is not trustworthy

  The two-step bind already bounds this authority to accounts that opted in
  with their own signature, which is what stops the controller enrolling
  people. It does nothing about the account that DID opt in: `auth.kotoba.cloud`
  compromised, or coerced, or simply wrong, could hand somebody's positions to
  a key of its choosing between one block and the next, and the holder would
  find out afterwards.

  A delay does not remove that authority — nothing here can, because key
  recovery IS the authority to replace a key. It makes the authority
  ANSWERABLE: the holder sees the proposal, and while they still hold the key
  they are replacing, they can refuse.

  **The tension is real and is not hidden.** Whoever holds the current key can
  cancel, and if that key was stolen the thief can cancel a legitimate
  recovery. The delay protects against a rogue controller and not against a
  stolen key; those are different attacks and this answers one of them. A
  chain that wants the other answer sets `rotation-delay-blocks` to 0 and says
  so.

  The account must already be BOUND — a pending claim is not enough. A claim
  is one signature from a key that may itself be the one being replaced, and
  letting it authorise rotation would collapse the handshake into a single
  step taken by whoever holds the key at that moment."
  [ex by account pubkey]
  (cond
    (not (configured? ex)) :no-controller
    (not= by (controller ex)) :not-the-controller
    (nil? (get-in ex [:principals account])) :not-bound
    (not (and (string? pubkey) (seq pubkey))) :malformed-principal
    (= pubkey (get-in ex [:account-keys account])) :already-that-key
    ;; One at a time. Two live proposals would let the controller queue a
    ;; second the holder has not seen while they are busy cancelling the
    ;; first, which turns the veto into a race the holder loses.
    (some? (get-in ex [:rotations account])) :rotation-pending
    :else nil))

(defn check-rotate-cancel
  "nil when `by` may cancel `account`'s pending rotation.

  Only the account itself. `torihiki.auth` has already established that this
  envelope carries the account's CURRENT owner key — which is exactly the key
  the rotation would replace, and the only party whose refusal means anything."
  [ex by account]
  (cond
    (nil? (get-in ex [:rotations account])) :no-rotation
    (not= by account) :not-the-holder
    :else nil))

(defn claim
  "Record the pending claim. Overwrites an earlier unconfirmed claim by the
  same account on purpose: the owner is allowed to change their mind before
  the controller has agreed to anything."
  [ex account principal]
  (assoc-in ex [:principal-claims account] principal))

(defn confirm
  "Write the binding, both ways, and drop the claim it came from."
  [ex account principal]
  (-> ex
      (assoc-in [:principals account] principal)
      (assoc-in [:principal-accounts principal] account)
      (update :principal-claims dissoc account)))

(defn rotate-propose
  "Record the pending rotation and the height it may take effect at.

  The height is stored rather than the delay, so a later change to
  `rotation-delay-blocks` cannot move a proposal that is already in flight —
  a holder who read `effective` and decided they had time would otherwise be
  wrong about a number they were shown."
  [ex account pubkey height]
  (assoc-in ex [:rotations account]
            {:pubkey pubkey :effective (+ height (rotation-delay ex))}))

(defn rotate-cancel
  "Drop a pending rotation."
  [ex account]
  (update ex :rotations dissoc account))

(defn- rotate!
  "Replace the owner key.

  Agents are dropped. They were authorised by the key that is being replaced,
  and a delegation outliving the credential that granted it is a key the new
  owner never issued and cannot see — the same reason `agent-forbidden` will
  not let an agent mint agents."
  [ex account pubkey]
  (-> ex
      (assoc-in [:account-keys account] pubkey)
      (update :agents dissoc account)))

(defn mature-rotations
  "Apply every rotation whose height has arrived, in account order.

  Driven by the BLOCK rather than by a transaction, for the same reason
  liquidation is: a rotation that needed somebody to send a transaction would
  be a recovery that depends on whoever is awake, and the holder's veto window
  would end whenever a keeper felt like ending it.

  Sorted by account id because two replicas applying the same set in a
  different order would produce different roots. There is no other ordering
  available and no reason to want one — the rotations are independent."
  [ex height]
  (reduce (fn [e [account {:keys [pubkey effective]}]]
            (if (>= height effective)
              (-> e (rotate! account pubkey) (rotate-cancel account))
              e))
          ex
          (sort-by key (:rotations ex {}))))

(defn pending-rotation
  "What is queued against `account`, or nil. The read a holder needs to know
  whether they are being replaced and by when."
  [ex account]
  (get-in ex [:rotations account]))

(defn principal-of [ex account] (get-in ex [:principals account]))
(defn account-of [ex principal] (get-in ex [:principal-accounts principal]))
