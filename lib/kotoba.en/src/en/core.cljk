(ns en.core
  "EN — the native currency unit riding on kotoba-lang/engi's L1
  (ADR-2607993000, com-junkawasaki/root). Pure, no I/O, no crypto, no
  wall-clock. Consumes an ALREADY-FINALIZED, globally-ordered sequence of
  transfers (the result of resolving `engi.consensus`'s 3-chain-committed
  blocks' proposal CIDs to their TransferBody content — that resolution is
  the caller's job, same division of labor `engi.core` already keeps
  between pure logic and I/O) and derives authoritative per-agent balances
  from it by REUSING `engi.core/fold-balance` unchanged, per agent, instead
  of duplicating its invariant-checking logic.

  This is deliberately the simplest possible 'smart contract': engi/L1
  supplies global BFT-finalized order (kotoba-lang/engi's
  `src/engi/consensus.cljc`); this repo supplies the deterministic
  state-transition semantics — which here IS exactly `fold-balance`'s
  existing invariant replay, just fed a globally-ordered multi-agent input
  instead of one agent's own unordered kotobase.net pull. No VM, no
  opcodes, no gas metering: ENGI/EN's whole domain is one operation (move a
  mutual-credit balance between two DIDs) and one invariant (net-zero,
  never below a declared credit limit)."
  (:require [engi.core :as engi]))

(defn- agents-in [transfers]
  (into #{} (mapcat (juxt :spender :receiver)) transfers))

(defn- assert-valid-transfer! [{:keys [amount transfer-id]}]
  (when-not (and (int? amount) (pos? amount))
    (throw (ex-info "en/transfer: amount must be a positive int"
                     {:transfer-id transfer-id :amount amount}))))

(defn- per-agent-entries
  "Build, for ONE `agent`, the ordered `entities` vector
  `engi.core/fold-balance` expects: a genesis (credit-limit from
  `credit-limits`, default 0 — ADR-2607101100's conservative
  \"undeclared limit means can only ever receive first\") followed by a
  debit entry for every finalized transfer where `agent` is the spender and
  a credit entry for every one where `agent` is the receiver, in the GLOBAL
  finalized order, `:engi/seq` renumbered per-agent (0-based, monotonic —
  the actual thing `fold-balance` checks). `:engi/prev-hash` is left as the
  placeholder \"unchecked\": `fold-balance`'s hash-chain check is opt-in via
  a supplied `:hash-fn`, deliberately omitted here since these entries are
  DERIVED from the finalized log, not an agent's own signed kotobase.net
  chain — the L1's Quorum Certificates are what vouch for finality here,
  not a per-agent hash chain."
  [agent transfers credit-limits]
  (let [genesis (engi/genesis {:credit-limit (get credit-limits agent 0) :created-at 0})
        relevant (filter #(or (= agent (:spender %)) (= agent (:receiver %))) transfers)]
    (into [genesis]
          (map-indexed
           (fn [seq* {:keys [spender receiver amount transfer-id ts]}]
             (engi/next-entry {:seq (dec seq*)} "unchecked"
                               {:id (str "en/tx/" transfer-id "/" agent)
                                :kind (if (= agent spender) "debit" "credit")
                                :counterparty (if (= agent spender) receiver spender)
                                :amount amount
                                :transfer-id transfer-id
                                :ts (or ts seq*)}))
           relevant))))

(defn replay-balances
  "Fold a globally-ordered, ALREADY-FINALIZED vector of `transfers`
  ({:keys [spender receiver amount transfer-id ts]}) into
  `{did -> engi.core/fold-balance-result}` for every agent that appears in
  at least one transfer. `credit-limits` — map of did -> non-positive int
  (ADR-2607101100 sign convention); an agent absent from this map gets the
  conservative default (0). Throws on a malformed (non-positive-amount)
  transfer — that's a caller bug, not a spending-limit violation, which
  `fold-balance` reports as data via `:violations` instead."
  ([transfers] (replay-balances transfers {}))
  ([transfers credit-limits]
   (run! assert-valid-transfer! transfers)
   (into {}
         (map (fn [agent]
                [agent (engi/fold-balance (per-agent-entries agent transfers credit-limits))]))
         (agents-in transfers))))

(defn balance-of
  "Convenience: `did`'s current EN balance after `replay-balances`. Raw, not
  spendable-adjusted — every transfer here is already L1-finalized, so
  there is no bilateral-pending state the way ADR-2607101100's v1 pull
  model had (a finalized transfer's debit and credit sides are both valid
  by construction, having passed witness quorum together)."
  [replay did]
  (get-in replay [did :balance] 0))

(defn net-zero?
  "The core ENGI/EN invariant, checkable at any point: total balance summed
  across every agent that appears in `replay` is zero — EN is never minted,
  only moved. A single finalized transfer's delta is always
  (+ amount (- amount)) = 0, so this holds after ANY prefix of a
  well-formed transfer sequence, not just the full log."
  [replay]
  (zero? (reduce + (map (comp :balance val) replay))))
