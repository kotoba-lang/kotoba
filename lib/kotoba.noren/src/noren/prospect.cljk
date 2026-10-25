(ns noren.prospect
  "見込み事業者（prospect）の型と適格判定。純 `.cljc`、I/O 無し。

  ここが答えるのは 1 つだけ —— **この事業者に、いま接触してよいか**。
  発見の手段（Common Crawl / passive DNS / 手入力）はこの名前空間の外にあり、
  どの経路で来た prospect も同じ述語を通る。

  適格性は 3 つの独立した問いに分かれる。混ぜると、片方が通ったことを理由に
  もう片方を通してしまう:

  1. `industry-eligible?` — 売る相手の業種か（ISIC gate）
  2. `contactable?`       — 特定電子メール法の例外に**実測で**当たるか
  3. `fresh?`             — 観測がまだ有効か（古い観測で今日の判断をしない）"
  (:require [kotoba.lang.text :as str]))

;; ── 業種 gate ────────────────────────────────────────────────────────────
;;
;; ISIC Rev.5。ここに無い業種へは売らない。「広げれば売れる」は正しいが、
;; 広げた瞬間に「この loop は何屋か」が答えられなくなる。広げるのは
;; blueprint actor が実在する業種に限る（cloud-itonami/cloud-itonami-isic-####）。

(def eligible-isic
  "接触してよい ISIC class → 何を売る面か。"
  {"5610" {:label "restaurants and mobile food service" :surface :storefront}
   "5629" {:label "other food service activities"       :surface :storefront}
   "5630" {:label "beverage serving activities"         :surface :storefront}
   "4791" {:label "retail sale via internet"            :surface :catalog}
   "4799" {:label "other retail sale not in stores"     :surface :catalog}})

(defn industry-eligible?
  [{:prospect/keys [isic]}]
  (contains? eligible-isic isic))

;; ── 連絡先の適格性 ───────────────────────────────────────────────────────
;;
;; 日本の特定電子メール法はオプトイン規制（法 3 条 1 項）で、広告宣伝メールは
;; 原則として同意が要る。例外の 1 つが **自らメールアドレスを公表している
;; 団体・営業を営む個人**（同項 4 号）で、この loop はそこにしか当たらない。
;;
;; だから `:prospect/contact` は「アドレスを知っている」では足りない。
;; **どこで公表されていたか（URL）と、いつ見たか**を持っていなければ、
;; 例外に当たる根拠が無い。根拠の無い接触は governor が HARD で止める。
;;
;; 同項ただし書き: 受信拒否を公表している相手は例外から外れる。サイトに
;; 「営業メールお断り」があれば、公表アドレスでも送れない。

(def opt-out-markers
  "サイト上の受信拒否表明。1 つでも見えたら接触不可。"
  [#"営業.{0,4}(メール|電話).{0,6}(お断り|ご遠慮|禁止)"
   #"(勧誘|セールス).{0,6}(お断り|ご遠慮)"
   #"(?i)no\s+(soliciting|solicitation)"
   #"(?i)do\s+not\s+contact"])

(defn declared-opt-out?
  "取得した HTML から受信拒否表明を読む。**書いてあることだけ**を見る。"
  [html]
  (boolean (and html (some #(re-find % html) opt-out-markers))))

(defn contactable?
  "特定電子メール法 3 条 1 項 4 号の例外に当たる形をしているか。

  ここは**形**だけを判定する（値の真偽は observation の責任）。返るのは
  bool ではなく理由つきの map —— 落ちた理由が分からないと、運用が
  『とりあえず送る』に倒れる。"
  [{:prospect/keys [kind contact opt-out-declared?]}]
  (let [{:contact/keys [email source-url observed-at]} contact
        reasons (cond-> []
                  (not (contains? #{:organization :sole-trader} kind))
                  (conj {:rule :recipient-not-a-business
                         :detail "個人宛は 4 号の例外に当たらない（団体・営業を営む個人のみ）"})

                  (str/blank? email)
                  (conj {:rule :no-email :detail "メールアドレスが無い"})

                  (str/blank? source-url)
                  (conj {:rule :no-publication-evidence
                         :detail "そのアドレスが公表されていた URL が無い（例外の根拠を持てない）"})

                  (str/blank? observed-at)
                  (conj {:rule :no-observation-time
                         :detail "いつ公表を見たかが無い（後から検証できない）"})

                  (true? opt-out-declared?)
                  (conj {:rule :opt-out-declared
                         :detail "サイト上で受信拒否が表明されている（4 号ただし書き）"}))]
    {:ok? (empty? reasons) :reasons reasons}))

;; ── 観測の鮮度 ───────────────────────────────────────────────────────────

(defn epoch-day
  "\"2026-08-11T09:00:00Z\" / \"2026-08-11\" → epoch day（整数）。
  解釈できなければ nil —— **今日として扱わない**（古い観測を新しく見せる）。"
  [s]
  (when (and (string? s) (re-find #"^\d{4}-\d{2}-\d{2}" s))
    (let [[y m d] (map #(#?(:clj Long/parseLong :cljs js/parseInt) %)
                       (rest (re-find #"^(\d{4})-(\d{2})-(\d{2})" s)))
          ;; 暦の厳密さは要らない（要るのは差だけ）。日数に潰す。
          y' (if (<= m 2) (dec y) y)
          era (quot (if (neg? y') (- y' 399) y') 400)
          yoe (- y' (* era 400))
          doy (+ (quot (+ (* 153 (+ m (if (> m 2) -3 9))) 2) 5) (dec d))
          doe (+ (* yoe 365) (quot yoe 4) (- (quot yoe 100)) doy)]
      (+ (* era 146097) doe -719468))))

(defn fresh?
  "観測が `max-age-days` 以内か。`now` は同じ書式の文字列。"
  [{:prospect/keys [observed-at]} now max-age-days]
  (let [a (epoch-day observed-at) b (epoch-day now)]
    (boolean (and a b (<= 0 (- b a) max-age-days)))))

;; ── まとめ ───────────────────────────────────────────────────────────────

(def default-max-age-days 90)

(defn dedup-key
  "同じ事業者を 2 回接触しないための鍵。host で畳む（`www.` と scheme の揺れを吸収）。"
  [{:prospect/keys [site-url]}]
  (some-> site-url
          str/lower
          (str/replace #"^https?://" "")
          (str/replace #"^www\." "")
          (str/split #"[/?#]") first
          not-empty))

(defn eligible
  "3 つの gate をまとめて通す。`{:ok? bool :reasons [...] :surface kw}`。"
  ([p now] (eligible p now default-max-age-days))
  ([p now max-age-days]
   (let [c (contactable? p)
         reasons (cond-> (:reasons c)
                   (not (industry-eligible? p))
                   (conj {:rule :industry-out-of-scope
                          :detail (str "ISIC " (:prospect/isic p) " はこの loop の対象外")})

                   (not (fresh? p now max-age-days))
                   (conj {:rule :stale-observation
                          :detail (str "観測が " max-age-days " 日より古い、または日付が読めない")})

                   (str/blank? (:prospect/site-url p))
                   (conj {:rule :no-site-url :detail "診断対象の URL が無い"}))]
     {:ok? (empty? reasons)
      :reasons (vec reasons)
      :surface (get-in eligible-isic [(:prospect/isic p) :surface])})))
