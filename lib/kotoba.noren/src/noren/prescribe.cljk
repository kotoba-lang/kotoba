(ns noren.prescribe
  "診断 → 処方。**測った事実だけを言う**ための名前空間。

  ここで作る `:claims` は提案文にそのまま載る文であり、1 文につき 1 つの
  軸 id を背負う。governor は claim の軸が evidence に無ければ HARD で止める
  ので、**測っていないことを書く経路が構造的に無い**。文面を LLM に書かせる
  ときも、LLM が触れてよいのはこの claim の並べ方だけで、claim 自体は増やせない。

  誇張が禁じられているのは行儀の問題ではない。相手のサイトについて外から
  断定できるのは測った軸だけで、それ以外は推測であり、推測を根拠に売るのは
  この loop が最初にやってはいけないことである。"
  (:require [kotoba.lang.text :as str]))

(def ^:private claim-templates
  "軸 id → 測定結果を述べる文。**改善の約束ではなく観測の報告**にする。"
  {:https           "サイトが HTTPS で配信されておらず、ブラウザが警告を表示します。"
   :contact-path    "ページから連絡する手段（電話・メール・フォーム）が見つかりませんでした。"
   :address         "所在地の記載が読み取れませんでした。"
   :tel             "電話番号の記載が読み取れませんでした。"
   :structured-data "検索や地図が読む構造化データ（schema.org）がありませんでした。"
   :ogp             "SNS に貼られたときの表示情報（OGP）がありませんでした。"
   :hours           "営業時間の記載が読み取れませんでした。"
   :menu            "価格つきのメニュー項目が読み取れませんでした。"
   :catalog         "価格つきの商品が読み取れませんでした。"
   :commerce-terms  "特定商取引法に基づく表記が見当たりませんでした。"
   :freshness       "更新の痕跡が見当たらず、いつの情報か判断できませんでした。"
   :viewport        "スマートフォンで開いたとき画面幅に合いません。"
   :tap-targets     "指で押す領域が小さく、押し間違いが起きやすい状態でした。"
   :contrast        "文字と背景のコントラストが WCAG の基準（4.5:1）を下回る箇所がありました。"
   :input-zoom      "入力欄の文字が小さく、iOS で自動的に拡大されます。"
   :focus-visible   "キーボード操作時に、いまどこを選んでいるかが表示されません。"
   :reduced-motion  "動きを減らす設定を尊重していません。"
   :responsive      "画面幅に応じた指定が見当たりませんでした。"
   :semantics       "言語や文字コードの指定が不足していました。"
   :safe-area       "端末のノッチ部分に内容が隠れる可能性があります。"
   :dynamic-viewport "モバイルで画面の高さが変わると表示が飛びます。"
   :color-scheme    "端末のダークモードに対応していません。"
   :overflow-guard  "横方向にはみ出してスクロールが発生する可能性があります。"
   :no-site         "公開されているサイトを見つけられませんでした。"})

(def ^:private owner-facts
  "**こちらが作ってはいけない事実。** 欠けている軸 → 所有者から貰う項目。
  ここに挙がったものを生成物に埋めるのは捏造で、営業以前に嘘である。"
  {:address  :fact/address
   :tel      :fact/tel
   :hours    :fact/hours
   :menu     :fact/menu-items
   :catalog  :fact/catalog-items
   :commerce-terms :fact/commerce-terms})

(def max-claims
  "提案 1 通に載せる claim の上限。全部並べると読まれない。"
  3)

(defn prescribe
  "`diagnosis`（`noren.diagnose/diagnose` の戻り）→ 処方。

  `:action`
    `:none`    健全。売るものが無い（**これを出せることが重要**。
               全件に提案が出る loop は測っていないのと同じ）
    `:repair`  直せる。既存の面に手を入れる
    `:rebuild` 建て替える。または面そのものが無い"
  [{:keys [verdict overall findings surface] :as diagnosis}]
  (let [action (case verdict
                 :healthy    :none
                 :repairable :repair
                 :rebuild    :rebuild
                 :absent     :rebuild)
        evidence (->> findings
                      (filter #(contains? claim-templates (:axis % (:id %))))
                      (map (fn [f]
                             (let [id (:axis f (:id f))]
                               {:evidence/axis id
                                :evidence/plane (:plane f)
                                :evidence/score (:score f)
                                :evidence/weight (:weight f)
                                :evidence/finding (:finding f)})))
                      vec)
        claims (->> evidence
                    (take max-claims)
                    (mapv (fn [e] {:claim/axis (:evidence/axis e)
                                   :claim/text (get claim-templates (:evidence/axis e))})))]
    {:action action
     :surface surface
     :overall overall
     :evidence evidence
     :claims (if (= action :none) [] claims)
     ;; 建て替えるなら、こちらが持っていない事実を先に貰う。
     :needs-owner-input (if (= action :none)
                          []
                          (->> evidence
                               (keep #(get owner-facts (:evidence/axis %)))
                               distinct vec))
     :diagnosis diagnosis}))

(defn claim-axes
  "governor が evidence と突き合わせるための集合。"
  [prescription]
  (set (map :claim/axis (:claims prescription))))

(defn summary-line
  "人が 1 行で読むための要約。数値は丸めるが、丸めた値で判定はしない。"
  [{:keys [action overall claims]}]
  (str (name action) " / " (int (Math/round (double overall))) "点 / "
       (str/join "、" (map :claim/text claims))))
