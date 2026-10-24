(ns okugai.order
  "屋外広告の**出稿（申込）ステートマシン**と純粋な governor 判定（媒体非依存）。
  `denchu.order`（電柱専用）を一般化したもの。

  workspace の Actors 不変条件をそのまま持ち込む: 提案する側と censor する側を
  分け、governor が拒否した状態遷移は起きない。この ns は純粋 —— I/O も custody も
  持たず、`violations` が空でなければ `advance` は遷移しない。

  状態:

    :draft            地点と掲出面を選んだだけ
    :quoted           参考見積が付いた（常に indicative）
    :inquiry-proposed 媒体社/代理店への問い合わせ文面ができた（未送信）
    :inquiry-sent     送信済み（外部影響。`:external-send`）
    :agency-confirmed 媒体社から可否・実額の回答が来た
    :permit-filed     必要な許可（条例／占用／工作物確認）を申請した
    :installed        製作・設置が完了した
    :active           掲出中
    :ended            掲出終了
    :held / :rejected 保留 / 取り下げ

  **`:agency-confirmed` より前に実額は存在しない。**
  **規制の要否が `:undetermined` のまま `:permit-filed` に進めない** ——
  高さ不明の広告板を『工作物確認は不要』として扱うと違法着工になる。"
  (:require [okugai.facts :as facts]
            [okugai.medium :as medium]
            [okugai.route :as route]))

(def states
  #{:draft :quoted :inquiry-proposed :inquiry-sent :agency-confirmed
    :permit-filed :installed :active :ended :held :rejected})

