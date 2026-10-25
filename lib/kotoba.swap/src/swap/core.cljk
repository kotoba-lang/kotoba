(ns swap.core
  "Provider-agnostic swap core: an intent, a normalized quote, an execution plan
  as DATA, and the safety invariants that must hold before anything is signed.

  NOTHING HERE SIGNS OR SENDS. `plan` returns an ordered vector of steps
  (`:erc20-approve`, `:evm-call`, `:native-transfer`) that an executor — holding
  the keys, which this namespace never sees — carries out. That is the
  `state + event -> next-state + effects` shape this workspace uses for
  application logic (ADR-2607201300): product semantics live in portable data,
  and the mechanism of actually moving funds lives in a host.

  It also means the interesting half is testable without a network, a key, or a
  chain: a plan is a value you can assert on.

  TWO RAILS, ONE SHAPE:
    :aggregator — same-chain EVM swap via a DEX aggregator (`swap.aggregator`)
    :thorchain  — native cross-chain, e.g. BTC <-> ETH (`swap.thorchain`)
  Both produce the same normalized quote and the same kind of plan, so a caller
  picks a rail by asset pair and doesn't branch on vendor shapes."
  (:require [kotoba.lang.text :as str]))

;; ─── intent ──────────────────────────────────────────────────────────────

