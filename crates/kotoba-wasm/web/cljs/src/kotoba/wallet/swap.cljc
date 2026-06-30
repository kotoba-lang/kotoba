(ns kotoba.wallet.swap
  "Same-chain swap planning. Cross-chain bridge routes are deliberately out of
   scope for this namespace.")

(def max-uint256 "115792089237316195423570985008687907853269984665640564039457584007913129639935")

(def required-quote-fields
  [:provider :router :spender :calldata :min-amount-out :deadline-ms :block-number])

(def required-observed-quote-fields
  [:origin :account-id :chain-id :from-token :to-token :amount-in])

(defn missing-fields [m ks]
  (filterv #(nil? (get m %)) ks))

(defn ensure-quote! [quote]
  (when-let [missing (seq (missing-fields quote required-quote-fields))]
    (throw (ex-info "wallet quote is missing required fields"
                    {:kind :wallet.quote/missing-fields
                     :missing (vec missing)
                     :quote-id (:id quote)})))
  quote)

(defn ensure-observed-quote! [quote]
  (when-let [missing (seq (missing-fields quote (into required-observed-quote-fields
                                                      required-quote-fields)))]
    (throw (ex-info "wallet quote is missing required fields"
                    {:kind :wallet.quote/missing-fields
                     :missing (vec missing)
                     :quote-id (:id quote)})))
  quote)

(defn- uint-decimal [x]
  (let [s (str (or x "0"))
        s (if (= \+ (first s)) (subs s 1) s)
        s (if-let [trimmed (seq (drop-while #(= \0 %) s))]
            (apply str trimmed)
            "0")]
    s))

(defn- compare-uint-decimal [a b]
  (let [a (uint-decimal a)
        b (uint-decimal b)]
    (compare [(count a) a] [(count b) b])))

(defn enough-allowance? [allowance amount]
  (not (neg? (compare-uint-decimal allowance amount))))

(defn quote-mismatch-fields [request quote]
  (->> [:chain-id :from-token :to-token :amount-in]
       (filterv (fn [k]
                  (and (contains? quote k)
                       (not= (get request k) (get quote k)))))))

(defn exact-approval-intent [request quote]
  {:kind :intent.kind/erc20-approve
   :token (:from-token request)
   :spender (:spender quote)
   :amount (:amount-in request)
   :unlimited-approval? false
   :to (:from-token request)
   :data :erc20.approve/exact
   :quote-id (:id quote)})

(defn router-intent [request quote]
  (cond-> {:kind :intent.kind/swap
           :to (:router quote)
           :value "0"
           :data (:calldata quote)
           :from-token (:from-token request)
           :to-token (:to-token request)
           :amount-in (:amount-in request)
           :min-amount-out (:min-amount-out quote)
           :slippage-bps (:slippage-bps request)
           :deadline-ms (:deadline-ms quote)
           :now-ms (:now-ms request)
           :spender (:spender quote)
           :quote-provider (:provider quote)
           :quote-block-number (:block-number quote)
           :quote-id (:id quote)}
    (seq (quote-mismatch-fields request quote))
    (assoc :quote-mismatch-fields (quote-mismatch-fields request quote))))

(defn plan [state quote request]
  (ensure-quote! quote)
  (when (:cross-chain? quote)
    (throw (ex-info "cross-chain routes require kotoba.bridge" {:quote quote})))
  (let [allowance (get-in state [:allowances [(:account-id request) (:chain-id request)
                                             (:from-token request) (:spender quote)]])
        approval-policy (get-in state [:policies (:origin request) :allow-unlimited-approval?])
        approval-needed? (not (enough-allowance? allowance (:amount-in request)))
        approval (when approval-needed?
                   (cond-> (exact-approval-intent request quote)
                     approval-policy (assoc :policy-allows-unlimited? true)))]
    (cond-> {:quote quote
             :request request
             :intents [(router-intent request quote)]}
      approval-needed? (update :intents #(vec (cons approval %))))))
