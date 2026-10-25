(ns thorchain.memo
  "THORChain swap-memo construction, parsing and validation.

  THE MEMO *IS* THE TRANSACTION. A THORChain swap is an ordinary transfer to a
  vault address whose memo tells the network what to do with the funds — which
  asset to swap into, where to send the result, and (this is the part that pays
  for a wallet) which affiliate to skim basis points for. Get the memo wrong and
  the network refunds minus fees; get the destination field wrong and the funds
  go to the wrong address with no recourse. So this namespace parses and
  validates rather than formatting strings at call sites.

  GRAMMAR (verified 2026-07-26 against BOTH the THORNode parser source —
  gitlab.com/thorchain/thornode `x/thorchain/memo/memo_swap.go` — and the
  published memo docs, because the two disagree about the affiliate-bps ceiling;
  see `max-affiliate-bps` below):

    SWAP:ASSET:DESTADDR:LIM/INTERVAL/QUANTITY:AFFILIATE:FEE:DEX_AGG:DEX_ADDR:DEX_LIM
      0    1      2              3               4       5    6       7       8

  Only parts 0 and 1 are required. `SWAP` may be abbreviated `s` or `=`.
  AFFILIATE takes up to 5 `/`-separated THORNames; FEE takes either one bps
  value applied to all of them or one per affiliate.

  Pure `.cljc`, dual-platform, no network access."
  (:require [kotoba.lang.text :as str]
            [thorchain.asset :as asset]))

(def swap-prefix
  "The shortest legal SWAP prefix. THORChain accepts `SWAP`, `s` and `=`; the
  short form is not a style choice — see `max-memo-bytes`."
  "=")

(def max-memo-bytes
  "80 bytes. A swap FROM Bitcoin carries its memo in an OP_RETURN, and the
  standard relay policy caps that at 80 bytes. A memo that overflows does not
  get truncated — the transaction does not relay, or it relays without a
  readable memo and the vault treats the funds as a donation. This is the single
  most expensive failure mode in the whole flow, which is why `build` refuses to
  emit an over-long memo instead of warning about one."
  80)

(def max-affiliates
  "THORNode's `MultipleAffiliatesMaxCount`."
  5)

(def max-affiliate-bps
  "1000 bps (10%) — the ceiling the published memo docs state.

  THORNode's own validation is looser: it rejects only a TOTAL above 10000 bps
  (100%). This library defaults to the documented 1000 and requires an explicit
  `:allow-node-max? true` to go above it, because the failure mode of the loose
  reading is a wallet quietly charging a 50% fee that the network happily
  honours. If you need >10%, you are choosing that on purpose."
  1000)

(def node-max-affiliate-bps
  "10000 bps — the hard cap THORNode enforces on the SUM of affiliate bps."
  10000)

;; ─── build ───────────────────────────────────────────────────────────────

