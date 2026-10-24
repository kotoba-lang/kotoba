(ns denchu.datoms
  "柱・面・代理店・見積を **datom 面** の entity map に射影する。

  出力は `manifest/edn-query.cljs` が読む `*.datoms.edn` の形（entity map の
  vector）で、`:source/dataset \"denchu-inventory\"` はローダ側が付ける。
  結合キーの設計:

  - `:pole/owner` は `:agency/sells-poles-of` と、`:agency/id` は
    `:route/agency-id` と文字列一致で join する（datascript.js は
    `:db.type/ref` を解決しないので、面をまたぐ結合は値一致で作る —
    lei-tos / yabai / kakekomi と同型）。
  - `:pole/id` が柱側の安定キー。survey を再実行しても座標が同じなら同じ id。

  **カバレッジ entity を必ず 1 件出す。** 索引を引いて出なかったことが
  『その柱は存在しない』の証拠に使われるのを防ぐため — concept 索引が
  `:concept/coverage` を持つのと同じ理由。"
  (:require [denchu.media :as media]
            [denchu.slot :as slot]))

(defn pole->entity
  "柱 → datom entity。観測の生データは blob 化せず件数と source だけを持つ
  （原本は survey の evidence journal 側にある）。"
  [pole]
  (cond-> {:pole/id (:pole/id pole)
           :pole/lat (:pole/lat pole)
           :pole/lon (:pole/lon pole)
           :pole/kind (name (:pole/kind pole))
           :pole/owner (name (:pole/owner pole))
           :pole/confidence (:pole/confidence pole)
           :pole/sources (:pole/sources pole)
           :pole/observation-count (count (:pole/observations pole))
           :pole/ad-eligible (name (:pole/ad-eligible pole))
           ;; :pole/routable は「所有者が確定していて窓口も分かる」だけを真にする。
           ;; 区域からの候補は別属性 :pole/route-status に出す —— 候補を routable に
           ;; 畳むと、所有者未確定の柱が確定済みとして数えられる。
           :pole/routable (media/routable? (:pole/owner pole))
           :pole/route-status (name (:route/status (media/contact-route pole)))}
    (:pole/owner-evidence pole) (assoc :pole/owner-evidence (:pole/owner-evidence pole))
    (:pole/jurisdiction pole) (assoc :pole/jurisdiction (:pole/jurisdiction pole))
    (:pole/survey-area pole) (assoc :pole/survey-area (:pole/survey-area pole))))

(defn agency->entity
  [a]
  {:agency/id (name (:agency/id a))
   :agency/legal-name (:agency/legal-name a)
   :agency/sells-poles-of (vec (sort (map name (:agency/sells-poles-of a))))
   :agency/products (vec (sort (map name (:agency/products a))))
   :agency/contact-form (get-in a [:agency/contact :form-url])
   :agency/service-url (get-in a [:agency/contact :service-url])
   :agency/tel (get-in a [:agency/contact :tel])
   :agency/source-url (:agency/source-url a)
   :agency/as-of (:agency/as-of a)})

(defn slot-kind->entity
  [k]
  (let [s (slot/describe k)]
    {:slot-kind/id (name k)
     :slot-kind/name-ja (:slot/name-ja s)
     :slot-kind/panels (:slot/panels s)
     :slot-kind/overhangs-road (:slot/overhangs-road? s)
     :slot-kind/source-url (:slot/source-url s)
     :slot-kind/as-of (:slot/as-of s)}))

(defn coverage->entity
  "この shard が何を見て何を見ていないかの申告。数え上げの分母になる。"
  [{:keys [poles areas sources rejected generated-at]}]
  (let [cov (media/coverage)]
    {:denchu.coverage/poles (count poles)
     :denchu.coverage/areas (vec areas)
     :denchu.coverage/sources (vec (sort (map name sources)))
     :denchu.coverage/rejected-observations rejected
     :denchu.coverage/owners-known (:owners-known cov)
     :denchu.coverage/owners-routable (count (:covered cov))
     :denchu.coverage/owners-unrouted (vec (map name (:uncovered cov)))
     :denchu.coverage/poles-with-unknown-owner
     (count (filter #(= :unknown (:pole/owner %)) poles))
     :denchu.coverage/poles-candidate-routable
     (count (filter #(= :candidate-by-area (:route/status (media/contact-route %))) poles))
     :denchu.coverage/poles-routable
     (count (filter #(= :routable (:route/status (media/contact-route %))) poles))
     :denchu.coverage/generated-at generated-at
     :denchu.coverage/note
     (str "この shard は列挙した survey area の中だけを見ている。"
          "面に無い柱は『存在しない』ではなく『まだ調べていない』。"
          "掲出可否 (:pole/ad-eligible) は全件 unknown から始まる —— "
          "所有者/代理店の回答だけがそれを動かせる。")}))

(defn catalog-shard
  "代理店と面種別の**静的カタログ**。survey 面とは別ファイルに出す。

  同じ内容を area ごとの shard に重複させると、面をまたいで数えたときに
  代理店が area 数だけ増えて見える（datom 面には upsert キーが無く、
  ローダは entity を素朴に足すため）。分けるのは重複を避けるためであって、
  join を分断するためではない —— どちらも同じ `denchu-inventory` dataset に
  入るので `:pole/owner` ↔ `:agency/sells-poles-of` は従来どおり join できる。"
  []
  (vec (concat
        (map agency->entity (sort-by (comp name :agency/id) (vals media/agencies)))
        (map slot-kind->entity (sort (keys slot/slot-kinds))))))

(defn inventory-shard
  "1 area 分の survey 結果 → `*.datoms.edn` に書ける entity map の vector。
  柱とカバレッジだけを持つ（カタログは `catalog-shard`）。"
  [{:keys [poles areas sources rejected generated-at]}]
  (vec (concat
        (map pole->entity (sort-by :pole/id poles))
        [(coverage->entity {:poles poles :areas areas :sources sources
                            :rejected (or rejected 0)
                            :generated-at generated-at})])))
