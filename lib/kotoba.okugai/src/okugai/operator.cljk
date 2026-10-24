(ns okugai.operator
  "屋外広告の**媒体社カタログ** —— 実際にその市場で在庫を売っている事業者。

  `denchu.media` が電柱の指定代理店を持つのと同じ役割を、電柱以外の媒体について
  果たす。これが無いと、地点が見つかっても『誰に買いに行くか』が決まらない
  （実測: 2026-08-04 時点で 3,262 地点のうち照会先が立つのは電柱と、観測に
  `operator` タグがある分だけだった）。

  ## 候補であって在庫ではない

  ここに載るのは『この法域でこの媒体を売っている事業者』であって、
  **特定の地点を持っているという主張ではない**。JCDecaux が Paris の street
  furniture 権を持つことと、ある 1 本の円柱が JCDecaux のものかは別の事実。
  だから返すのは `:candidate-by-catalog` —— `denchu.area` の
  `:candidate-by-area` と同じ性格で、確定は照会でしかできない。

  ## 収録は薄い。薄さを申告する

  世界の OOH 市場は数千社の地場事業者がいて、ここに載るのは公開情報で確認できた
  大手だけ。`coverage` は法域あたり何社かを返す —— 「候補が出た」を
  「市場を網羅した」と読ませないため。"
  (:require [kotoba.lang.text :as str]))

(def operators
  "事業者 id → 実体。`:operator/jurisdictions` は**公開情報で確認できた**主要市場で、
  事業展開の全量ではない。`:operator/media` は扱う媒体（`okugai.medium` の id）。"
  {:jcdecaux
   {:operator/id :jcdecaux
    :operator/legal-name "JCDecaux SE"
    :operator/hq "FRA"
    :operator/jurisdictions #{"FRA" "DEU" "JPN" "CHN" "IND" "ARE" "USA"}
    :operator/media #{:column :poster-box :screen :transit-shelter :billboard}
    :operator/kind :street-furniture-concession
    :operator/contact {:site-url "https://www.jcdecaux.com/"}
    :operator/note "street furniture の自治体 concession が中核。Paris の street-furniture 権は 2047 年まで。**concession 型なので、その都市の該当媒体はほぼこの 1 社に集まる。**"
    :operator/source-urls ["https://www.mordorintelligence.com/industry-reports/digital-ooh-market"]
    :operator/as-of "2026-08-04"}

   :clear-channel-outdoor
   {:operator/id :clear-channel-outdoor
    :operator/legal-name "Clear Channel Outdoor Holdings, Inc."
    :operator/hq "USA"
    :operator/jurisdictions #{"USA"}
    :operator/media #{:billboard :screen :poster-box :transit-shelter}
    :operator/kind :inventory-owner
    :operator/contact {:site-url "https://www.clearchanneloutdoor.com/"}
    :operator/source-urls ["https://www.mordorintelligence.com/industry-reports/digital-ooh-market"]
    :operator/as-of "2026-08-04"}

   :lamar
   {:operator/id :lamar
    :operator/legal-name "Lamar Advertising Company"
    :operator/hq "USA"
    :operator/jurisdictions #{"USA"}
    :operator/media #{:billboard :screen}
    :operator/kind :inventory-owner
    :operator/contact {:site-url "https://www.lamar.com/"}
    :operator/note "米国の traditional / digital ビルボードを全国規模で保有。"
    :operator/source-urls ["https://www.mordorintelligence.com/industry-reports/digital-ooh-market"]
    :operator/as-of "2026-08-04"}

   :outfront
   {:operator/id :outfront
    :operator/legal-name "OUTFRONT Media Inc."
    :operator/hq "USA"
    :operator/jurisdictions #{"USA"}
    :operator/media #{:billboard :screen :transit-shelter}
    :operator/kind :inventory-owner
    :operator/contact {:site-url "https://www.outfront.com/"}
    :operator/source-urls ["https://www.mordorintelligence.com/industry-reports/digital-ooh-market"]
    :operator/as-of "2026-08-04"}

   :stroeer
   {:operator/id :stroeer
    :operator/legal-name "Ströer SE & Co. KGaA"
    :operator/hq "DEU"
    :operator/jurisdictions #{"DEU"}
    :operator/media #{:billboard :poster-box :column :screen :transit-shelter}
    :operator/kind :inventory-owner
    :operator/contact {:site-url "https://www.stroeer.de/"}
    :operator/source-urls ["https://www.mordorintelligence.com/industry-reports/digital-ooh-market"]
    :operator/as-of "2026-08-04"}

   :focus-media
   {:operator/id :focus-media
    :operator/legal-name "Focus Media Information Technology Co., Ltd."
    :operator/hq "CHN"
    :operator/jurisdictions #{"CHN"}
    :operator/media #{:screen}
    :operator/kind :inventory-owner
    :operator/contact {:site-url "https://www.focusmedia.cn/"}
    :operator/note "ビル内・エレベータの digital screen が中核で、路上の billboard 主体ではない。"
    :operator/source-urls ["https://www.mordorintelligence.com/industry-reports/digital-ooh-market"]
    :operator/as-of "2026-08-04"}

   :nexco-west-communications
   {:operator/id :nexco-west-communications
    :operator/legal-name "NEXCO西日本コミュニケーションズ株式会社"
    :operator/hq "JPN"
    :operator/jurisdictions #{"JPN"}
    :operator/media #{:expressway-service-area}
    :operator/kind :highway-concession
    :operator/contact {:media-kit-url "https://www.w-nexco-coms.co.jp/img/common/file/w-nexco-media.pdf"}
    :operator/note "高速道路 SA/PA 内の媒体。**観測では決して見つからない媒体（`:expressway-service-area`）に対する唯一の入口**なので、カタログが無いと到達不能だった。"
    :operator/source-urls ["https://www.w-nexco-coms.co.jp/img/common/file/w-nexco-media.pdf"]
    :operator/as-of "2026-08-04"}})

