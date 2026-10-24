(ns denchu.media
  "電柱の所有者 → その柱に広告を掲出できる**媒体社／指定代理店**と問い合わせ先。

  日本の電柱広告は open inventory ではない。柱は電力会社・通信会社の
  設備であり、広告の販売は所有者が指定した代理店を通してしか行えない。
  したがってこの ns が答えるのは「この柱に出したい → 誰に連絡するか」で
  あって、「いくらで買えるか」ではない（それは `denchu.pricing`、しかも
  常に indicative）。

  **カバレッジは正直に申告する。** ここに無い所有者は「掲出できない」の
  ではなく「まだ調べていない」。`coverage` がその差を返す。各エントリは
  必ず `:source-url` と `:as-of` を持ち、出典の無い連絡先は載せない。

  **自称は自称として記録する。** 代理店自身のサイトが主張する独占性・
  唯一性は `:claims` に `:self-reported` として置き、事実として昇格させない。"
  (:require [kotoba.lang.text :as str]
            [denchu.area :as area]))

(def agencies
  "代理店 id → 実体。`:contact` は公開されている問い合わせ経路のみ。
  個人名・直通番号は載せない（公開情報だけを扱う）。"
  {:tepco-town-planning
   {:agency/id :tepco-town-planning
    :agency/legal-name "東電タウンプランニング株式会社"
    :agency/group "東京電力グループ"
    :agency/sells-poles-of #{:tepco-pg}
    :agency/products #{:wrap :projecting}
    :agency/contact {:tel "03-6371-8111"
                     :tel-hours "月～金 9:00～17:00（祝日・年末年始除く）"
                     :form-url "https://www.ttplan.co.jp/contact/"
                     :service-url "https://www.ttplan.co.jp/service/ad_pole/"
                     :landing-url "https://denchu-koukoku.com/"}
    :agency/source-url "https://www.ttplan.co.jp/service/ad_pole/"
    :agency/as-of "2026-08-04"}

   :telwel-east
   {:agency/id :telwel-east
    :agency/legal-name "テルウェル東日本株式会社"
    :agency/group "NTTグループ"
    :agency/sells-poles-of #{:ntt-east}
    :agency/products #{:wrap :projecting}
    :agency/contact {:form-url "https://www.telwel-east.co.jp/contact/"
                     :service-url "https://www.telwel-east.co.jp/products/other/denchu/"
                     :fee-url "https://www.telwel-east.co.jp/denchu-koukoku/fee/"}
    :agency/note "道路占用の申請および NTT 電柱の使用許可申請は当社および販売会社が行う旨を自社サイトに掲載。"
    :agency/source-url "https://www.telwel-east.co.jp/products/other/denchu/"
    :agency/as-of "2026-08-04"}

   :ntt-townpage
   {:agency/id :ntt-townpage
    :agency/legal-name "NTTタウンページ株式会社"
    :agency/group "NTTグループ"
    :agency/sells-poles-of #{:ntt-east}
    :agency/products #{:wrap :projecting}
    :agency/coverage-note "北海道全域・長野県全域・新潟県全域（自社サイト記載）"
    :agency/contact {:service-url "https://www.ntt-tp.co.jp/service/pole.html"}
    :agency/source-url "https://www.ntt-tp.co.jp/service/pole.html"
    :agency/as-of "2026-08-04"}

   :cocots
   {:agency/id :cocots
    :agency/legal-name "株式会社広告通信社"
    :agency/group "NTT西日本グループ総合広告代理店"
    :agency/sells-poles-of #{:ntt-west}
    :agency/products #{:wrap :projecting}
    :agency/contact {:service-url "https://www.cocots.jp/service/denchu/"}
    :agency/source-url "https://www.cocots.jp/service/denchu/"
    :agency/as-of "2026-08-04"}

   :nikko-tsushinsha
   {:agency/id :nikko-tsushinsha
    :agency/legal-name "株式会社日広通信社"
    :agency/sells-poles-of #{:tepco-pg :ntt-east}
    :agency/products #{:wrap :projecting}
    :agency/contact {:service-url "https://www.ad-nikko.co.jp/denchu/"}
    :agency/claims [{:claim "東京電力柱・NTT柱の両方を販売できる指定代理店"
                     :status :self-reported
                     :source-url "https://www.ad-nikko.co.jp/denchu/"}]
    :agency/source-url "https://www.ad-nikko.co.jp/denchu/"
    :agency/as-of "2026-08-04"}

   :kanden-service
   {:agency/id :kanden-service
    :agency/legal-name "関電サービス株式会社"
    :agency/group "関西電力グループ"
    :agency/sells-poles-of #{:kepco-t}
    :agency/products #{:wrap :projecting}
    :agency/contact {:service-url "https://www.kandensv.co.jp/service/appeal/koukoku/denchu/agency.html"
                     :landing-url "https://denchu-koukoku.jp/"}
    :agency/note "協力店（組合員の広告会社）経由での受付を自社サイトで案内。"
    :agency/source-url "https://www.kandensv.co.jp/service/appeal/koukoku/denchu/agency.html"
    :agency/as-of "2026-08-04"}

   :kanden-denchu-kumiai
   {:agency/id :kanden-denchu-kumiai
    :agency/legal-name "関西電力電柱広告業組合"
    :agency/sells-poles-of #{:kepco-t}
    :agency/products #{:wrap :projecting}
    :agency/contact {:service-url "https://kanden-denchu-koukoku.org/"}
    :agency/note "組合員の広告会社が窓口。個社の一覧は組合サイト側にある。"
    :agency/source-url "https://kanden-denchu-koukoku.org/"
    :agency/as-of "2026-08-04"}

   :chuden-kbs
   {:agency/id :chuden-kbs
    :agency/legal-name "中電クラビス株式会社"
    :agency/group "中部電力グループ"
    :agency/sells-poles-of #{:chuden-pg}
    :agency/products #{:wrap :projecting}
    :agency/contact {:service-url "https://www.chudenkbs.co.jp/service/adcom/denchu/"}
    :agency/source-url "https://www.chudenkbs.co.jp/service/adcom/denchu/"
    :agency/as-of "2026-08-04"}})

