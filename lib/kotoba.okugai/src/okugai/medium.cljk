(ns okugai.medium
  "屋外広告物（physical / out-of-home）の**媒体タクソノミー**。

  `denchu`（電柱広告）はこの中の 1 媒体でしかない。ここが持つのは
  「どんな物理媒体があり、それぞれ**どの観測タグで見つかり**、**どの法令が
  効くか**」で、個々の媒体社・料金・在庫は媒体ごとの repo（`denchu` 等）に置く。

  ## 観測タグは実測に基づく

  OSM の `advertising=*` は実在する値だけを載せる。実測（2026-08-04、都心 bbox
  35.65,139.68〜35.72,139.78）で 46 件が返り、内訳は board 25 / billboard 9 /
  screen 7 / poster_box 2 / column 1 / totem 1 / sign 1 だった。**推測した値を
  混ぜない** —— 存在しないタグで引くと空応答が『媒体が無い』に見える。

  ## 規制トリガは**普遍カテゴリ**で、法令名ではない

  各国の法令名を共通語彙にすると「ある国の法体系が世界のモデル」になってしまう。
  媒体が持つのは**どんな規制カテゴリに触れうるか**だけで、そのカテゴリを実際に
  どの法令が担うかは `okugai.facts` が法域ごとに持つ:

  - `:display-permit`    掲出そのものの許可（JP 屋外広告物条例 / FR déclaration ou
                         autorisation préalable / DE Baugenehmigung / CN 设置规划と
                         审批 / IN 市自治体の NOC / SA Balady / AE Dubai Municipality
                         permit / US 州 DOT + 地方 zoning）
  - `:road-space`        道路上空・路上に出る（JP 道路占用/道路使用 ほか）
  - `:structural`        構造・建築の審査（JP 建築基準法88条の4m超工作物確認と
                         64条の防火地域 / DE Werbeanlage は bauliche Anlage /
                         IN structural stability certificate）
  - `:highway-corridor`  幹線道路の沿線・区域（US Highway Beautification Act の
                         right-of-way 660 ft / JP 高速道路沿道ガイドライン /
                         IN 国道 right-of-way 上の禁止）

  **高さは媒体種別からは決まらない。** 同じ `:billboard` でも 3m と 6m がある。
  だから `:regulatory-triggers` は『**条件付きで効きうる**規制』の集合であって、
  『必ず要る』ではない —— 実際の要否は `okugai.facts/applicable` に寸法と場所を
  渡して判定する。"
  (:require [kotoba.lang.text :as str]))

