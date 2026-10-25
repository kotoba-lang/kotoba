(ns denchu.order
  "電柱広告の**出稿（申込）ステートマシン**と、その純粋な governor 判定。

  workspace の Actors 不変条件をそのまま持ち込む: 提案する側（ops-LLM）と
  censor する側（governor）を分け、governor が拒否した状態遷移は起きない。
  この ns は純粋 — I/O も custody も持たず、`violations` が空でなければ
  `advance` は遷移しない。

  状態:

    :draft            柱と面を選んだだけ
    :quoted           参考見積が付いた（`denchu.pricing`、常に indicative）
    :inquiry-proposed 代理店への問い合わせ文面ができた（未送信）
    :inquiry-sent     送信済み（外部影響を伴うので `:risk :external-send`）
    :agency-confirmed 代理店から空き・実額の回答が来た
    :permit-filed     屋外広告物許可（必要なら道路占用も）を申請した
    :installed        製作・取付が完了した
    :active           掲出中
    :ended            掲出終了
    :held             governor が保留（差し戻し）
    :rejected         取り下げ

  **`:agency-confirmed` より前に実額は存在しない。** 見積を実額として
  扱う遷移は governor が弾く。"
  (:require [kotoba.lang.text :as str]
            [denchu.facts :as facts]
            [denchu.media :as media]
            [denchu.slot :as slot]))

(def states
  #{:draft :quoted :inquiry-proposed :inquiry-sent :agency-confirmed
    :permit-filed :installed :active :ended :held :rejected})

