(ns noren.diagnose
  "事業者の公開面（サイト）を測る。純 `.cljc`、LLM もブラウザも使わない。

  **UI 品質は測り直さない。** `kotoba-lang/design-quality` が HIG/WCAG の
  12 軸を既に持っており、この名前空間はその軸ベクタと同じ形の
  `{:id :title :weight :check}` を足すだけで機構（重み正規化・finding 収集）を
  丸ごと借りる。ここが持つのは design-quality に無い問い —— **その店が
  やっている仕事を、そのページが代わりに引き受けられているか**。

  綺麗だが電話番号も営業時間も無いページは、UI 軸では高得点になる。
  だから presence を UI より重く置く（0.55 / 0.45）。"
  (:require [kotoba.lang.text :as str]
            [design-quality.audit :as dq]))

(defn ^:private has? [s re] (boolean (re-find re s)))

(defn ^:private text-only
  "タグを落とした素のテキスト。文言の有無を見る軸はこちらに当てる
  （属性値や class 名に偶然当たるのを防ぐ）。"
  [html]
  (-> html
      (str/replace #"(?is)<(script|style)\b.*?</\1>" " ")
      (str/replace #"(?s)<[^>]*>" " ")))

;; ── presence 軸 ──────────────────────────────────────────────────────────
;;
;; 軸は文脈に依存する（EC に営業時間は要らず、飲食店に決済導線は要らない）。
;; 定数ベクタではなく **文脈から軸を作る関数**にしてあるのはそのため。

(defn presence-axes
  "`ctx` = {:surface :storefront|:catalog :url \"https://…\" :year 2026}"
  [{:keys [surface url year]}]
  (let [catalog? (= surface :catalog)]
    (into
     [{:id :https :title "HTTPS で配信されている" :weight 0.12
       :check (fn [_]
                (if (and url (str/starts-with? (str/lower url) "https://"))
                  {:score 1.0}
                  {:score 0.0 :finding "HTTPS ではない — ブラウザが警告を出し、フォームは事実上使えない"}))}

      {:id :contact-path :title "問い合わせ導線がある" :weight 0.15
       :check (fn [s]
                (let [tel  (has? s #"(?i)href=[\"']tel:")
                      mail (has? s #"(?i)href=[\"']mailto:")
                      form (has? s #"(?is)<form\b")]
                  (case (count (filter true? [tel mail form]))
                    0 {:score 0.0 :finding "電話・メール・フォームのいずれも無い — 見た人が連絡する手段が無い"}
                    1 {:score 0.6 :finding "連絡手段が 1 つだけ — 相手が使える経路を選べない"}
                    {:score 1.0})))}

      {:id :address :title "所在地が書かれている" :weight 0.13
       :check (fn [s]
                (let [t (text-only s)]
                  (if (or (has? s #"(?is)<address\b")
                          (has? t #"〒\s*\d{3}")
                          (has? t #"(北海道|東京都|大阪府|京都府|..県)\s*\S{1,12}(市|区|町|村)"))
                    {:score 1.0}
                    {:score 0.0 :finding "所在地が読み取れない — 地図にも検索結果にも載りにくい"})))}

      {:id :tel :title "電話番号が書かれている" :weight 0.10
       :check (fn [s]
                (cond
                  (has? s #"(?i)href=[\"']tel:")            {:score 1.0}
                  (has? (text-only s) #"0\d{1,4}-\d{1,4}-\d{4}")
                  {:score 0.7 :finding "電話番号はあるが tel: リンクになっていない — スマートフォンから掛けられない"}
                  :else {:score 0.0 :finding "電話番号が無い"}))}

      {:id :structured-data :title "schema.org の構造化データ" :weight 0.12
       :check (fn [s]
                (let [ld (has? s #"(?i)application/ld\+json")
                      typ (has? s #"(?i)\"@type\"\s*:\s*\"(Restaurant|LocalBusiness|Store|CafeOrCoffeeShop|BarOrPub|FoodEstablishment|Product|Offer)\"")]
                  (cond
                    (and ld typ) {:score 1.0}
                    ld {:score 0.5 :finding "JSON-LD はあるが業種の @type が無い — 検索結果のリッチ表示に載らない"}
                    :else {:score 0.0 :finding "構造化データが無い — 地図・検索の情報が第三者の書いた内容のままになる"})))}

      {:id :ogp :title "共有時の見え方（OGP）" :weight 0.08
       :check (fn [s]
                (let [n (count (distinct (re-seq #"(?i)property=[\"']og:(title|description|image|url)[\"']" s)))]
                  (cond
                    (>= n 3) {:score 1.0}
                    (pos? n) {:score 0.5 :finding "OGP が部分的 — SNS に貼られたときタイトルも画像も出ないことがある"}
                    :else    {:score 0.0 :finding "OGP が無い — SNS やメッセージに貼られても何の店か分からない"})))}]

     (if catalog?
       [{:id :catalog :title "商品と価格が載っている" :weight 0.16
         :check (fn [s]
                  (let [t (text-only s)
                        priced (count (re-seq #"[¥￥]\s?\d|(\d{2,3},\d{3}|\d{3,5})\s*円" t))]
                    (cond
                      (>= priced 3) {:score 1.0}
                      (pos? priced) {:score 0.5 :finding "価格の記載が 1〜2 件しかない — 品揃えが分からない"}
                      :else {:score 0.0 :finding "商品と価格が読み取れない — 買う判断ができない"})))}
        {:id :commerce-terms :title "特商法表記" :weight 0.14
         :check (fn [s]
                  (if (has? (text-only s) #"特定商取引法|特商法")
                    {:score 1.0}
                    {:score 0.0 :finding "特定商取引法に基づく表記が見当たらない — 通信販売では表示義務がある"}))}]

       [{:id :hours :title "営業時間が書かれている" :weight 0.16
         :check (fn [s]
                  (let [t (text-only s)]
                    (cond
                      (has? t #"(営業時間|OPEN|Open Hours|ランチ|ディナー)[^。\n]{0,40}\d{1,2}[:：]\d{2}") {:score 1.0}
                      (has? t #"(営業時間|定休日)") {:score 0.5 :finding "営業時間の見出しはあるが時刻が読み取れない"}
                      :else {:score 0.0 :finding "営業時間が無い — 行ってよいか判断できない"})))}
        {:id :menu :title "メニューと価格が載っている" :weight 0.14
         :check (fn [s]
                  (let [t (text-only s)
                        priced (count (re-seq #"[¥￥]\s?\d|\d{3,5}\s*円" t))]
                    (cond
                      (>= priced 3) {:score 1.0}
                      (pos? priced) {:score 0.5 :finding "価格つきの品目が 1〜2 件 — 予算が分からない"}
                      :else {:score 0.0 :finding "メニューと価格が読み取れない"})))}])

     )))

(defn ^:private freshness-axis
  "更新の痕跡。`year` を渡されたときだけ効く（年を知らずに古さは言えない）。"
  [year]
  {:id :freshness :title "更新されている痕跡" :weight 0.10
   :check (fn [s]
            (let [t (text-only s)
                  years (->> (re-seq #"20[0-9]{2}" t)
                             (map #(#?(:clj Long/parseLong :cljs js/parseInt) %))
                             (filter #(<= 2000 % (+ year 1))))
                  newest (when (seq years) (reduce max years))]
              (cond
                (nil? newest) {:score 0.5 :finding "年の記載が無く、いつの情報か分からない"}
                (>= newest (dec year)) {:score 1.0}
                :else {:score 0.0
                       :finding (str "最新の年表記が " newest " 年 — 少なくとも "
                                     (- year newest) " 年更新されていないように見える")})))})

;; ── 診断 ─────────────────────────────────────────────────────────────────

(def ui-weight 0.45)
(def presence-weight 0.55)

(def verdict-thresholds
  "判定の境目。**loop 側で書き換えない** —— 基準が周ごとに動くと、
  前の周の提案と今の周の提案が比較できなくなる。"
  {:healthy 80.0 :repairable 55.0})

(defn verdict
  [overall]
  (cond
    (>= overall (:healthy verdict-thresholds))    :healthy
    (>= overall (:repairable verdict-thresholds)) :repairable
    :else                                         :rebuild))

(defn definitive-absence?
  "**取れなかったこと**と**無いこと**は別物。ここを混ぜると、こちらの回線が
  一瞬切れただけで『御社のサイトが見つかりません』と送ることになる。

  無いと言い切ってよいのは、相手のサーバが明確にそう答えたときだけ
  （404 / 410）。接続エラー・タイムアウト・5xx は**こちらの観測の失敗**で、
  相手について何も分かっていない。"
  [status]
  (contains? #{404 410 "404" "410"} status))

(defn diagnose
  "`html` を測る。`ctx` = {:surface :url :year :status}。サイトが取れていない
  （`html` が nil/空）ときは `:absent` を返す —— **0 点ではない**。
  取れなかったのか無いのかを区別しないと、後段が「ひどいサイト」として
  提案文を書いてしまう。"
  [html {:keys [surface url year status] :as ctx}]
  (if (str/blank? html)
    {:verdict :absent :overall 0.0 :url url :surface surface
     :observation {:status status :definitive? (definitive-absence? status)}
     :findings [{:axis :no-site :finding "公開面が取得できなかった（無いか、応答しない）"}]}
    (let [ui (dq/score-page html {:extra-axes dq/extra-axes})
          pres (dq/score-page html {:axes (cond-> (presence-axes ctx)
                                            year (conj (freshness-axis year)))})
          overall (+ (* ui-weight (:overall ui)) (* presence-weight (:overall pres)))
          findings (->> (concat (map #(assoc % :plane :presence) (:axes pres))
                                (map #(assoc % :plane :ui) (:axes ui)))
                        (filter :finding)
                        ;; 効き目の大きい順（重み × 伸びしろ）。提案に載せる順序でもある。
                        (sort-by (fn [a] (- (* (:weight a) (- 1.0 (:score a))))))
                        vec)]
      {:verdict (verdict overall)
       :overall overall
       :observation {:status status :definitive? true}
       :ui (:overall ui)
       :presence (:overall pres)
       :url url
       :surface surface
       :axes {:ui (:axes ui) :presence (:axes pres)}
       :findings findings})))
