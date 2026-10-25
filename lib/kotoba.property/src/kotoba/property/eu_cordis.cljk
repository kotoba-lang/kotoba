(ns kotoba.property.eu-cordis
  "CORDIS Horizon Europe の一括 CSV -> **EU の intent 母集団**。I/O は 1 バイトも無い。

   日本側（gBizINFO 届出認定）と同じ型を EU で作る。対応は 1 対 1 ではない ——
   日本の母集団は『設備投資の税制優遇を取りにいった中小企業』で、それは
   **SKU A（オンプレ機・JP shipping の Stripe リンク 1 本）**の ICP である。
   EU には出荷しないので、EU が母集団になるのは **SKU B（ホスト推論 API）**の側で、
   代理するシグナルも別物になる:

     JP / SKU A  『この会社は最近、設備投資の優遇を取りにいった』
     EU / SKU B  『この会社は最近、EU の競争的 R&D 資金を取りにいった』

   ## 母集団の定義

   `activityType = PRC`（private for-profit）かつ、**署名日または開始日が
   `since` 以降**のプロジェクトに参加している法人。CORDIS は 1 行 =
   1 (法人, プロジェクト) の参加なので、法人単位に畳んでから採点する。

   ## 区切りはセミコロン

   ⚠ gBizINFO はカンマだが **CORDIS はセミコロン**（実測 2026-08-25）。
   カンマで読むと 1 行が 1 フィールドとして通り、例外にならない。
   `bulk-csv/parse` に `delimiter` を渡すこと。

   ## 出典

   出典：CORDIS（欧州委員会）https://cordis.europa.eu/ の Horizon Europe
   projects データセットを加工して作成。CC BY 4.0。"
  (:require [kotoba.lang.text :as str]))

(def dataset "eu-cordis-intent")
(def authority-id "EU/EC-CORDIS-HorizonEurope")
(def attribution
  "出典：CORDIS（欧州委員会）https://cordis.europa.eu/ Horizon Europe projects（CC BY 4.0）を加工して作成。")

(def delimiter
  "CORDIS の CSV 区切り。**カンマではない。**"
  ";")

(def private-for-profit
  "`activityType` のうち民間営利。HES(高等教育) / REC(研究機関) / PUB(公的機関) /
   OTH は母集団に入れない —— 買うのは法人であって大学ではない。"
  "PRC")

;; ---------------------------------------------------------------------------
;; トピック（call ID）の分類
;;
;; `topics` 列は 100% 埋まっている（実測 2026-08-25、23,451 プロジェクト全件）ので、
;; ここから作る点数は **base**（全社比較可能）に置ける。