(def media
  "媒体 id → 定義。`:osm` は OSM のタグ、`:mapillary` は Mapillary の object_value
  （どちらも実在する値のみ）。`:owner-kind` は誰が持っているかの類型で、確定では
  なく調査の出発点。"
  {:utility-pole
   {:medium/id :utility-pole
    :medium/name-ja "電柱広告（巻付・袖）"
    :medium/osm [["power" "pole"] ["man_made" "utility_pole"]]
    :medium/mapillary ["object--support--utility-pole" "object--support--pole"]
    :medium/owner-kind :utility          ; 電力・通信事業者
    :medium/attached-to :pole
    :medium/regulatory-triggers #{:display-permit :road-space}
    :medium/domain-repo "kotoba-lang/denchu"
    :medium/note "販売は所有者の指定代理店経由。区域から候補所有者を導ける唯一の媒体。"}

   :billboard
   {:medium/id :billboard
    :medium/name-ja "野立看板・ビルボード"
    :medium/osm [["advertising" "billboard"]]
    :medium/mapillary ["object--sign--advertisement"]
    :medium/owner-kind :landowner-or-operator
    :medium/attached-to :ground
    :medium/regulatory-triggers #{:display-permit :structural :highway-corridor}
    :medium/note "自立式。高さ4m超なら工作物確認申請。高速道路沿道は禁止区域指定がありうる。"}

   :board
   {:medium/id :board
    :medium/name-ja "広告板（小型）"
    :medium/osm [["advertising" "board"]]
    :medium/mapillary ["object--sign--advertisement" "object--sign--store"]
    :medium/owner-kind :landowner-or-operator
    :medium/attached-to :ground
    :medium/regulatory-triggers #{:display-permit}
    :medium/note "実測で最も多い値（都心 bbox 46 件中 25 件）。小型なので 88 条は通常かからない。"}

   :wall
   {:medium/id :wall
    :medium/name-ja "壁面広告"
    :medium/osm [["advertising" "wall_painting"]]
    :medium/mapillary ["object--banner" "object--sign--store"]
    :medium/owner-kind :building-owner
    :medium/attached-to :building
    :medium/regulatory-triggers #{:display-permit :structural}
    :medium/note "建物所有者の承諾が前提。突出すれば道路占用も。"}

   :rooftop
   {:medium/id :rooftop
    :medium/name-ja "屋上看板・広告塔"
    ;; OSM に固有タグが無く、Mapillary の点検出でも『屋上にある』は判定できない
    ;; （同じ object--sign--advertisement が野立看板にも付く）。observation では
    ;; 見つからない媒体として明示する —— 誤って billboard として拾うより良い。
    :medium/osm []
    :medium/mapillary []
    :medium/owner-kind :building-owner
    :medium/attached-to :building
    :medium/regulatory-triggers #{:display-permit :structural}
    :medium/note "広告塔部分が高さ4m超なら工作物確認申請。防火地域の屋上は 64 条で不燃材料。**観測では見つからない** —— 媒体社カタログか現地調査からしか入らない。"}

   :screen
   {:medium/id :screen
    :medium/name-ja "屋外ビジョン・デジタルサイネージ"
    :medium/osm [["advertising" "screen"]]
    :medium/mapillary ["object--sign--advertisement"]
    :medium/owner-kind :media-operator
    :medium/attached-to :building
    :medium/regulatory-triggers #{:display-permit :structural}
    :medium/note "運営会社が明確なことが多く、媒体社への直接照会が成立しやすい。"}

   :poster-box
   {:medium/id :poster-box
    :medium/name-ja "ポスターボックス・掲示板"
    :medium/osm [["advertising" "poster_box"]]
    :medium/mapillary ["object--sign--information"]
    :medium/owner-kind :municipality-or-operator
    :medium/attached-to :ground
    :medium/regulatory-triggers #{:display-permit :road-space}
    :medium/note "自治体設置のものは公共掲示板で広告媒体ではない場合がある（operator を見る）。"}

   :column
   {:medium/id :column
    :medium/name-ja "円柱広告（アドピラー）"
    :medium/osm [["advertising" "column"]]
    :medium/mapillary ["object--banner"]
    :medium/owner-kind :media-operator
    :medium/attached-to :ground
    :medium/regulatory-triggers #{:display-permit :road-space}}

   :totem
   {:medium/id :totem
    :medium/name-ja "トーテム型サイン"
    :medium/osm [["advertising" "totem"]]
    :medium/mapillary ["object--sign--store"]
    :medium/owner-kind :landowner-or-operator
    :medium/attached-to :ground
    :medium/regulatory-triggers #{:display-permit :structural}}

   :sign
   {:medium/id :sign
    :medium/name-ja "広告サイン"
    :medium/osm [["advertising" "sign"]]
    :medium/mapillary ["object--sign--advertisement" "object--sign--store"]
    :medium/owner-kind :landowner-or-operator
    :medium/attached-to :ground
    :medium/regulatory-triggers #{:display-permit}}

   :banner
   {:medium/id :banner
    :medium/name-ja "バナー・幕"
    :medium/osm [["advertising" "flag"] ["advertising" "tarp"]]
    :medium/mapillary ["object--banner"]
    :medium/owner-kind :landowner-or-operator
    :medium/attached-to :building
    :medium/regulatory-triggers #{:display-permit}
    :medium/note "多くの条例が電柱・街路灯柱への広告旗を禁止物件として列挙する —— 掲出場所で可否が変わる。"}

   :transit-shelter
   {:medium/id :transit-shelter
    :medium/name-ja "バス停シェルター広告"
    ;; OSM の bus_stop は停留所であって広告媒体ではない。広告面の有無は
    ;; observation では決まらないので選択子を持たせない。
    :medium/osm []
    :medium/mapillary []
    :medium/owner-kind :transit-or-operator
    :medium/attached-to :ground
    :medium/regulatory-triggers #{:display-permit :road-space}
    :medium/note "停留所の位置は OSM にあるが、そこに広告面があるかは書かれていない。媒体社カタログからしか入らない。"}

   :expressway-roadside
   {:medium/id :expressway-roadside
    :medium/name-ja "高速道路沿道看板"
    ;; 観測上 :billboard と同一タグで、沿道かどうかは高速道路からの距離でしか
    ;; 決まらない。**独自の選択子を持たせない** —— 持たせると同じ物件が
    ;; billboard と expressway-roadside の 2 件に増える。
    :medium/osm []
    :medium/mapillary []
    :medium/derived-from :billboard
    :medium/owner-kind :landowner-or-operator
    :medium/attached-to :ground
    :medium/regulatory-triggers #{:display-permit :structural :highway-corridor}
    :medium/note "道路区域の外。条例の禁止区域指定・高速道路沿道ガイドラインが上乗せされうる。billboard の後付け分類であって独立に観測できる媒体ではない。"}

   :expressway-service-area
   {:medium/id :expressway-service-area
    :medium/name-ja "高速道路 SA/PA 内広告"
    :medium/osm []                        ; 施設内の媒体は OSM に無い
    :medium/mapillary []
    :medium/owner-kind :expressway-operator
    :medium/attached-to :facility
    :medium/regulatory-triggers #{:highway-corridor}
    :medium/note "道路区域内なので道路管理者（NEXCO 各社）の媒体。屋外広告物条例ではなく媒体社の媒体資料が窓口。**観測では見つからない** —— 媒体社カタログからしか入らない。"}})

(def observable-media
  "OSM または Mapillary のタグで**実際に見つけられる**媒体。
  ここに無い媒体（屋上看板・SA/PA 内）は observation では埋まらず、
  媒体社カタログか現地調査からしか入らない —— その差を隠さないための集合。"
  (->> media
       (filter (fn [[_ m]] (or (seq (:medium/osm m)) (seq (:medium/mapillary m)))))
       (map key) set))

(def unobservable-media
  (into #{} (remove observable-media (keys media))))

(defn describe [id] (get media id))

(defn medium? [id] (contains? media id))

(defn osm-selectors
  "媒体列 → OSM のタグ選択子（重複除去）。"
  [medium-ids]
  (->> medium-ids (mapcat #(:medium/osm (describe %) [])) distinct vec))

(defn osm-tags->medium
  "OSM のタグ map → 媒体 id。どの選択子で引かれたかではなくタグそのもので決める
  ので、複数選択子が同じ node を返しても分類が揺れない。"
  [tags]
  (let [adv (get tags "advertising")]
    (cond
      (= "pole" (get tags "power")) :utility-pole
      (= "utility_pole" (get tags "man_made")) :utility-pole
      (= "billboard" adv) :billboard
      (= "board" adv) :board
      (= "screen" adv) :screen
      (= "poster_box" adv) :poster-box
      (= "column" adv) :column
      (= "totem" adv) :totem
      (= "sign" adv) :sign
      (= "wall_painting" adv) :wall
      (#{"flag" "tarp"} adv) :banner
      :else nil)))

(def mapillary-canonical
  "Mapillary の object_value → **その値を代表させる媒体**。

  Mapillary の点検出は媒体を一意に決めない —— `object--sign--advertisement` は
  野立看板にも屋上看板にも壁面にも付く。だから逆写像は**明示的な表**として持ち、
  各媒体の `:medium/mapillary`（『この媒体を示しうる値』）から導出しない。
  導出にすると並び順という隠れた依存で分類が決まってしまう。"
  {"object--support--utility-pole" :utility-pole
   "object--support--pole" :utility-pole
   "object--sign--advertisement" :billboard
   "object--sign--store" :sign
   "object--sign--information" :poster-box
   "object--banner" :banner})

(defn mapillary-object->medium
  "object_value → 代表媒体。表に無い値は nil（`object--street-light` 等、
  広告媒体でないものはここに来ない）。"
  [object-value]
  (get mapillary-canonical object-value))

(defn triggers [id] (:medium/regulatory-triggers (describe id) #{}))

(defn coverage
  "何媒体を知っていて、そのうち何媒体が観測で見つかるかの申告。"
  []
  {:media (count media)
   :observable (count observable-media)
   :unobservable (vec (sort (map name unobservable-media)))
   :note (str "収録 " (count media) " 媒体のうち観測で見つかるのは "
              (count observable-media) " 媒体。残りは media catalog か現地調査からしか入らない —— "
              "observation に出ないことは『存在しない』ではない。")})

(defn summary [id]
  (when-let [m (describe id)]
    (str (:medium/name-ja m)
         " / OSM: " (if (seq (:medium/osm m))
                      (str/join "," (map (fn [[k v]] (str k "=" v)) (:medium/osm m)))
                      "なし")
         " / 規制: " (str/join "," (map name (sort (:medium/regulatory-triggers m)))))))
