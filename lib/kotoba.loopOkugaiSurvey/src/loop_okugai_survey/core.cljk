(ns loop-okugai-survey.core
  "屋外広告物（physical / out-of-home）在庫の継続 survey —
  observe → evaluate → decide → act → record-evidence。

  `loop-*` は continuous orchestrator であって domain truth の持ち主ではない
  （`manifest/repository-rules.edn` `:name-prefix`）。したがってこの ns は:

  - **媒体の定義・法令・出稿の一般則を持たない** → `okugai.*` に委譲
  - **地点の束ね方・信頼度を持たない** → `okugai.site` に委譲
  - **媒体固有の窓口解決を持たない** → 媒体 repo に委譲（電柱なら `denchu`）
  - **API の作法を持たない** → origin 面の 2 repo に委譲

  ここが所有するのは『どの面をどの媒体で見て、何を証跡として残すか』だけ。

  ## 媒体固有の enrichment は hook で受ける

  電柱だけは供給区域から候補所有者を導けるので、所有者未確定でも問い合わせ経路が
  立つ（`denchu.area`）。これは電柱固有の知識なのでこの ns には書かず、
  `:enrich` 関数として渡してもらう。渡されなければ地点はそのまま。

  **カバレッジの申告がこの loop の成果物の一部。** 見た面・見た媒体の外に
  地点が無いのではなく、見ていない。観測タグを持たない媒体（屋上看板・SA/PA 内・
  沿道分類・シェルター）はそもそも survey では決して出ない。"
  (:require [okugai.datoms :as datoms]
            [okugai.medium :as medium]
            [okugai.site :as site]))

(defn area
  "survey 対象面。`:jurisdiction` は ISO 3166-2 相当を**呼び出し側が宣言する** ——
  座標から逆引きして推測しない。"
  [{:keys [id bbox jurisdiction note]}]
  {:area/id id :area/bbox bbox :area/jurisdiction jurisdiction :area/note note})

(def default-media
  "既定で survey する媒体。観測タグを持つものだけ（持たない媒体を並べても
  空振りするだけで『調べたが無かった』という誤読を生む）。"
  (vec (sort medium/observable-media)))

;; ── evaluate ────────────────────────────────────────────────────────

(defn- in-bbox?
  [{:keys [south west north east]} {:keys [site/lat site/lon]}]
  (and (<= south lat north) (<= west lon east)))

(defn stamp-area
  "地点に管轄と survey area を刻む。**座標から逆引きしない** —— survey が宣言した
  area の bbox に入っているかだけを見る。どの area にも入らない地点には付けない。"
  [sites areas]
  (mapv (fn [s]
          (if-let [a (some (fn [a] (when (and (:area/jurisdiction a)
                                              (in-bbox? (:area/bbox a) s))
                                     a))
                           areas)]
            (assoc s :site/jurisdiction (:area/jurisdiction a)
                   :site/survey-area (:area/id a))
            s))
        sites))

