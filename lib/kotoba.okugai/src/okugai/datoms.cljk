(ns okugai.datoms
  "屋外広告の地点・媒体・規制を **datom 面** の entity map に射影する。

  出力は `manifest/edn-query.cljs` が読む `*.datoms.edn` の形（entity map の
  vector）。`:source/dataset` はローダ側が付ける。

  結合キー（datascript.js は `:db.type/ref` を解決しないので値一致で作る):
  - `:site/medium` ↔ `:medium/id`
  - `:site/operator` ↔ 媒体 repo 側のカタログ（電柱なら `:agency/sells-poles-of`）
  - `:site/id` が地点側の安定キー

  **カバレッジ entity を必ず 1 件出す。** 索引を引いて出なかったことが
  『その地点は存在しない』の証拠に使われるのを防ぐため。"
  (:require [okugai.facts :as facts]
            [okugai.medium :as medium]
            [okugai.operator :as operator]
            [okugai.route :as route]))

(defn site->entity
  [site]
  (cond-> {:site/id (:site/id site)
           :site/lat (:site/lat site)
           :site/lon (:site/lon site)
           :site/medium (name (:site/medium site))
           :site/operator (if (keyword? (:site/operator site))
                            (name (:site/operator site))
                            (str (:site/operator site)))
           :site/confidence (:site/confidence site)
           :site/sources (:site/sources site)
           :site/observation-count (count (:site/observations site))
           :site/ad-eligible (name (:site/ad-eligible site))
           ;; 観測から埋まらないもの。nil のまま出すのではなく「未測定」と明示する
           :site/height-known (some? (:site/height-m site))}
    (:site/operator-raw site) (assoc :site/operator-raw (:site/operator-raw site))
    (:site/operator-evidence site) (assoc :site/operator-evidence (:site/operator-evidence site))
    (:site/height-m site) (assoc :site/height-m (:site/height-m site))
    (:site/jurisdiction site) (assoc :site/jurisdiction (:site/jurisdiction site))
    (:site/survey-area site) (assoc :site/survey-area (:site/survey-area site))
    (:site/route-status site) (assoc :site/route-status (name (:site/route-status site)))
    (seq (:site/owner-candidates site)) (assoc :site/owner-candidates (:site/owner-candidates site))
    (seq (:site/agencies site)) (assoc :site/agencies (:site/agencies site))
    (seq (:site/operator-candidates site))
    (assoc :site/operator-candidates (:site/operator-candidates site))))

(defn operator->entity
  [o]
  {:operator/id (name (:operator/id o))
   :operator/legal-name (:operator/legal-name o)
   :operator/hq (:operator/hq o)
   :operator/jurisdictions (vec (sort (:operator/jurisdictions o)))
   :operator/media (vec (sort (map name (:operator/media o))))
   :operator/kind (name (:operator/kind o))
   :operator/site-url (get-in o [:operator/contact :site-url])
   :operator/source-urls (vec (:operator/source-urls o))
   :operator/as-of (:operator/as-of o)
   :operator/note (:operator/note o)})

(defn medium->entity
  [id]
  (let [m (medium/describe id)]
    {:medium/id (name id)
     :medium/name-ja (:medium/name-ja m)
     :medium/owner-kind (name (:medium/owner-kind m))
     :medium/attached-to (name (:medium/attached-to m))
     :medium/observable (boolean (medium/observable-media id))
     :medium/osm-tags (mapv (fn [[k v]] (str k "=" v)) (:medium/osm m))
     :medium/mapillary-objects (vec (:medium/mapillary m))
     :medium/regulatory-triggers (vec (sort (map name (:medium/regulatory-triggers m))))
     :medium/domain-repo (:medium/domain-repo m)
     :medium/note (:medium/note m)}))

(defn regulation->entity
  "instrument → entity。**法域を必ず持たせる** —— これが無いと日本の建築基準法88条と
  米国の HBA が同じ面で区別できなくなる。"
  [iso3 id]
  (let [r (facts/describe-regulation iso3 id)]
    (cond-> {:regulation/id (name id)
             :regulation/jurisdiction iso3
             :regulation/category (name (:reg/category r))
             :regulation/decision (name (:reg/decision r))
             :regulation/name (:reg/name r)
             :regulation/authority (:reg/authority r)
             :regulation/legal-basis (:reg/legal-basis r)
             :regulation/evidence-key (:reg/evidence-key r)
             :regulation/source-urls (vec (:reg/source-urls r))}
      (:reg/note r) (assoc :regulation/note (:reg/note r))
      (:reg/penalty r) (assoc :regulation/penalty (:reg/penalty r))
      (:reg/zone r) (assoc :regulation/zone (name (:reg/zone r)))
      (get-in r [:reg/threshold :height-m])
      (assoc :regulation/threshold-height-m (get-in r [:reg/threshold :height-m]))
      (get-in r [:reg/threshold :area-m2])
      (assoc :regulation/threshold-area-m2 (get-in r [:reg/threshold :area-m2]))
      (get-in r [:reg/threshold :corridor-distance-ft])
      (assoc :regulation/threshold-corridor-ft
             (get-in r [:reg/threshold :corridor-distance-ft])))))