(def transitions
  {:draft            #{:quoted :rejected}
   :quoted           #{:inquiry-proposed :rejected}
   :inquiry-proposed #{:inquiry-sent :held :rejected}
   :inquiry-sent     #{:agency-confirmed :held :rejected}
   :agency-confirmed #{:permit-filed :held :rejected}
   :permit-filed     #{:installed :held :rejected}
   :installed        #{:active :held}
   :active           #{:ended}
   :ended            #{}
   :held             #{:inquiry-proposed :agency-confirmed :permit-filed :rejected}
   :rejected         #{}})

(defn- iso3 [order] (or (:order/jurisdiction order) "JPN"))

(defn placement
  "order → `okugai.facts/applicable` に渡す掲出条件。媒体固有の面情報
  （電柱の袖＝道路上空 等）は `:order/overhangs-road?` として order が持つ。

  `:special-zones` は防火地域などの区域集合。**nil と空集合を区別する** ——
  nil は『調べていない』、空集合は『調べた結果どの区域にも入らない』。"
  [order]
  {:medium (:order/medium order)
   :height-m (:order/height-m order)
   :area-m2 (:order/area-m2 order)
   :special-zones (:order/special-zones order)
   :overhangs-road? (:order/overhangs-road? order)
   :highway-adjacent? (:order/highway-adjacent? order)
   :highway-facility? (:order/highway-facility? order)})

(defn violations
  "`order` を `to` へ進めてよいか。理由の文字列 vector（空 = 可）。
  governor はこれを**再計算するだけ**で、提案者の主張を信用しない。

  `:route-status` は媒体 repo が解決した問い合わせ経路の状態を order に載せたもの
  （`:routable` / `:candidate-by-area` なら照会できる）。この ns は媒体ごとの
  窓口解決ロジックを持たない —— それは媒体 repo の仕事。"
  [order to]
  (let [from (:order/state order)
        site (:order/site order)
        med (:order/medium order)
        route (:order/route-status order)]
    (cond-> []
      (not (contains? states to))
      (conj (str "unknown target state: " to))

      (not (contains? (get transitions from #{}) to))
      (conj (str "transition not allowed: " from " -> " to))

      (not (medium/medium? med))
      (conj (str "unknown medium: " med))

      (nil? (:site/id site))
      (conj "order has no site")

      (and (= to :inquiry-proposed) (nil? (:order/quote order)))
      (conj "no indicative quote attached")

      (and (#{:inquiry-proposed :inquiry-sent} to)
           (not (route/reachable-status? route)))
      (conj (str "no reachable agency for site " (:site/id site)
                 " (route-status=" route ") — 窓口も候補も無いまま問い合わせを組まない"))

      (and (= to :inquiry-sent) (nil? (:order/agency order)))
      (conj "inquiry-sent requires a concrete agency")

      (and (= to :inquiry-sent) (empty? (:order/inquiry-body order)))
      (conj "inquiry-sent requires a drafted body")

      (and (= to :agency-confirmed) (nil? (:order/agency-answer order)))
      (conj "agency-confirmed requires the agency's own answer")

      (and (= to :agency-confirmed)
           (nil? (get-in order [:order/agency-answer :answer/source])))
      (conj "agency answer must carry :answer/source")

      (and (= to :permit-filed) (not (facts/covered? (iso3 order))))
      (conj (str "no spec-basis for jurisdiction " (iso3 order)))

      ;; 規制の要否が判定できないまま許可申請へ進めない
      (and (= to :permit-filed) (facts/undetermined? (iso3 order) (placement order)))
      (conj (str "regulatory applicability undetermined: "
                 (let [a (facts/applicable (iso3 order) (placement order))]
                   (if (= a :no-spec-basis) [:no-spec-basis]
                       (vec (sort (map name (:undetermined a))))))
                 " — 高さ・面積・区域・道路上空の別を確定してから申請する"))

      (and (= to :permit-filed)
           (let [m (facts/missing-evidence (iso3 order) (placement order)
                                           (keys (:order/evidence order)))]
             (or (= m :no-spec-basis) (seq m))))
      (conj (str "missing required evidence: "
                 (facts/missing-evidence (iso3 order) (placement order)
                                         (keys (:order/evidence order)))))

      (and (= to :installed) (nil? (:order/permit order)))
      (conj "installed requires a recorded permit"))))

(defn risk
  [to]
  (case to
    :inquiry-sent :external-send
    :permit-filed :external-filing
    :internal))

(defn advance
  "governor 判定を通った時だけ遷移する。通らなければ状態を変えず理由を残す。"
  [order to]
  (let [vs (violations order to)]
    (if (seq vs)
      (assoc order :order/last-violations vs :order/last-decision :held)
      (-> order
          (assoc :order/state to
                 :order/last-violations []
                 :order/last-decision :committed
                 :order/risk (risk to))
          (update :order/history (fnil conj []) {:history/to to :history/risk (risk to)})))))

(defn new-order
  [{:keys [site medium jurisdiction advertiser route-status height-m area-m2
           overhangs-road? special-zones highway-adjacent?]}]
  {:order/state :draft
   :order/site site
   :order/medium (or medium (:site/medium site))
   :order/jurisdiction (or jurisdiction "JPN")
   :order/advertiser advertiser
   :order/route-status route-status
   :order/height-m height-m
   :order/area-m2 area-m2
   :order/overhangs-road? overhangs-road?
   :order/special-zones special-zones
   :order/highway-adjacent? highway-adjacent?
   :order/evidence {}
   :order/history []})

(defn regulatory-summary
  "この掲出に効く規制の一覧（人が読む用 + 監査ログ）。`:undetermined` を
  隠さないのが要点。"
  [order]
  (let [a (facts/applicable (iso3 order) (placement order))]
    (if (= a :no-spec-basis)
      {:regulatory/jurisdiction (iso3 order)
       :regulatory/status :no-spec-basis
       :regulatory/note "この法域は okugai.facts に未収録。要件を創作せず、掲出提案は保留する。"}
      {:regulatory/jurisdiction (iso3 order)
       :regulatory/required (vec (sort (map name (:required a))))
       :regulatory/undetermined (vec (sort (map name (:undetermined a))))
       :regulatory/not-applicable (vec (sort (map name (:not-applicable a))))
       :regulatory/note (if (seq (:undetermined a))
                          "要否が確定していない規制がある。高さ・面積・区域・道路上空の別を確定するまで申請に進めない。"
                          "既知の条件で要否は確定済み。")})))
