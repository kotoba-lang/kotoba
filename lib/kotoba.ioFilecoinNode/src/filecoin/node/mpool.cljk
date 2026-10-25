(ns filecoin.node.mpool
  "Message admission — `Message.ValidForBlockInclusion`.

  These are the checks a node applies before a message may go in a block, and
  they are the reason a well-formed message can still be rejected. Every one
  of them is transcribed from `chain/types/message.go` rather than inferred,
  because the interesting ones are not the obvious ones:

  - `GasPremium > GasFeeCap` is invalid. A premium is *paid out of* the cap,
    not added to it, so a caller who sets the premium as if it were a tip on
    top writes a message no block will carry.
  - `To` may not be the **zero address** (`f3yaaa…by2smx7a`, the all-zero BLS
    key) from network version 7 onward. It is a valid address that nobody
    holds the key to, so it is a burn that does not look like one.
  - An `f4` (delegated) address is only admissible from network version 18.
    Before Hygge there was no address manager to give it meaning.
  - `GasLimit` must be strictly positive *and* at least `min-gas`, which is
    the cost of storing the message on chain — a figure that depends on the
    message's own serialised length, so it is a parameter here rather than a
    constant.

  This namespace judges a message on its own terms only. Whether the sender
  exists, has the nonce, or can pay `required-funds` is state, and state is
  not something this library has."
  (:require [filecoin.address :as addr]
            [filecoin.bigint :as bigint]))

(def ^:const block-gas-limit 10000000000)

(def ^:const total-filecoin-atto
  "2 × 10^9 FIL, in attoFIL. A value larger than the entire supply is refused
  outright rather than left to fail later against a balance."
  "2000000000000000000000000000")

(def ^:const zero-address
  "The all-zero BLS address. `buildconstants.ZeroAddress`."
  "f3yaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaby2smx7a")

(def ^:const network-version-zero-address-check
  "From nv7 on, `To` may not be the zero address."
  7)

(def ^:const network-version-delegated
  "Hygge. `f4` addresses became admissible here."
  18)

(defn- address-of [x]
  (cond (nil? x) nil
        (map? x) x
        (string? x) (addr/from-string x)
        :else (throw (ex-info "mpool: not an address" {:value x}))))

(defn- address-string [a]
  (addr/to-string (assoc a :network :mainnet)))

(defn address-valid-for-network-version?
  "`abi.AddressValidForNetworkVersion`. Every protocol but `f4` has always
  been valid; `f4` starts at nv18."
  [a network-version]
  (if (= addr/delegated-protocol (addr/protocol a))
    (>= network-version network-version-delegated)
    true))

(defn check-valid-for-block-inclusion!
  "Throw with a reason, or return the message. `min-gas` is the on-chain
  storage cost of this message; `network-version` gates the two rules that
  changed."
  [msg min-gas network-version]
  (let [{:keys [version to from value gas-limit gas-fee-cap gas-premium]} msg
        to (address-of to)
        from (address-of from)
        fail! (fn [why extra] (throw (ex-info (str "mpool: " why) (or extra {}))))]
    (when-not (= 0 version)
      (fail! "'Version' unsupported" {:version version}))
    (when (nil? to)
      (fail! "'To' address cannot be empty" nil))
    (when (and (>= network-version network-version-zero-address-check)
               (= zero-address (address-string to)))
      (fail! "invalid 'To' address — the zero address" nil))
    (when-not (address-valid-for-network-version? to network-version)
      (fail! "'To' address protocol unsupported for network version"
             {:protocol (addr/protocol to) :network-version network-version}))
    (when (nil? from)
      (fail! "'From' address cannot be empty" nil))
    (when-not (address-valid-for-network-version? from network-version)
      (fail! "'From' address protocol unsupported for network version"
             {:protocol (addr/protocol from) :network-version network-version}))
    (when (nil? value)
      (fail! "'Value' cannot be nil" nil))
    (when (bigint/lt value "0")
      (fail! "'Value' field cannot be negative" {:value value}))
    (when (bigint/gt value total-filecoin-atto)
      (fail! "'Value' field cannot be greater than total filecoin supply"
             {:value value}))
    (when (nil? gas-fee-cap)
      (fail! "'GasFeeCap' cannot be nil" nil))
    (when (bigint/lt gas-fee-cap "0")
      (fail! "'GasFeeCap' field cannot be negative" {:gas-fee-cap gas-fee-cap}))
    (when (nil? gas-premium)
      (fail! "'GasPremium' cannot be nil" nil))
    (when (bigint/lt gas-premium "0")
      (fail! "'GasPremium' field cannot be negative" {:gas-premium gas-premium}))
    (when (bigint/gt gas-premium gas-fee-cap)
      (fail! "'GasFeeCap' less than 'GasPremium'"
             {:gas-fee-cap gas-fee-cap :gas-premium gas-premium}))
    (when (> gas-limit block-gas-limit)
      (fail! "'GasLimit' field cannot be greater than a block's gas limit"
             {:gas-limit gas-limit :block-gas-limit block-gas-limit}))
    (when (<= gas-limit 0)
      (fail! "'GasLimit' field must be positive" {:gas-limit gas-limit}))
    (when (< gas-limit min-gas)
      (fail! "'GasLimit' field cannot be less than the cost of storing a message on chain"
             {:gas-limit gas-limit :min-gas min-gas}))
    msg))

(defn valid-for-block-inclusion?
  [msg min-gas network-version]
  (try (check-valid-for-block-inclusion! msg min-gas network-version) true
       (catch #?(:clj Exception :cljs :default) _ false)))

(defn required-funds
  "`GasFeeCap × GasLimit` — what the sender's balance must cover *before* the
  message runs, whatever it actually spends."
  [msg]
  (bigint/mul (:gas-fee-cap msg) (str (:gas-limit msg))))

(defn effective-gas-premium
  "What the miner actually collects, given a base fee.

  The premium is clamped to `GasFeeCap - BaseFee`: a sender who asks for a
  large premium under a cap that barely covers the base fee is not offering
  what they wrote down. Providers do include messages whose cap is below the
  base fee, and for those the premium is zero rather than negative."
  [msg base-fee]
  (let [available (bigint/sub (:gas-fee-cap msg) base-fee)
        available (if (bigint/lt available "0") "0" available)]
    (if (<= (bigint/cmp (:gas-premium msg) available) 0)
      (str (:gas-premium msg))
      available)))
