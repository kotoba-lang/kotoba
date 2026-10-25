(ns noren.governor
  "NorenGovernor —— 提案を外へ出してよいかを、提案を作った側とは別に判定する。

  この loop は**相手が頼んでいないのに相手のサイトを採点して連絡する**。
  それが許される形は狭い。狭さをここに 1 箇所で書き、他のどこにも書かない
  （`noren.prescribe` は文を作るだけで、送ってよいかを知らない）。

  純関数。ここに I/O は無く、**判定に必要な事実はすべて呼び出し側が渡す**。
  『渡し忘れ』は握り潰さず HARD 違反になる —— 検査に必要な材料が無いことは、
  検査に通ったことではない。

  ## HARD（1 つでも当たれば :hold）

  | rule | 根拠 |
  |---|---|
  | `:prospect-ineligible`      | 特定電子メール法 3 条 1 項 4 号の形をしていない |
  | `:suppressed`               | 一度断られた相手（拒否は恒久） |
  | `:resend-too-soon`          | 最短間隔以内の再送 |
  | `:contact-limit-reached`    | 生涯接触回数の上限 |
  | `:claim-without-evidence`   | 測っていないことを書いている |
  | `:nothing-to-sell`          | 健全なサイトへの接触（用が無い） |
  | `:no-measured-claim`        | 主張できる測定結果が 1 件も無い |
  | `:unverified-absence`       | 取得失敗を「サイトが無い」として言おうとしている |
  | `:sender-disclosure-missing`| 法 4 条の表示義務（名称・住所・受信拒否の通知先） |
  | `:opt-out-missing`          | 本文に受信拒否の方法が無い |
  | `:outcome-promise`          | 測れない成果を約束している |
  | `:asset-reuse`              | 相手の画像・ロゴを生成物へ複製している |"
  (:require [kotoba.lang.text :as str]
            [noren.prospect :as prospect]
            [noren.prescribe :as prescribe]))

(def min-resend-interval-days
  "同じ相手への再接触の最短間隔。"
  60)

(def max-lifetime-contacts
  "同じ相手への生涯接触回数。2 回目で返事が無ければ用が無い。"
  2)

(def outcome-promise-markers
  "測れない約束。売り文句としては強いが、この loop は成果を測っていない。"
  [#"必ず"
   #"保証(します|いたします)"
   #"確実に"
   #"(売上|集客|来店|注文|予約)が(必ず|確実に|\d+%?)?\s*(増え|上が|伸び)"
   #"(検索|Google).{0,6}(1位|一位|上位).{0,6}(表示|保証|確約)"
   #"(?i)guarantee(d)?\s+(ranking|traffic|sales)"])

(defn ^:private days-between [a b]
  (when-let [x (prospect/epoch-day a)]
    (when-let [y (prospect/epoch-day b)] (- y x))))

(defn ^:private hard [rule detail] {:rule rule :severity :hard :detail detail})
(defn ^:private soft [rule detail] {:rule rule :severity :soft :detail detail})

(defn review
  "`{:prospect :prescription :message :history :suppression :now}` → 判定。

  `message` = `{:body \"…\" :sender {:name :address :opt-out-contact}}`
  `history` = その相手への過去の接触 `[{:contacted-at \"2026-06-01\"} …]`
  `suppression` = 受信拒否された鍵の集合（`prospect/dedup-key` と同じ形）"
  [{:keys [prospect prescription message history suppression now]}]
  (let [key      (prospect/dedup-key prospect)
        elig     (prospect/eligible prospect now)
        claims   (prescribe/claim-axes prescription)
        evidence (set (map :evidence/axis (:evidence prescription)))
        body     (or (:body message) "")
        sender   (:sender message)
        history  (vec (or history []))
        last-at  (->> history (keep :contacted-at) sort last)
        gap      (when last-at (days-between last-at now))
        vs
        (cond-> []
          (not (:ok? elig))
          (conj (hard :prospect-ineligible
                      (str "接触の前提を満たしていない: "
                           (str/join " / " (map :detail (:reasons elig))))))

          (contains? (set suppression) key)
          (conj (hard :suppressed "この相手は受信を拒否している（恒久）"))

          (and gap (< gap min-resend-interval-days))
          (conj (hard :resend-too-soon
                      (str "前回接触から " gap " 日（最短 " min-resend-interval-days " 日）")))

          ;; 履歴が渡されていないのに再送判定はできない。last-at が無いのは
          ;; 「初回」かもしれないし「渡し忘れ」かもしれない —— 区別できないので
          ;; soft で必ず可視化する（黙って初回として扱わない）。
          (and (empty? history) (nil? last-at))
          (conj (soft :history-absent "接触履歴が渡されていない。初回として扱うが、記録が無いだけの可能性がある"))

          (>= (count history) max-lifetime-contacts)
          (conj (hard :contact-limit-reached
                      (str "接触回数が上限 " max-lifetime-contacts " に達している")))

          (seq (remove evidence claims))
          (conj (hard :claim-without-evidence
                      (str "測っていない軸を主張している: "
                           (str/join ", " (map name (remove evidence claims))))))

          (= :none (:action prescription))
          (conj (hard :nothing-to-sell "診断が健全。用が無いのに接触しない"))

          ;; 取得に失敗しただけで「サイトが見つかりません」と送らない。
          ;; 相手について分かっていないことを、相手について言わない。
          (and (= :absent (get-in prescription [:diagnosis :verdict]))
               (not (true? (get-in prescription [:diagnosis :observation :definitive?]))))
          (conj (hard :unverified-absence
                      (str "公開面が無いと言い切れる観測ではない（status: "
                           (pr-str (get-in prescription [:diagnosis :observation :status]))
                           "）。取得失敗はこちらの観測の失敗であって、相手の事実ではない")))

          ;; `:nothing-to-sell` とは別の rule にしてある。健全だから言うことが
          ;; 無いのと、測れていないから言うことが無いのは、直し方が違う。
          (empty? claims)
          (conj (hard :no-measured-claim "主張できる測定結果が 1 件も無い"))

          (or (str/blank? (:name sender)) (str/blank? (:address sender)))
          (conj (hard :sender-disclosure-missing
                      "送信者の名称と住所が無い（特定電子メール法 4 条の表示義務）"))

          (or (str/blank? (:opt-out-contact sender))
              (not (str/includes? body (str (:opt-out-contact sender)))))
          (conj (hard :opt-out-missing
                      "受信拒否の通知先が本文に書かれていない（同 3 条 3 項 / 4 条）"))

          (some #(re-find % body) outcome-promise-markers)
          (conj (hard :outcome-promise
                      "測っていない成果を約束している。言えるのは測った軸だけ"))

          (seq (:build/borrowed-assets prescription))
          (conj (hard :asset-reuse
                      (str "相手の素材を生成物へ複製している: "
                           (str/join ", " (:build/borrowed-assets prescription)))))

          (seq (:needs-owner-input prescription))
          (conj (soft :owner-facts-pending
                      (str "所有者から貰うまで埋めてはいけない事実: "
                           (str/join ", " (map name (:needs-owner-input prescription)))))))

        hards (filterv #(= :hard (:severity %)) vs)]
    {:decision (if (seq hards) :hold :commit)
     :violations hards
     :warnings (filterv #(= :soft (:severity %)) vs)
     :receipt {:receipt/prospect key
               :receipt/at now
               :receipt/action (:action prescription)
               :receipt/claim-axes (vec (sort (map name claims)))
               :receipt/overall (:overall prescription)}}))
