(ns org-openstreetmap-overpass.core
  "OpenStreetMap の Overpass API に対する **純粋な** クエリ組み立てと応答正規化。

  この ns は I/O を持たない。ネットワークは `org-openstreetmap-overpass.fetch`
  （nbb）が担い、ここは『どの QL を投げるか』『返ってきた JSON をどう読むか』
  だけを決める。分けている理由は、クエリの正しさをネットワーク無しで検査
  できるようにするため。

  電柱に対応する OSM のタグは 1 つではない（実測されている実務差）:

    power=pole            配電柱。日本の電柱の大半はこれ
    man_made=utility_pole 電力/通信を問わない柱として使われることがある
    power=tower           送電鉄塔。電柱ではないので既定では引かない
    man_made=street_lamp  街路灯。電柱ではないが誤マッピングが実在するため
                          `:street-light` として**別 kind で**引ける

  `operator` タグがあれば所有者が分かるが、**多くの柱には付いていない**。
  付いていないことを『所有者不明』として持ち上げるのがこの ns の仕事で、
  地域から推測して埋めることはしない。"
  (:require [kotoba.lang.text :as str]))

(def default-endpoint
  "公開エンドポイント。Overpass API 自体は overpass-api.de で運用されるが、
  データとタグ体系の authority は openstreetmap.org（repo 名の由来）。"
  "https://overpass-api.de/api/interpreter")

(def mirrors
  ["https://overpass-api.de/api/interpreter"
   "https://overpass.kumi.systems/api/interpreter"])

(def pole-selectors
  "kind → OSM タグ選択子。`:street-light` は既定では引かない（`kinds` で明示）。"
  {:utility-pole [["power" "pole"] ["man_made" "utility_pole"]]
   :pole [["man_made" "mast"]]
   :street-light [["highway" "street_lamp"]]})

(def default-kinds [:utility-pole])

(defn bbox-str
  "Overpass の bbox は (south,west,north,east)。GeoJSON の順とは違うので
  ここで一度だけ変換し、呼び出し側に順序を覚えさせない。"
  [{:keys [south west north east]}]
  (str south "," west "," north "," east))

(defn valid-bbox? [{:keys [south west north east]}]
  (and (number? south) (number? west) (number? north) (number? east)
       (< south north) (< west east)
       (<= -90 south 90) (<= -90 north 90)
       (<= -180 west 180) (<= -180 east 180)))

(defn- quote-escape
  "Overpass QL の値は二重引用符で囲む。値に `\"` が入ると節が閉じるので落とす
  （エスケープして通すのではなく **拒否する** —— タグ値に引用符が要る検索は
  この repo が今日まで一度も要求されておらず、通す実装は検査の無い経路になる）。"
  [v]
  (let [v (str v)]
    (when (str/includes? v "\"")
      (throw (ex-info "quote in selector value" {:value v})))
    v))