(def transitions
  "許可された遷移だけ。ここに無い遷移は理由を問わず起きない。"
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

(defn violations
  "`order` を `to` へ進めてよいか。理由の文字列 vector を返す（空 = 可）。
  governor はこれを再計算するだけで、提案者の主張を信用しない。"
  [order to]
  (let [from (:order/state order)
        pole (:order/pole order)
        slot-kind (:order/slot-kind order)]
    (cond-> []
      (not (contains? states to))
      (conj (str "unknown target state: " to))

      (not (contains? (get transitions from #{}) to))
      (conj (str "transition not allowed: " from " -> " to))

      (not (slot/slot-kind? slot-kind))
      (conj (str "unknown slot kind: " slot-kind))

      (nil? (:pole/id pole))
      (conj "order has no pole")

      ;; 見積 → 問い合わせ: 参考見積が付いていること
      (and (= to :inquiry-proposed) (nil? (:order/quote order)))
      (conj "no indicative quote attached")

      ;; 問い合わせ先が分からないまま送らない。所有者が確定していなくても、
      ;; 管轄から候補が出るなら組んでよい（所有者はその照会で確定する）。
      (and (#{:inquiry-proposed :inquiry-sent} to)
           (not (contains? #{:routable :candidate-by-area}
                           (:route/status (media/contact-route pole)))))
      (conj (str "no reachable agency for pole " (:pole/id pole)
                 " (owner=" (:pole/owner pole)
                 " jurisdiction=" (:pole/jurisdiction pole)
                 ") — 窓口も区域候補も無いまま問い合わせを組まない"))

      ;; 送信は外部影響。宛先の実体が要る
      (and (= to :inquiry-sent) (nil? (:order/agency order)))
      (conj "inquiry-sent requires a concrete agency")

      (and (= to :inquiry-sent) (empty? (:order/inquiry-body order)))
      (conj "inquiry-sent requires a drafted body")

      ;; 代理店回答なしに実額を主張しない
      (and (= to :agency-confirmed) (nil? (:order/agency-answer order)))
      (conj "agency-confirmed requires the agency's own answer")

      (and (= to :agency-confirmed)
           (nil? (get-in order [:order/agency-answer :answer/source])))
      (conj "agency answer must carry :answer/source")

      ;; 許可申請は管轄の spec-basis が要る。無い管轄では進めない
      (and (= to :permit-filed) (not (facts/covered? (iso3 order))))
      (conj (str "no spec-basis for jurisdiction " (iso3 order)))

      (and (= to :permit-filed)
           (seq (let [m (facts/missing-evidence (iso3 order) slot-kind
                                                (keys (:order/evidence order)))]
                  (if (= m :no-spec-basis) [:no-spec-basis] m))))
      (conj (str "missing required evidence: "
                 (facts/missing-evidence (iso3 order) slot-kind
                                         (keys (:order/evidence order)))))

      ;; 突出形態は道路占用の検討を明示的に済ませてから
      (and (= to :permit-filed)
           (facts/road-occupancy-relevant? (iso3 order) slot-kind)
           (nil? (:order/road-occupancy order)))
      (conj "projecting slot requires a recorded road-occupancy determination")

      ;; 取付は許可の後
      (and (= to :installed) (nil? (:order/permit order)))
      (conj "installed requires a recorded permit"))))

(defn risk
  "その遷移が外部に影響するか。`:external-send` は承認キューに載せる印。"
  [to]
  (case to
    :inquiry-sent :external-send
    :permit-filed :external-filing
    :internal))

(defn advance
  "governor 判定を通った時だけ遷移する。通らなければ状態を変えず、
  `:order/last-violations` に理由を残す（黙って落とさない）。"
  [order to]
  (let [vs (violations order to)]
    (if (seq vs)
      (assoc order :order/last-violations vs :order/last-decision :held)
      (-> order
          (assoc :order/state to
                 :order/last-violations []
                 :order/last-decision :committed
                 :order/risk (risk to))
          (update :order/history (fnil conj []) {:history/to to
                                                 :history/risk (risk to)})))))

(defn new-order
  "柱 + 面 から draft を起こす。ここでは何も外部に触れない。"
  [{:keys [pole slot-kind jurisdiction advertiser]}]
  {:order/state :draft
   :order/pole pole
   :order/slot-kind slot-kind
   :order/jurisdiction (or jurisdiction "JPN")
   :order/advertiser advertiser
   :order/route (media/contact-route pole)
   :order/evidence {}
   :order/history []})

(defn inquiry-draft
  "代理店への問い合わせ文面（未送信）。**価格を確定として書かない** —
  参考値であることと、確認したい事項が本文の主眼であることを明記する。

  所有者が未確定（`:candidate-by-area`）の場合は、**設備所有者の確認そのものを
  第一の問い合わせ事項にする** —— 当方の推定として社名を書くと、相手が
  「そちらの言うとおり」と流してしまい、誤った所有者が確定してしまう。"
  [order]
  (let [pole (:order/pole order)
        q (:order/quote order)
        agency (:order/agency order)
        route (media/contact-route pole)
        candidate? (= :candidate-by-area (:route/status route))]
    (str "件名: 電柱広告の掲出可否・お見積のご相談\n\n"
         (or (:agency/legal-name agency) "ご担当者") " 御中\n\n"
         (if candidate?
           "下記の電柱について、まず貴社のお取り扱い設備かどうかのご確認と、掲出可否・お見積をご相談させてください。\n\n"
           "下記の電柱について、広告掲出の可否と正式なお見積をご相談させてください。\n\n")
         "・柱の位置: 緯度 " (:pole/lat pole) " / 経度 " (:pole/lon pole) "\n"
         "・柱の識別子（当方の内部 id）: " (:pole/id pole) "\n"
         (if candidate?
           (str "・設備所有者: **当方では特定できておりません。**"
                " 掲出地の区域から貴社のお取り扱い範囲に含まれる可能性があると考え、ご連絡しております。\n"
                "  （区域からの候補: "
                (str/join "、" (map name (:route/owner-candidates route)))
                "。柱 1 本の所有者を当方が判定したものではありません）\n"
                (when (:route/boundary? route)
                  (str "  ※ " (:route/boundary-note route) "\n")))
           (str "・所有者: " (name (:pole/owner pole))
                (when-let [e (:pole/owner-evidence pole)] (str "（根拠: " e "）"))
                "\n"))
         "・希望する掲出面: " (:slot/name-ja (slot/describe (:order/slot-kind order))) "\n"
         "・希望本数/期間: " (:quote/units q) "本 / " (:quote/months q) "ヶ月\n\n"
         "当方で参照した公開料金は "
         (get-in q [:quote/basis :rate/source-url])
         " の記載（" (get-in q [:quote/basis :rate/as-of]) " 時点）で、"
         "あくまで参考値として扱っております。"
         (when candidate? "設備所有者・")
         "掲出可否・空き状況・実額・"
         "屋外広告物許可および道路占用許可の要否について、貴社のご確認内容を"
         "そのまま採用いたします。\n")))