(defn evaluate
  "観測列 → 地点列 + 測定値。`:enrich` は地点 1 件 → 地点（媒体 repo の知識を
  載せる）。`:operator-resolver` は `okugai.site/fuse` にそのまま渡す。"
  [observations {:keys [radius-m areas enrich operator-resolver]
                 :or {radius-m 8.0}}]
  (let [{:keys [sites rejected]} (site/fuse observations
                                            {:radius-m radius-m
                                             :operator-resolver operator-resolver})
        sites (stamp-area sites (or areas []))
        sites (if enrich (mapv enrich sites) sites)
        by-source (frequencies (map :obs/source observations))
        multi (count (filter #(> (count (:site/sources %)) 1) sites))
        unknown-op (count (filter #(= :unknown (:site/operator %)) sites))
        route-status (frequencies (map #(or (:site/route-status %) :not-resolved) sites))]
    {:sites sites
     :rejected rejected
     :measurements
     {:observations (count observations)
      :observations-by-source by-source
      :sites (count sites)
      :sites-by-medium (site/by-medium sites)
      :sites-multi-source multi
      :sites-unknown-operator unknown-op
      :sites-with-known-height (count (filter :site/height-m sites))
      :sites-by-route-status route-status
      :rejected-observations (count rejected)}}))

;; ── decide ──────────────────────────────────────────────────────────

(def ^:const default-min-confidence
  "在庫候補として台帳に載せる下限。下回った地点は捨てずに数える —— 消えると
  『調べた結果いなかった』に化ける。"
  0.45)

(defn decide
  "どの地点を在庫候補として採るか。判断は信頼度のみ。所有者不明でも落とさない
  （所有者は後から埋まる。落とすと二度と探されない）。"
  [sites {:keys [min-confidence] :or {min-confidence default-min-confidence}}]
  (let [{accepted true below false} (group-by #(>= (:site/confidence %) min-confidence) sites)]
    {:accepted (vec (or accepted []))
     :below-threshold (vec (or below []))
     :min-confidence min-confidence}))

;; ── act / record-evidence ───────────────────────────────────────────

(defn all-sources-failed?
  "要求した source が全部落ちたか。**このとき shard を書いてはいけない** ——
  0 件の台帳は『調べて無かった』と読まれるが、実際は『調べられなかった』。"
  [sources source-errors]
  (and (seq sources)
       (= (set sources) (set (map :source source-errors)))))

(defn shard
  [{:keys [accepted areas sources rejected generated-at media-requested source-errors]}]
  (datoms/inventory-shard {:sites accepted
                           :areas (mapv :area/id areas)
                           :sources sources
                           :rejected rejected
                           :generated-at generated-at
                           :media-requested media-requested
                           :source-errors source-errors}))

(defn evidence
  "1 回の survey の証跡。入力・測定・閾値・落としたものを全部持つので、
  同じ入力から同じ shard が再現できるかを後から検査できる。"
  [{:keys [areas sources measurements decision generated-at radius-m media-requested
           source-errors]}]
  {:survey/generated-at generated-at
   :survey/areas (mapv (fn [a] (select-keys a [:area/id :area/bbox :area/jurisdiction])) areas)
   :survey/sources (vec (sort (map name sources)))
   :survey/media-requested (vec (sort (map name media-requested)))
   :survey/media-unobservable (vec (sort (map name medium/unobservable-media)))
   :survey/fuse-radius-m radius-m
   :survey/min-confidence (:min-confidence decision)
   :survey/measurements measurements
   :survey/accepted (count (:accepted decision))
   :survey/below-threshold (count (:below-threshold decision))
   :survey/below-threshold-ids (mapv :site/id (:below-threshold decision))
   :survey/source-errors (vec source-errors)
   :survey/partial (boolean (seq source-errors))
   :survey/honesty
   (str "この survey は列挙した area の中で、要求した媒体だけを見ている。"
        "area の外・要求しなかった媒体に地点が無いのではなく、見ていない。"
        "屋上看板・SA/PA 内広告・高速道路沿道の後付け分類・シェルター広告は観測タグを"
        "持たないので survey では決して出ない —— 媒体社カタログか現地調査からしか入らない。"
        "高さは観測から埋まらないので建築基準法88条の要否は既定で undetermined。"
        "閾値未満の地点は捨てずに id を残してある。掲出可否は全件 unknown。")})

(defn run
  "観測が揃っている前提で 1 サイクル回す純関数。ネットワークは CLI 側。"
  [{:keys [areas observations sources generated-at radius-m min-confidence
           media-requested enrich operator-resolver source-errors]
    :or {radius-m 8.0 min-confidence default-min-confidence}}]
  (let [{:keys [sites rejected measurements]}
        (evaluate observations {:radius-m radius-m :areas areas
                                :enrich enrich :operator-resolver operator-resolver})
        decision (decide sites {:min-confidence min-confidence})]
    {;; 全 source が落ちたときは shard を出さない（nil）。呼び出し側は書かない。
     :shard (when-not (all-sources-failed? sources source-errors)
              (shard {:accepted (:accepted decision) :areas areas :sources sources
                      :rejected (count rejected) :generated-at generated-at
                      :media-requested media-requested :source-errors source-errors}))
     :all-sources-failed (all-sources-failed? sources source-errors)
     :evidence (evidence {:areas areas :sources sources :measurements measurements
                          :decision decision :generated-at generated-at
                          :radius-m radius-m :media-requested media-requested
                          :source-errors source-errors})
     :decision decision
     :measurements measurements}))