(defn selector->clause
  "選択子 1 つ → Overpass QL の 1 節。**3 つの形を取る**:

    [\"power\" \"pole\"]                 [\"power\"=\"pole\"]      値が決まっている
    [\"shop\"]                          [\"shop\"]              **キーが在るだけでよい**
    [\"amenity\" {:any-of [\"cafe\" \"bar\"]}]  [\"amenity\"~\"^(cafe|bar)$\"]  値の集合

  キー存在形と集合形は、値が数百ある key（`shop` は OSM で 500 以上）を
  1 節で引くためにある。値ごとに節を並べると、クエリが数百行になり
  Overpass の共有インフラに対して無作法で、しかも**表に無い新しい値が
  黙って取りこぼされる**（キー存在形なら取れて、分類器が `nil` を返し、
  `:unclassified` として数に出る）。

  `:any-of` は完全一致の集合として組む（`^(...)$` で囲う）—— 囲わないと
  `cafe` が `cafeteria` にも当たる。生の正規表現が要るときは `{:re \"...\"}`。"
  [prefix sel bbox]
  (let [[k v] (if (vector? sel) sel [sel nil])
        k (quote-escape k)]
    (cond
      (nil? v) (str "  " prefix "[\"" k "\"](" bbox ");")
      (string? v) (str "  " prefix "[\"" k "\"=\"" (quote-escape v) "\"](" bbox ");")
      (and (map? v) (seq (:any-of v)))
      (str "  " prefix "[\"" k "\"~\"^(" (str/join "|" (map quote-escape (:any-of v))) ")$\"](" bbox ");")
      (and (map? v) (:re v))
      (str "  " prefix "[\"" k "\"~\"" (quote-escape (:re v)) "\"](" bbox ");")
      :else (throw (ex-info "unsupported selector" {:selector sel})))))

(defn ql
  "bbox + 選択子 → Overpass QL。`out:json` 固定、`timeout` は明示。

  **選択子は呼び出し側が渡す。** タクソノミーはこの repo の持ち物ではない
  （屋外広告物の媒体分類は `kotoba-lang/okugai` が正本で、そちらの
  `okugai.medium/osm-selectors` が `[[tag value] ...]` を返す。事業者の
  業種分類は `cloud-itonami/eigyo-list` の `eigyo-list.crosswalk`）。`:kinds` は
  電柱だけを引きたい呼び出し側のための短縮形。

  要素の範囲は 3 通り:

    既定        node だけ
    `:ways?`    node + way（壁面広告や大型看板は way のことがある）
    `:nwr?`     node + way + relation を **1 節**で（`nwr`）

  `:nwr?` が別にあるのは、`way` と `relation` を別々に並べると節数が倍に
  なるからで、Overpass はその 3 つを `nwr` として 1 節で受ける。
  way / relation は座標を持たないので `out center tags;` になる。"
  ([bbox] (ql bbox {}))
  ([bbox {:keys [kinds selectors timeout ways? nwr? meta?]
          :or {kinds default-kinds timeout 60}}]
   (when-not (valid-bbox? bbox)
     (throw (ex-info "invalid bbox" {:bbox bbox})))
   (let [b (bbox-str bbox)
         sels (or (seq selectors)
                  (seq (for [k kinds, sel (get pole-selectors k)] sel)))
         prefixes (cond nwr? ["nwr"] ways? ["node" "way"] :else ["node"])
         clauses (for [p prefixes, sel sels] (selector->clause p sel b))]
     (when (empty? clauses)
       (throw (ex-info "no selectors" {:kinds kinds :selectors selectors})))
     (str "[out:json][timeout:" timeout "];\n"
          "(\n" (str/join "\n" clauses) "\n);\n"
          ;; way / relation を引く場合は中心座標が要る（out center は node には無害）
          ;; `meta?` は version / timestamp を足す（`out … meta` は tags も含む）。
          (cond
            (and meta? (or ways? nwr?)) "out center meta;\n"
            meta? "out meta;\n"
            (or ways? nwr?) "out center tags;\n"
            :else "out body;\n")))))

(defn tags->kind
  "タグ map → kind。どの選択子で引かれたかではなく**タグそのもの**から
  決めるので、複数選択子が同じ node を返しても分類が揺れない。"
  [tags]
  (cond
    (= "pole" (get tags "power")) :utility-pole
    (= "utility_pole" (get tags "man_made")) :utility-pole
    (= "mast" (get tags "man_made")) :pole
    (= "street_lamp" (get tags "highway")) :street-light
    :else nil))

(defn element->observation
  "Overpass の element → 観測。`classify` は tags → 分類キーワードの関数で、
  既定は電柱用の `tags->kind`。**分類器は呼び出し側が渡す** —— 屋外広告物の
  媒体分類は `okugai.medium/osm-tags->medium`。

  `attr` は分類結果を載せるキー（既定 `:obs/kind`、okugai 経路では
  `:obs/medium`）。分類できない element と座標の無い element は `nil`。
  way / relation は `out center` の `center` から座標を取る。

  `out meta` で引いたときは `:obs/osm-version` と `:obs/osm-timestamp` が付く
  （**`user` / `uid` は取らない** —— 誰が編集したかは対象の事実ではなく編集者
  個人の情報で、この観測の用途に要らない）。

  `:types` は受け入れる element type の集合（既定 node / way / relation）。
  relation を既定に入れているのは、除くと **黙って落ちる**（`:unclassified`
  にも入らない type 別の落とし方だった）ため —— 落とすなら数えられる形で。"
  ([el] (element->observation el {}))
  ([{:strs [type id lat lon tags center version timestamp] :as _el}
    {:keys [classify attr types]
     :or {classify tags->kind attr :obs/kind types #{"node" "way" "relation"}}}]
   (let [tags (or tags {})
         k (classify tags)
         [la lo] (cond (and (number? lat) (number? lon)) [lat lon]
                       (map? center) [(get center "lat") (get center "lon")]
                       :else [nil nil])]
     (when (and k (number? la) (number? lo) (types type))
       (cond-> {:obs/source :osm
        :obs/source-id (str type "/" id)
        :obs/lat la
        :obs/lon lo
        attr k
        :obs/tags tags
        :obs/evidence-url (str "https://www.openstreetmap.org/" type "/" id)}
         version (assoc :obs/osm-version version)
         timestamp (assoc :obs/osm-timestamp timestamp))))))

(defn parse-response
  "Overpass の JSON（keyword 化していない string キーの map）→
  `{:observations [...] :unclassified n :raw-count n}`。

  分類できなかった element を**黙って落とさず数える** — 落ちた数が見えないと
  『この地域には対象が無い』と『この地域の対象を読めなかった』が区別できない。

  `opts` は `element->observation` にそのまま渡る（`:classify` / `:attr`）。"
  ([json] (parse-response json {}))
  ([json opts]
  (let [els (get json "elements" [])
        obs (keep #(element->observation % opts) els)]
    {:observations (vec obs)
     :raw-count (count els)
     :unclassified (- (count els) (count obs))
     :generator (get json "generator")
     :osm3s (get json "osm3s")})))

(defn observations-with-operator
  "`operator` タグを持つ観測だけ。所有者を確定できる割合を測るために使う
  （収集率の分母を可視化する目的で、フィルタとしては使わない）。"
  [observations]
  (filterv #(seq (str (get-in % [:obs/tags "operator"] ""))) observations))

(defn operator-coverage
  "所有者タグの充足率。survey が『所有者不明が多い』ことを申告するための値。"
  [observations]
  (let [total (count observations)
        with (count (observations-with-operator observations))]
    {:total total
     :with-operator with
     :without-operator (- total with)
     :ratio (if (pos? total) (/ (double with) total) 0.0)}))
