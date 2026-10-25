(ns game.economy
  "Economy system: Gems wallet + transactions.

  Restored from kami-game (kotoba-lang/kami-engine, deleted PR #82),
  per ADR-2607010930. Ported 1:1 from `kami-game/src/economy.rs`.")

;; Wallet: {:gems <i64> :transactions [Transaction ...]}
;; Transaction: {:amount <i64> :reason <string> :tick <u32>}

(defn wallet-new
  "Create a new wallet with `initial-gems`."
  [initial-gems]
  {:gems initial-gems
   :transactions []})

(defn wallet-default
  "Default wallet: 100 starting gems."
  []
  (wallet-new 100))

(defn wallet-credit
  "Credit `amount` gems into `wallet` with `reason`/`tick` logged.
  Returns the updated wallet (call `:gems` on the result for the new balance)."
  [wallet amount reason tick]
  (-> wallet
      (update :gems + amount)
      (update :transactions conj {:amount amount :reason reason :tick tick})))

(defn wallet-debit
  "Debit `amount` gems from `wallet`. Returns [:ok updated-wallet] or
  [:error \"insufficient gems\"] mirroring Rust's Result<i64, &'static str>."
  [wallet amount reason tick]
  (if (< (:gems wallet) amount)
    [:error "insufficient gems"]
    [:ok (-> wallet
             (update :gems - amount)
             (update :transactions conj {:amount (- amount) :reason reason :tick tick}))]))
