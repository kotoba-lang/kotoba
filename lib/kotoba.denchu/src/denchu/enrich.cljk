(ns denchu.enrich
  "`okugai.site` の地点に**電柱固有の知識**を載せる hook。

  `loop-okugai-survey` は媒体非依存なので、供給区域から候補所有者を導く知識
  （`denchu.area`）をあちらに書けない。survey に渡す `:enrich` 関数がこの境界。

  電柱以外の媒体は素通しする —— この repo は電柱のことしか知らない。"
  (:require [kotoba.lang.text :as str]
            [denchu.media :as media]
            [denchu.pole :as pole]))

(def ^:const medium :utility-pole)

(defn jp-jurisdiction?
  "日本の管轄か。`denchu.area` は ISO 3166-2:JP しか知らない。"
  [j]
  (boolean (and (string? j) (or (= "JPN" j) (str/starts-with? j "JP")))))

(defn operator-resolver
  "`okugai.site/fuse` に渡す解決器。電柱の `operator` 文字列 → 電力/通信事業者の
  キーワード。未知は `:unknown`（推測しない）。

  **電柱以外の媒体では生文字列をそのまま返す** —— 電柱の社名表は電力/通信事業者
  しか知らないので、広告物の設置者名（『株式会社アトレ』等）に当てると全部
  `:unknown` に潰れて、観測から得られた照会先の手がかりを失う。"
  [operator-string med]
  (if (= medium med)
    (pole/operator->owner operator-string)
    operator-string))

(defn- site->pole
  "okugai の site を `denchu.media/contact-route` が読む形に写す。"
  [s]
  {:pole/id (:site/id s)
   :pole/owner (if (keyword? (:site/operator s)) (:site/operator s) :unknown)
   :pole/jurisdiction (:site/jurisdiction s)})

(defn site
  "地点 → 電柱固有の enrichment を載せた地点。

  - `:site/route-status` を `:routable` / `:candidate-by-area` / `:unknown-owner` に
    確定させる（`okugai.route/stamp` の一般則より強い）
  - 候補所有者と候補代理店を地点に残す —— **`:site/operator` は unknown のまま**。
    候補は地点ではなく経路に載る、が `denchu.area` の設計。"
  [s]
  ;; **日本の電柱にしか効かない。** denchu が知っているのは日本の電力/通信事業者と
  ;; 供給区域だけなので、国外の電柱に当てると `:unknown-owner`（denchu の語彙）が
  ;; 付いて、okugai の一般則が出した `:unresolved` を上書きしてしまう。
  (if (or (not= medium (:site/medium s))
          (not (jp-jurisdiction? (:site/jurisdiction s))))
    s
    (let [route (media/contact-route (site->pole s))]
      (cond-> (assoc s :site/route-status (:route/status route))
        (seq (:route/owner-candidates route))
        (assoc :site/owner-candidates (mapv name (:route/owner-candidates route)))

        (seq (:route/agencies route))
        (assoc :site/agencies (mapv (comp name :agency/id) (:route/agencies route)))

        (:route/boundary? route)
        (assoc :site/owner-candidates-boundary true)))))