(defn jurisdiction->entity
  [iso3]
  (let [j (facts/requirements iso3)]
    {:jurisdiction/iso3 iso3
     :jurisdiction/name (:name j)
     :jurisdiction/permit-level (name (:permit-level j))
     :jurisdiction/instruments (count (facts/regulations-for iso3))
     :jurisdiction/note (:note j)}))

(defn catalog-shard
  "媒体タクソノミーと規制カタログの**静的カタログ**。survey 面とは別ファイルに出す
  （area shard に混ぜると area 数だけ重複する）。同じ dataset に入るので join は
  従来どおりできる。"
  []
  (vec (concat (map medium->entity (sort (keys medium/media)))
               (map operator->entity (map val (sort-by key operator/operators)))
               (map jurisdiction->entity (sort (keys facts/regulations)))
               (for [iso3 (sort (keys facts/regulations))
                     id (sort (keys (facts/regulations-for iso3)))]
                 (regulation->entity iso3 id))
               ;; 未収録のうち人口の大きい法域も entity にする —— 「N 法域収録」だけ
               ;; 見せると世界を覆っているように読めるため、欠けている側も引けるようにする。
               (for [e (:entries facts/uncovered-large-jurisdictions)]
                 {:jurisdiction/iso3 (:iso3 e)
                  :jurisdiction/name (:name e)
                  :jurisdiction/covered false
                  :jurisdiction/population (:population e)
                  :jurisdiction/population-source (:source-url facts/uncovered-large-jurisdictions)
                  :jurisdiction/population-as-of (:as-of facts/uncovered-large-jurisdictions)
                  :jurisdiction/note "人口 1 億超だが okugai.facts に未収録。spec-basis 無し。"}))))

(defn coverage->entity
  [{:keys [sites areas sources rejected generated-at media-requested source-errors]}]
  (let [mc (medium/coverage)]
    {:okugai.coverage/sites (count sites)
     :okugai.coverage/areas (vec areas)
     :okugai.coverage/sources (vec (sort (map name sources)))
     :okugai.coverage/media-requested (vec (sort (map name (or media-requested []))))
     :okugai.coverage/sites-by-medium (pr-str (into (sorted-map) (dissoc (frequencies (map (comp name :site/medium) sites)) nil)))
     :okugai.coverage/rejected-observations (or rejected 0)
     ;; **失敗した source を数える。** 0 件が「調べて無かった」なのか
     ;; 「調べられなかった」なのかは、これが無いと台帳から区別できない。
     :okugai.coverage/source-errors (count (or source-errors []))
     :okugai.coverage/sources-failed (vec (sort (map (comp name :source) (or source-errors []))))
     :okugai.coverage/partial (boolean (seq source-errors))
     :okugai.coverage/media-known (:media mc)
     :okugai.coverage/media-observable (:observable mc)
     :okugai.coverage/media-unobservable (vec (:unobservable mc))
     :okugai.coverage/sites-with-unknown-operator
     (count (filter #(= :unknown (:site/operator %)) sites))
     :okugai.coverage/sites-with-known-height
     (count (filter :site/height-m sites))
     :okugai.coverage/sites-by-route-status
     (pr-str (into (sorted-map)
                   (map (fn [[k v]] [(name (or k :unresolved)) v]))
                   (frequencies (map :site/route-status sites))))
     :okugai.coverage/sites-reachable
     (count (filter route/reachable? sites))
     :okugai.coverage/generated-at generated-at
     :okugai.coverage/note
     (str "この shard は列挙した survey area の中で、要求した媒体だけを見ている。"
          "面に無い地点は『存在しない』ではなく『まだ調べていない』。"
          "屋上看板・SA/PA 内広告は観測タグを持たないので survey では決して出ない —— "
          "媒体社カタログか現地調査からしか入らない。"
          "高さは観測から埋まらないので建築基準法88条の要否は既定で undetermined。")}))

(defn inventory-shard
  "1 area 分の survey 結果 → `*.datoms.edn` に書ける entity map の vector。"
  [{:keys [sites areas sources rejected generated-at media-requested source-errors]}]
  (vec (concat
        (map site->entity (sort-by :site/id sites))
        [(coverage->entity {:sites sites :areas areas :sources sources
                            :rejected (or rejected 0) :generated-at generated-at
                            :media-requested media-requested
                            :source-errors source-errors})])))
