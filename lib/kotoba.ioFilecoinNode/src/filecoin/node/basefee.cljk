(ns filecoin.node.basefee
  "The base fee: what every message on Filecoin burns per unit of gas, and how
  the network moves it.

  There are **two** mechanisms, and which one applies is decided by height:

  - Before `FireHorse`, from **utilisation** — the classic EIP-1559 shape.
    Gas used above target raises the fee, below target lowers it, capped at
    12.5% per epoch.
  - From `FireHorse` on, from **premiums** — the fee tracks what senders were
    actually willing to tip at the 80th percentile of block gas, so it
    responds to demand rather than to how full blocks happen to be.

  Both are pure functions of numbers, which is why they are here. Gathering
  their *inputs* is not: the utilisation form needs every message in the
  tipset deduplicated by CID, and the premium form needs them deduplicated by
  (sender, nonce) — that is a blockstore walk, and a blockstore is a seam
  (`filecoin.node.protocols/IBlockstore`).

  Every value is a decimal string through `filecoin.bigint`, because
  `baseFee × delta` reaches 10^18 on an ordinary epoch. Note that the
  division is Euclidean, not truncating — see `filecoin.bigint/div`; the
  numerator is negative on every under-target epoch, which is most of them."
  (:require [filecoin.bigint :as bigint]))

(def ^:const block-gas-limit 10000000000)
(def ^:const block-gas-target 5000000000)      ; BlockGasLimit / 2

(def ^:const block-gas-target-index
  "`BlockGasLimit*80/100 - 1`. The premium mechanism reads the premium at the
  80th percentile of a block's gas, counted from the top."
  7999999999)

(def ^:const base-fee-max-change-denom 8)      ; 12.5% per epoch
(def ^:const minimum-base-fee 100)             ; attoFIL; the fee never goes below
(def ^:const packing-efficiency-num 4)
(def ^:const packing-efficiency-denom 5)

(def ^:const upgrade-smoke-height
  "Before Smoke, utilisation was scaled by a packing-efficiency factor: blocks
  could not be filled to the limit in practice, so the raw gas figure
  understated how loaded the network was."
  51000)

(def ^:const upgrade-fire-horse-height
  "Mainnet epoch at which the base fee stopped tracking utilisation and
  started tracking premiums."
  6052800)

(defn next-base-fee-from-utilization
  "`ComputeNextBaseFee`. `gas-limit-used` is the sum of the gas limits of the
  distinct messages in the tipset, `no-of-blocks` its block count.

  The delta is capped at ±`block-gas-target` before it is scaled, which is
  what bounds the change at 12.5% — an empty epoch and a triply-overfull one
  move the fee by the same amount in opposite directions."
  [base-fee gas-limit-used no-of-blocks epoch]
  (let [delta (if (> epoch upgrade-smoke-height)
                (- (quot gas-limit-used no-of-blocks) block-gas-target)
                (- (quot (* packing-efficiency-denom gas-limit-used)
                         (* no-of-blocks packing-efficiency-num))
                   block-gas-target))
        delta (max (- block-gas-target) (min block-gas-target delta))
        change (-> (bigint/mul base-fee (str delta))
                   (bigint/div (str block-gas-target))
                   (bigint/div (str base-fee-max-change-denom)))
        next-fee (bigint/add base-fee change)]
    (bigint/max-of next-fee (str minimum-base-fee))))

(defn next-base-fee-from-premium
  "`nextBaseFeeFromPremium`:

      maxAdj = ceil(baseFee / 8)
      next   = max(minBaseFee, baseFee + min(maxAdj, premiumP - maxAdj))

  The `premiumP - maxAdj` term is what makes this a *tracking* rule rather
  than a utilisation one: a percentile premium exactly equal to one
  adjustment step leaves the fee where it is, a larger one raises it, and
  zero pulls it down by the full step."
  [base-fee premium-p]
  (let [denom (str base-fee-max-change-denom)
        max-adj (bigint/div (bigint/add base-fee (bigint/sub denom "1")) denom)
        adj (bigint/min-of max-adj (bigint/sub premium-p max-adj))]
    (bigint/max-of (str minimum-base-fee) (bigint/add base-fee adj))))

(defn weighted-quick-select
  "The gas-weighted percentile premium — `WeightedQuickSelect`.

  Upstream picks a random pivot and recurses; the answer does not depend on
  the pivot (its own test asserts that across every permutation), so this
  sorts descending and walks the cumulative weight instead. Same result, no
  randomness to seed, and no recursion depth to worry about on a tipset with
  a few thousand messages.

  `index` counts gas from the *highest* premium down. Reaching the end of the
  list without passing it means the tipset did not fill the percentile, and
  the answer is zero — blocks that are not full do not raise the fee."
  [premiums limits index]
  (let [pairs (sort (fn [a b] (bigint/cmp (first b) (first a)))
                    (map vector premiums limits))]
    (loop [ps pairs acc 0]
      (if (empty? ps)
        "0"
        (let [[premium weight] (first ps)
              acc (+ acc weight)]
          (if (> acc index) (str premium) (recur (rest ps) acc)))))))