(def topic-class-order
  "判定は上から順に当てる。**順序が意味を持つ** —— `HORIZON-JU-Chips` は
   `HORIZON-JU-` にも当たるので、先に見る。"
  [[:msca      #"(?i)^HORIZON-MSCA"]
   [:eic       #"(?i)^HORIZON-EIC"]
   [:chips-ju  #"(?i)^HORIZON-JU-Chips"]
   [:cl4-digital  #"(?i)^HORIZON-CL4"]
   [:cl3-security #"(?i)^HORIZON-CL3"]
   [:cl1-health   #"(?i)^HORIZON-CL1"]
   [:cl2-culture  #"(?i)^HORIZON-CL2"]
   [:cl5-climate  #"(?i)^HORIZON-CL5"]
   [:cl6-food     #"(?i)^HORIZON-CL6"]
   [:other-ju  #"(?i)^HORIZON-JU-"]
   [:widera    #"(?i)^HORIZON-WIDERA"]
   [:infra     #"(?i)^HORIZON-INFRA|^HORIZON-ERA"]
   [:erc       #"(?i)^ERC-|^HORIZON-ERC"]])

(defn topic-class
  "call ID -> クラス。当たらなければ `:other`。**nil を返さない** ——
   `topics` は 100% 埋まっているので、分類できないことは『測れなかった』ではなく
   『こちらの表に無い』であり、母集団から落とす理由にならない。"
  [topic]
  (let [t (str/trim (str topic))]
    (if (str/blank? t)
      :other
      (or (some (fn [[k re]] (when (re-find re t) k)) topic-class-order)
          :other))))

;; ---------------------------------------------------------------------------
;; 日付

(defn event-date
  "その参加の『公表された出来事の日』。**署名日を優先する。**

   `ecSignatureDate` は助成契約に署名した日（＝予算が確定した公的な行為）で、
   日本の『証明日』に一番近い。`startDate` は事業の開始で、**未来の日付が
   実在する**（実測 2026-08-25: startDate が 2026 年 4,676 件 / 2027 年 844 件）。
   未来の開始日をそのまま経過月数に入れると負になるので、リセンシーは署名日で測る。"
  [{:keys [signature-date start-date]}]
  (let [s (str/trim (str signature-date))
        st (str/trim (str start-date))]
    (cond (not (str/blank? s)) s
          (not (str/blank? st)) st
          :else nil)))

(defn recent?
  "この参加が母集団の切り口に入るか。**署名日か開始日のどちらかが `since` 以降**。

   両方見るのは、署名が古くても開始が最近なら（＝いま走っている）
   予算の執行はこれからだからである。"
  [{:keys [signature-date start-date]} since]
  (let [ge (fn [d] (and (not (str/blank? (str d))) (>= 0 (compare (str since) (str d)))))]
    (boolean (or (ge signature-date) (ge start-date)))))

;; ---------------------------------------------------------------------------
;; 参加 -> 法人

(defn- blank->nil [s]
  (let [s (str/trim (str s))] (when-not (str/blank? s) s)))

(defn ->participation
  "CSV の 1 行から取り出した値 -> 正規化した参加 1 件。

   入力は文字列の map（列名は呼び手が引く）。**空文字と nil を区別しない** ——
   CSV の空フィールドは『そこに値が無い』であって、両者に別の意味は無い。"
  [m]
  (let [p {:organisation-id (blank->nil (:organisation-id m))
           :project-id (blank->nil (:project-id m))
           :name (blank->nil (:name m))
           :short-name (blank->nil (:short-name m))
           :vat (blank->nil (:vat m))
           :street (blank->nil (:street m))
           :post-code (blank->nil (:post-code m))
           :city (blank->nil (:city m))
           :country (blank->nil (:country m))
           :url (blank->nil (:url m))
           :contact-form (blank->nil (:contact-form m))
           :role (blank->nil (:role m))
           :activity-type (blank->nil (:activity-type m))
           :topic (blank->nil (:topic m))
           :signature-date (blank->nil (:signature-date m))
           :start-date (blank->nil (:start-date m))
           ;; SME は 3 値。**`false` と『載っていない』を同じにしない。**
           :sme (case (str/lower (str (:sme m))) "true" true "false" false nil)
           :ec-contribution (let [v (blank->nil (:ec-contribution m))]
                              (when v
                                (let [n #?(:clj (try (Double/parseDouble (str/replace v "," "."))
                                                     (catch Exception _ nil))
                                           :cljs (let [n (js/parseFloat (str/replace v "," "."))]
                                                   (when-not (js/isNaN n) n)))]
                                  n)))
           ;; euroSciVoc は **部分被覆**（実測 2026-08-25: 20,161/23,451 プロジェクト
           ;; = 86.0%）。だから nil は『AI ではない』ではなく『測れなかった』。
           :ai-tagged? (:ai-tagged? m)}]
    (assoc p :topic-class (topic-class (:topic p))
             :event-date (event-date p))))

(defn organisation
  "同じ法人の参加の列 -> 法人 1 件。

   **住所と URL は『最も新しい参加のもの』を採り、空なら古い方へ落ちる。**
   CORDIS の同一 organisationID は行ごとに住所が空だったり埋まっていたりするので、
   1 行だけ見ると取れるはずの住所を落とす（実測: 参加行の URL 被覆 22.0% に対し、
   法人単位で『どれか 1 行に URL がある』は 13.2%。行を跨いで拾う必要がある）。"
  [participations]
  (let [ps (vec (reverse (sort-by #(str (:event-date %)) participations)))
        pick (fn [k] (some k ps))
        classes (vec (distinct (keep :topic-class ps)))]
    {:organisation-id (pick :organisation-id)
     :name (pick :name)
     :short-name (pick :short-name)
     :vat (pick :vat)
     :street (pick :street)
     :post-code (pick :post-code)
     :city (pick :city)
     :country (pick :country)
     :url (pick :url)
     :contact-form (pick :contact-form)
     ;; SME は 3 値のまま畳む。1 行でも true なら true、全部 false なら false、
     ;; 全部 nil なら nil（測れなかった）。
     :sme (cond (some true? (map :sme ps)) true
                (some false? (map :sme ps)) false
                :else nil)
     :coordinator? (boolean (some #(= "coordinator" (:role %)) ps))
     :ai-tagged? (cond (some true? (map :ai-tagged? ps)) true
                       (some false? (map :ai-tagged? ps)) false
                       :else nil)
     :ec-contribution (let [xs (keep :ec-contribution ps)]
                        (when (seq xs) (reduce + 0.0 xs)))
     :topic-classes classes
     :participations ps
     :latest-event-date (pick :event-date)
     :project-count (count (distinct (keep :project-id ps)))}))

(defn addressable?
  "宛名を作れるか。**社名と番地と市**。〒 は無くても郵送はできるが、
   番地が無いと作れない。"
  [org]
  (boolean (and (blank->nil (:name org))
                (blank->nil (:street org))
                (blank->nil (:city org)))))

(defn postal-address
  "郵送用の 1 行住所。取れなかった要素は**入れない**（`nil` を文字列にしない）。"
  [org]
  (->> [(:street org) (:post-code org) (:city org) (:country org)]
       (keep blank->nil)
       (str/join ", ")
       blank->nil))