(def owners
  "所有者キーワード → 表示名。`denchu.pole/operator->owner` の値域と対応する。
  ここに載っている = 柱を識別できる、であって、代理店を知っている、ではない。"
  {:tepco-pg   "東京電力パワーグリッド"
   :tohoku-epco "東北電力ネットワーク"
   :chuden-pg  "中部電力パワーグリッド"
   :kepco-t    "関西電力送配電"
   :energia-nw "中国電力ネットワーク"
   :yonden-t   "四国電力送配電"
   :kyuden-t   "九州電力送配電"
   :hepco-nw   "北海道電力ネットワーク"
   :rikuden-t  "北陸電力送配電"
   :okiden     "沖縄電力"
   :ntt-east   "東日本電信電話"
   :ntt-west   "西日本電信電話"})

(defn agencies-for
  "所有者 → その柱を売れる代理店（実体の vector）。未収録なら空。
  空は「掲出できない」ではなく「窓口を未収集」を意味する。"
  [owner]
  (->> (vals agencies)
       (filter (fn [a] (contains? (:agency/sells-poles-of a) owner)))
       (sort-by (comp name :agency/id))
       vec))

(defn routable?
  "その柱の掲出申込先が分かるか。"
  [owner]
  (boolean (seq (agencies-for owner))))

(defn coverage
  "窓口カバレッジの正直な申告。`:covered` は代理店を1社以上収録した
  所有者、`:uncovered` は識別できるのに窓口が未収集の所有者。"
  []
  (let [ks (keys owners)
        covered (filterv routable? ks)
        uncovered (filterv (complement routable?) ks)]
    {:owners-known (count ks)
     :covered (vec (sort-by name covered))
     :uncovered (vec (sort-by name uncovered))
     :agency-count (count agencies)
     :note (str "所有者 " (count ks) " 件中 " (count covered)
                " 件に窓口を収録。未収録は掲出不可ではなく未調査。")}))

(defn candidate-agencies-for
  "管轄 → その地域に区域を持つ事業者を扱える代理店。所有者が確定していない
  柱の**問い合わせ先候補**であって、その柱の所有者を主張するものではない。"
  [jurisdiction]
  (when-let [c (area/candidates jurisdiction)]
    (let [as (->> (:owner/candidates c)
                  (mapcat agencies-for)
                  distinct
                  (sort-by (comp name :agency/id))
                  vec)]
      (assoc c :agencies as))))

(defn contact-route
  "柱 1 本 → 申込ルート。`denchu.order` が inquiry を組むときの唯一の入口。

  所有者が確定していれば `:routable`。確定していなくても、柱の管轄
  （`:pole/jurisdiction`）が分かっていれば区域から**候補**を出して
  `:candidate-by-area` を返す —— 所有者はこの問い合わせで確定するのが実務。
  管轄も無ければ `:unknown-owner`。**どの経路でも所有者を推測しない。**"
  [{:keys [pole/owner pole/id pole/jurisdiction]}]
  (let [as (agencies-for owner)]
    (cond
      (and (= owner :unknown) (seq (:agencies (candidate-agencies-for jurisdiction))))
      (let [c (candidate-agencies-for jurisdiction)]
        {:route/status :candidate-by-area
         :route/pole-id id
         :route/jurisdiction jurisdiction
         :route/owner-candidates (:owner/candidates c)
         :route/boundary? (:boundary? c)
         :route/boundary-note (:boundary-note c)
         :route/agencies (mapv (fn [a] (select-keys a [:agency/id :agency/legal-name
                                                       :agency/sells-poles-of
                                                       :agency/contact :agency/source-url
                                                       :agency/as-of]))
                               (:agencies c))
         :route/next-step "候補代理店に『この座標の柱は御社の設備か』を照会して所有者を確定する"
         :route/caveat "候補は区域から出た制度的事実。この柱の所有者を主張するものではない。"})

      (= owner :unknown)
      {:route/status :unknown-owner
       :route/pole-id id
       :route/jurisdiction jurisdiction
       :route/next-step (if jurisdiction
                          (str "管轄 " jurisdiction " が denchu.area に未収録 — 区域を調べて追加する")
                          "柱に管轄 (:pole/jurisdiction) が付いていない — survey の area 宣言を確認する")}

      (empty? as)
      {:route/status :no-agency-recorded
       :route/pole-id id
       :route/owner owner
       :route/next-step (str (get owners owner (name owner))
                             " の電柱広告窓口を調査して denchu.media/agencies に追加する")}

      :else
      {:route/status :routable
       :route/pole-id id
       :route/owner owner
       :route/agencies (mapv (fn [a] (select-keys a [:agency/id :agency/legal-name
                                                     :agency/contact :agency/source-url
                                                     :agency/as-of]))
                             as)})))

(defn agency-summary
  "人が読む一行要約。UI ではなく監査ログ向け。"
  [agency-id]
  (when-let [a (get agencies agency-id)]
    (str (:agency/legal-name a)
         " / 対応柱: " (str/join "," (map name (sort (:agency/sells-poles-of a))))
         " / 出典: " (:agency/source-url a)
         " (" (:agency/as-of a) ")")))
