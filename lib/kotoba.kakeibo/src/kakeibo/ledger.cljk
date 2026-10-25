(ns kakeibo.ledger
  "Projection of categorized transactions onto double-entry postings.

  The ledger contract is not reinvented here: entries and postings are built
  with `kotoba-lang/banking` (`kotoba.banking/entry`, `posting`), which already
  owns balanced-posting validation and the minor-unit amount convention. This
  namespace only decides *which two accounts* a personal transaction touches:

  | direction        | debit              | credit             |
  |------------------|--------------------|--------------------|
  | outflow (amount<0)| `:expense/<category>` | the bank account |
  | inflow  (amount>0)| the bank account   | `:income/<category>` |

  Every posting is balanced by construction — one debit, one credit, same
  magnitude and currency — and `project` still asserts
  `:ledger/balanced?` before accepting one rather than trusting the
  construction, because an unbalanced posting reaching a ledger is the one
  error that is expensive to unwind."
  (:require [kotoba.banking :as banking]))

(defn expense-account
  "`:groceries` -> `:expense/groceries`."
  [category]
  (keyword "expense" (name (or category :uncategorized))))

(defn income-account
  "`:salary` -> `:income/salary`."
  [category]
  (keyword "income" (name (or category :uncategorized))))

(defn tx->posting
  "Build one balanced posting from a categorized transaction.

  Returns `{:kakeibo/posting {...}}`, or `{:kakeibo/problem ...}` for a
  transaction that cannot be posted. A zero amount is rejected: a zero posting
  carries no accounting meaning and its presence in a ledger is indistinguishable
  from a parse that silently failed."
  [{:tx/keys [id amount currency account category description] :as tx}]
  (cond
    (nil? id)      {:kakeibo/problem :missing-id :kakeibo/tx tx}
    (nil? amount)  {:kakeibo/problem :missing-amount :kakeibo/tx tx}
    (zero? amount) {:kakeibo/problem :zero-amount :kakeibo/tx tx}
    (nil? account) {:kakeibo/problem :missing-account :kakeibo/tx tx}
    :else
    (let [magnitude (if (neg? amount) (- amount) amount)
          outflow?  (neg? amount)
          entries   (if outflow?
                      [(banking/entry (expense-account category) :debit magnitude currency :ref id)
                       (banking/entry account :credit magnitude currency :ref id)]
                      [(banking/entry account :debit magnitude currency :ref id)
                       (banking/entry (income-account category) :credit magnitude currency :ref id)])
          p (banking/posting id entries :memo description)]
      (if (:ledger/balanced? p)
        {:kakeibo/posting (assoc p
                                 :kakeibo/date (:tx/date tx)
                                 :kakeibo/category (or category :uncategorized)
                                 :kakeibo/direction (if outflow? :outflow :inflow))}
        {:kakeibo/problem :unbalanced-posting :kakeibo/tx tx}))))

(defn project
  "Project a categorized transaction sequence onto postings.

  Returns `{:kakeibo/postings [...] :kakeibo/rejected [...] :kakeibo/posted n}`.
  Rejections are returned, never dropped, so a ledger total can always be
  reconciled against the transactions that produced it."
  [txs]
  (let [results (map tx->posting txs)]
    {:kakeibo/postings (vec (keep :kakeibo/posting results))
     :kakeibo/rejected (vec (filter :kakeibo/problem results))
     :kakeibo/posted   (count (filter :kakeibo/posting results))}))

(defn account-balances
  "Net movement per ledger account across postings, per currency.

  Returns `{[account currency] net-minor}` where a debit is positive and a
  credit negative. This is a movement summary, not an opening-balance-aware
  account balance: kakeibo sees statement windows, not the account's whole
  history, so calling it a balance would overstate what the data supports."
  [postings]
  (reduce
   (fn [acc entry]
     (let [k [(:ledger/account entry) (:ledger/currency entry)]
           delta (if (= :debit (:ledger/side entry))
                   (:ledger/amount entry)
                   (- (:ledger/amount entry)))]
       (update acc k (fnil + 0) delta)))
   {}
   (mapcat :ledger/entries postings)))