(defn intent
  "Normalize a user's swap request.

    (intent {:from {:chain \"BTC\" :asset \"BTC.BTC\" :decimals 8}
             :to   {:chain \"ETH\" :asset \"ETH.ETH\" :decimals 18}
             :amount \"0.05\"            ; HUMAN decimal, exact string
             :destination \"0xabc…\"
             :taker \"bc1q…\"             ; who pays (EVM: the signing address)
             :slippage-bps 100
             :fee-bps 30})               ; OUR fee, in basis points

  `:amount` is a decimal STRING on purpose. A uint256 does not fit in a double
  and ClojureScript loses precision above 2^53, so no float is allowed anywhere
  near an amount in this library."
  [{:keys [from to amount destination taker slippage-bps fee-bps fee-recipient
           fee-recipient-contract? deadline-seconds]
    :as raw}]
  (when-not (and (map? from) (map? to))
    (throw (ex-info "swap: :from and :to must be maps of {:chain :asset :decimals}"
                    {:intent raw})))
  (doseq [[k side] {:from from :to to}]
    (doseq [f [:chain :asset :decimals]]
      (when (nil? (get side f))
        (throw (ex-info (str "swap: " k " is missing " f) {:side side})))))
  (when-not (and (string? amount) (re-matches #"\d+(\.\d+)?" (str/trim amount)))
    (throw (ex-info "swap: :amount must be a non-negative decimal STRING (no floats)"
                    {:amount amount})))
  (when (and fee-bps (not (and (integer? fee-bps) (<= 0 fee-bps 1000))))
    (throw (ex-info "swap: :fee-bps must be an integer in 0..1000 (0–10%)"
                    {:fee-bps fee-bps})))
  (when (and fee-bps (pos? fee-bps) (nil? fee-recipient))
    (throw (ex-info (str "swap: :fee-bps without :fee-recipient — the fee would be"
                         " charged and then paid to nobody (or, on some aggregators,"
                         " silently dropped). Name the recipient explicitly.")
                    {:fee-bps fee-bps})))
  {:from from :to to
   :amount (str/trim amount)
   :destination destination
   :taker taker
   :slippage-bps (or slippage-bps 100)
   :fee-bps (or fee-bps 0)
   :fee-recipient fee-recipient
   ;; Declared, not guessed: an EOA recipient legitimately has no code, so
   ;; "no code at this address" is ambiguous between safe and funds-lost unless the
   ;; caller says which kind of recipient it is. Set this true for a Safe or any
   ;; other contract, and `check` will refuse a chain where it is not deployed.
   :fee-recipient-contract? (boolean fee-recipient-contract?)
   :deadline-seconds (or deadline-seconds 1200)})

(defn cross-chain?
  "Does this intent cross chains? Decides the rail: same-chain EVM goes through
  an aggregator, anything else needs a cross-chain network."
  [{:keys [from to]}]
  (not= (:chain from) (:chain to)))

;; ─── normalized quote ────────────────────────────────────────────────────

(defn quote-shape
  "The fields every provider must normalize to. Documented as data so a new
  driver has an explicit contract rather than an implied one."
  []
  #{:rail                  ; :aggregator | :thorchain
    :expected-out          ; smallest-unit decimal STRING
    :min-out               ; smallest-unit decimal STRING — the on-chain guard
    :fee-bps               ; OUR fee, as actually encoded in the swap
    :fee-mechanism         ; :protocol-affiliate | :separate-transfer | :none
    :expires-at            ; unix seconds, or nil if the provider gives none
    :steps                 ; ordered execution steps (see `plan`)
    :provider              ; vendor id, for audit
    :raw})                 ; the untouched provider response

;; ─── safety invariants ───────────────────────────────────────────────────

;; Amounts are smallest-unit decimal strings, which means comparisons need a
;; bignum on both platforms (a uint256 does not fit in a double). Both platforms
;; have one — unlike modInverse/modPow — so these three helpers are all the
;; reader-conditional this namespace needs.

(defn contract-code?
  "Does an `eth_getCode` result indicate deployed code? An empty result means the
  address is an EOA — or nothing at all — ON THAT CHAIN."
  [code-result]
  (boolean (and code-result (string? code-result)
                (pos? (count (str/replace code-result #"^0x" ""))))))

(defn amount<
  "Compare two non-negative smallest-unit decimal STRINGS, without a bignum:
  normalize leading zeros, then shorter-is-smaller, then lexicographic. Exact and
  fully portable — a double would corrupt any comparison above 2^53, which is
  well inside the range of an 18-decimal token balance."
  [a b]
  (let [n (fn [s] (str/replace (str/trim (str s)) #"^0+(?=\d)" ""))
        a (n a) b (n b)]
    (if (not= (count a) (count b))
      (< (count a) (count b))
      (neg? (compare a b)))))

(defn- big [s]
  (when (and s (re-matches #"\d+" (str s)))
    #?(:clj (java.math.BigInteger. (str s)) :cljs (js/BigInt (str s)))))

(defn- big-zero? [b]
  #?(:clj (zero? (.signum ^java.math.BigInteger b))
     :cljs (= b (js/BigInt 0))))

(defn- big-lt? [a b]
  #?(:clj (neg? (.compareTo ^java.math.BigInteger a ^java.math.BigInteger b))
     :cljs (< a b)))

(defn- apply-bps
  "b * (10000 - bps) / 10000 — integer arithmetic, no float."
  [b bps]
  #?(:clj (-> ^java.math.BigInteger b
              (.multiply (java.math.BigInteger/valueOf (long (- 10000 bps))))
              (.divide (java.math.BigInteger/valueOf 10000)))
     :cljs (/ (* b (js/BigInt (- 10000 bps))) (js/BigInt 10000))))

(defn check
  "Validate a normalized quote against the intent BEFORE anything is signed.
  Returns `{:ok? true}` or `{:ok? false :problems [{…}]}` — every problem at
  once, as data, so a UI can show all of them instead of the first.

  These are the checks whose absence is expensive:

  - **min-out present and non-zero.** A swap submitted without a minimum-output
    guard can be sandwiched for an arbitrary fraction of its value. A provider
    that returns no min-out is not usable, not a warning.
  - **min-out consistent with the requested slippage.** If the provider's
    min-out is further below expected-out than the caller asked to tolerate,
    the caller's slippage setting is not being honoured.
  - **the fee is actually encoded.** If a fee was requested and the quote came
    back with `:fee-mechanism :none`, the swap earns nothing. Silent, and only
    discovered when the money doesn't arrive.
  - **not expired.** Requires `now` to be passed in — this namespace never reads
    a clock, so the same quote+time pair always yields the same verdict
    (`Date.now()` is also unavailable to workflow-style callers here).
  - **steps present.** A plan with no steps would \"succeed\" doing nothing.
  - **the fee recipient exists on the chain it will be paid on.** Checked when the
    intent declares `:fee-recipient-contract? true`. A Safe is deployed PER CHAIN,
    and a fee paid to an address with no code there cannot be moved by anyone —
    measured on a real Safe that existed on Ethereum and had no code on six other
    chains. Declared-but-unchecked is itself a problem, so a caller cannot forget
    to look.

  `facts` is an optional map of things this namespace cannot look up, because it
  performs no I/O: currently `{:fee-recipient-code <eth_getCode result>}`, obtained
  via `swap.fee/recipient-code-request`."
  ([intent quote now] (check intent quote now {}))
  ([intent {:keys [expected-out min-out fee-bps fee-mechanism expires-at steps]} now
    {:keys [fee-recipient-code] :as facts}]
  (let [exp (big expected-out)
        mn (big min-out)
        problems
        (cond-> []
          (empty? steps)
          (conj {:problem :no-steps})

          (nil? mn)
          (conj {:problem :missing-min-out
                 :note "a swap without a minimum-output guard can be sandwiched"})

          (and mn (big-zero? mn))
          (conj {:problem :zero-min-out
                 :note "min-out of 0 accepts any output, including ~nothing"})

          (and exp mn (big-lt? mn (apply-bps exp (:slippage-bps intent))))
          (conj {:problem :min-out-below-requested-slippage
                 :expected-out expected-out :min-out min-out
                 :slippage-bps (:slippage-bps intent)})

          (and (pos? (:fee-bps intent 0)) (= :none fee-mechanism))
          (conj {:problem :fee-not-encoded
                 :requested-bps (:fee-bps intent)
                 :note "the provider returned no fee mechanism — this swap earns nothing"})

          (and (pos? (:fee-bps intent 0)) fee-bps (not= fee-bps (:fee-bps intent)))
          (conj {:problem :fee-bps-mismatch
                 :requested (:fee-bps intent) :encoded fee-bps})

          (and expires-at now (<= expires-at now))
          (conj {:problem :quote-expired :expires-at expires-at :now now})

          ;; A contract fee recipient must be deployed on the chain the fee lands
          ;; on. Declared-but-unchecked is its OWN problem rather than a silent
          ;; pass: the point is that a caller cannot forget to look.
          (and (pos? (:fee-bps intent 0))
               (:fee-recipient-contract? intent)
               (not (contains? facts :fee-recipient-code)))
          (conj {:problem :fee-recipient-unverified
                 :recipient (:fee-recipient intent)
                 :note (str "recipient is declared a contract but no eth_getCode result"
                            " was supplied — run swap.fee/recipient-code-request and pass"
                            " the result as :fee-recipient-code")})

          (and (pos? (:fee-bps intent 0))
               (:fee-recipient-contract? intent)
               (contains? facts :fee-recipient-code)
               (not (contract-code? fee-recipient-code)))
          (conj {:problem :fee-recipient-has-no-code
                 :recipient (:fee-recipient intent)
                 :chain (or (get-in intent [:to :chain]) (get-in intent [:from :chain]))
                 :note (str "no contract code at the fee recipient on this chain. A Safe"
                            " is deployed PER CHAIN — a fee paid here cannot be moved by"
                            " anyone. Deploy it on this chain first, or name a recipient"
                            " that exists here.")}))]
    (if (seq problems) {:ok? false :problems problems} {:ok? true}))))

(defn plan
  "Validate and return the execution steps, or throw. Use when a caller wants a
  hard gate rather than a problem list — `check` is the one to use in a UI.

  Every step is a map with `:step/kind` and enough data to execute it, and
  nothing else:

    {:step/kind :erc20-approve :chain \"ETH\" :to <token> :data <0x…> :value \"0\"
     :step/why \"router needs an allowance for 1.5 USDC\"}
    {:step/kind :evm-call      :chain \"ETH\" :to <router> :data <0x…> :value <wei>}
    {:step/kind :native-transfer :chain \"BTC\" :to <vault> :amount <sats> :memo <str>}

  `:step/why` is required on every step. A wallet that cannot explain a
  confirmation prompt in the user's words shouldn't be asking for it."
  [intent quote now]
  (let [{:keys [ok? problems]} (check intent quote now)]
    (when-not ok?
      (throw (ex-info (str "swap: quote failed pre-signing checks: "
                           (str/join ", " (map (comp name :problem) problems)))
                      {:problems problems})))
    (:steps quote)))

;; ─── execution state machine ─────────────────────────────────────────────

(def terminal-statuses #{:confirmed :failed :refunded :expired})

(defn begin
  "Initial execution state for a validated quote."
  [intent quote]
  {:status :ready
   :intent intent
   :quote quote
   :step-index 0
   :submitted []        ; tx ids, in order
   :events []})

(defn advance
  "`state + event -> next state`. Pure: no clock, no network, no I/O. The host
  turns each pending step into a real transaction and feeds the outcome back as
  an event, which is what keeps the sequencing rules here and not scattered
  through a UI.

  Events: `{:event :submitted :tx-id …}` `{:event :confirmed :tx-id …}`
          `{:event :failed :reason …}` `{:event :refunded :tx-id …}`
          `{:event :expired}`"
  [{:keys [status step-index quote] :as state} {:keys [event tx-id reason] :as ev}]
  (let [steps (:steps quote)
        record (fn [s] (update s :events conj ev))]
    (cond
      (terminal-statuses status) (record state)

      (= :submitted event)
      (record (-> state (assoc :status :pending) (update :submitted conj tx-id)))

      (= :confirmed event)
      (let [next-index (inc step-index)]
        (record (if (< next-index (count steps))
                  (assoc state :status :ready :step-index next-index)
                  (assoc state :status :confirmed))))

      (= :failed event) (record (assoc state :status :failed :failure reason))
      (= :refunded event) (record (assoc state :status :refunded))
      (= :expired event) (record (assoc state :status :expired))
      :else (record state))))

(defn current-step
  "The step the executor should perform next, or nil when there is nothing to do
  (either finished, or waiting on a confirmation)."
  [{:keys [status step-index quote]}]
  (when (= :ready status)
    (get (:steps quote) step-index)))

(defn done? [{:keys [status]}] (contains? terminal-statuses status))