(defn- fixed8
  "THORChain expresses every amount in 1e8 fixed point regardless of the asset's
  native decimals. Accepts an already-1e8 integer (int or decimal string) and
  renders it as a plain integer — NOT scientific notation. The memo grammar does
  accept `1e6`, but a plain integer is unambiguous and this field is a
  minimum-output guard: a misread exponent silently changes slippage protection."
  [v]
  (let [s (str/trim (str v))]
    (when-not (re-matches #"\d+" s)
      (throw (ex-info "thorchain: 1e8 amount must be a non-negative integer"
                      {:value v})))
    (str/replace s #"^0+(?=\d)" "")))

(defn- validate-affiliates!
  [affiliates bps {:keys [allow-node-max?]}]
  (when (seq affiliates)
    (when (> (count affiliates) max-affiliates)
      (throw (ex-info (str "thorchain: at most " max-affiliates " affiliates")
                      {:affiliates affiliates})))
    (when (empty? bps)
      (throw (ex-info (str "thorchain: affiliate given without affiliate-bps — the network"
                           " would skim nothing, which is a silent 0% fee rather than an"
                           " error. Pass :affiliate-bps explicitly (0 if that is intended).")
                      {:affiliates affiliates})))
    (when-not (or (= 1 (count bps)) (= (count bps) (count affiliates)))
      (throw (ex-info (str "thorchain: affiliate-bps must be one value (applied to all)"
                           " or one per affiliate")
                      {:affiliates affiliates :bps bps})))
    (doseq [b bps]
      (when-not (and (integer? b) (<= 0 b))
        (throw (ex-info "thorchain: affiliate bps must be a non-negative integer"
                        {:bps b}))))
    (let [total (* (if (= 1 (count bps)) (count affiliates) 1) (reduce + bps))
          ceiling (if allow-node-max? node-max-affiliate-bps max-affiliate-bps)]
      (when (> total ceiling)
        (throw (ex-info (str "thorchain: total affiliate fee " total " bps exceeds "
                             ceiling " bps"
                             (when-not allow-node-max?
                               (str " — the documented maximum. THORNode itself allows up to "
                                    node-max-affiliate-bps
                                    "; pass :allow-node-max? true to charge more than "
                                    (/ max-affiliate-bps 100.0) "%.")))
                        {:total-bps total :ceiling ceiling}))))))

(defn build
  "Build a swap memo.

    (build {:to-asset \"ETH.ETH\"
            :destination \"0xe6a3…\"
            :limit \"10000000\"           ; optional, 1e8 fixed point
            :streaming-interval 3         ; optional (blocks between sub-swaps)
            :streaming-quantity 0         ; optional (0 = let the node decide)
            :affiliate \"t\"               ; optional THORName, or a seq of up to 5
            :affiliate-bps 10})           ; optional, one value or one per affiliate

  Emits the shortest legal form (`=` prefix, trailing empty fields dropped) and
  THROWS if the result exceeds `max-memo-bytes`, because an over-long memo means
  lost funds on a Bitcoin inbound rather than a rejected call.

  `:short-asset? true` abbreviates a token's contract address to its last 4 hex
  digits (`thorchain.asset/short-form`) to fit inside 80 bytes.

  AN AFFILIATE MUST BE REGISTERED, and this function cannot check that. A live
  node rejects an unregistered THORName outright (`cannot parse 'kb' as an
  Address`), which fails the whole swap and refunds it minus fees — and an
  unregistered name is shape-identical to a registered one, so no offline
  validation can catch it. Check with `thorchain.quote/thorname-request` +
  `registered?` before you rely on a name, or use a plain address."
  [{:keys [to-asset destination limit streaming-interval streaming-quantity
           affiliate affiliate-bps dex-aggregator dex-target-address
           dex-target-limit short-asset? allow-node-max?]}]
  (when-not (asset/valid? to-asset)
    (throw (ex-info "thorchain: :to-asset is not valid asset notation"
                    {:to-asset to-asset})))
  (let [affiliates (cond (nil? affiliate) []
                         (sequential? affiliate) (vec affiliate)
                         :else [affiliate])
        bps (cond (nil? affiliate-bps) []
                  (sequential? affiliate-bps) (vec affiliate-bps)
                  :else [affiliate-bps])
        _ (validate-affiliates! affiliates bps {:allow-node-max? allow-node-max?})
        asset-str (if short-asset? (asset/short-form to-asset) (:asset (asset/parse to-asset)))
        lim-field (cond
                    (or streaming-interval streaming-quantity)
                    (str (if limit (fixed8 limit) "0") "/"
                         (or streaming-interval 0) "/"
                         (or streaming-quantity 0))
                    limit (fixed8 limit)
                    :else "")
        parts [swap-prefix
               asset-str
               (or destination "")
               lim-field
               (str/join "/" affiliates)
               (str/join "/" bps)
               (or dex-aggregator "")
               (or dex-target-address "")
               (if dex-target-limit (fixed8 dex-target-limit) "")]
        ;; drop trailing empties only — an interior empty field is positional
        ;; and must stay (that is what `::t1/t2:10` means)
        trimmed (loop [v parts]
                  (if (and (> (count v) 2) (str/blank? (peek v))) (recur (pop v)) v))
        memo (str/join ":" trimmed)
        ;; UTF-8 BYTE length, not character count — the OP_RETURN limit is bytes.
        len #?(:clj (alength (.getBytes ^String memo "UTF-8"))
               :cljs (.-length (.encode (js/TextEncoder.) memo)))]
    (when (> len max-memo-bytes)
      (throw (ex-info (str "thorchain: memo is " len " bytes, over the " max-memo-bytes
                           "-byte OP_RETURN limit — a Bitcoin inbound with this memo would"
                           " not relay. Shorten it with a THORName destination,"
                           " :short-asset? true, or by dropping the limit field.")
                      {:memo memo :bytes len})))
    memo))

;; ─── parse ───────────────────────────────────────────────────────────────

(def ^:private swap-prefixes #{"SWAP" "S" "="})

(defn- parse-uint [s]
  (when (and (seq s) (re-matches #"\d+" s))
    #?(:clj (Long/parseLong s) :cljs (js/parseInt s 10))))

(defn parse
  "Parse a swap memo back into data. Returns nil if it is not a swap memo.

  The reason this exists: a quote API hands you a ready-made memo, and that memo
  encodes WHERE YOUR FUNDS GO. Submitting it unread means trusting a remote
  server with the destination address. `thorchain.quote/verify-memo` uses this to
  check the returned memo against what was actually requested."
  [memo]
  (when (string? memo)
    (let [parts (str/split (str/trim memo) #":" -1)
          head (str/upper (or (first parts) ""))]
      (when (contains? swap-prefixes head)
        (let [at (fn [i] (let [v (get parts i)] (when (seq v) v)))
              lim (at 3)
              [lim* interval quantity] (when lim (str/split lim #"/" -1))]
          (cond-> {:kind :swap
                   :to-asset (at 1)
                   :memo (str/trim memo)}
            (at 2) (assoc :destination (at 2))
            (seq lim*) (assoc :limit lim*)
            (seq interval) (assoc :streaming-interval (parse-uint interval))
            (seq quantity) (assoc :streaming-quantity (parse-uint quantity))
            (at 4) (assoc :affiliate (str/split (at 4) #"/" -1))
            (at 5) (assoc :affiliate-bps (mapv parse-uint (str/split (at 5) #"/" -1)))
            (at 6) (assoc :dex-aggregator (at 6))
            (at 7) (assoc :dex-target-address (at 7))
            (at 8) (assoc :dex-target-limit (at 8))))))))

(defn total-affiliate-bps
  "Total basis points a parsed memo skims. One bps value applied to N affiliates
  means N*bps in total — a detail that makes `:affiliate [a b c] :affiliate-bps
  [30]` a 90 bps fee, not 30."
  [{:keys [affiliate affiliate-bps]}]
  (let [affiliates (count (or affiliate []))
        bps (or affiliate-bps [])]
    (cond
      (empty? bps) 0
      (= 1 (count bps)) (* (max 1 affiliates) (first bps))
      :else (reduce + bps))))