(defn describe [id] (get operators id))

(defn candidates-for
  "`{:jurisdiction \"FRA\" :medium :column}` → 候補事業者（実体の vector）。

  **候補であって在庫ではない。** その法域でその媒体を売っている事業者、という
  以上の主張はしない。空なら『売り手がいない』ではなく『カタログに未収録』。"
  [{:keys [jurisdiction medium]}]
  (->> (vals operators)
       (filter (fn [o] (and (contains? (:operator/jurisdictions o) jurisdiction)
                            (or (nil? medium) (contains? (:operator/media o) medium)))))
       (sort-by (comp name :operator/id))
       vec))

(defn catalogued?
  [placement]
  (boolean (seq (candidates-for placement))))

(defn coverage
  "収録の薄さを申告する。法域あたり何社載っているか。"
  []
  (let [by-j (reduce (fn [acc o]
                       (reduce (fn [a j] (update a j (fnil inc 0)))
                               acc (:operator/jurisdictions o)))
                     {} (vals operators))]
    {:operators (count operators)
     :jurisdictions (count by-j)
     :by-jurisdiction (into (sorted-map) by-j)
     :note (str "収録 " (count operators) " 社 / " (count by-j) " 法域。"
                "世界の OOH 市場には数千社の地場事業者がいて、ここに載るのは公開情報で"
                "確認できた大手だけ。**候補が出たことを市場を網羅したと読まない。**"
                "空の法域は『売り手がいない』ではなく『未収録』。")}))

(defn summary [id]
  (when-let [o (describe id)]
    (str (:operator/legal-name o)
         " / 市場: " (str/join "," (sort (:operator/jurisdictions o)))
         " / 媒体: " (str/join "," (map name (sort (:operator/media o))))
         " / 出典: " (first (:operator/source-urls o)) " (" (:operator/as-of o) ")")))
