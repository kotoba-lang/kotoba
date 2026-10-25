(ns denchu.area
  "管轄（ISO 3166-2:JP）→ その地域に柱を持ちうる**候補**事業者。

  ## なぜ「候補」なのか — これは推測ではなく、確定でもない

  `denchu.pole` は所有者を推測しない（`operator` タグが無ければ `:unknown`）。
  実測では OSM の柱の大半に `operator` が無く、261 本中 0 本しか所有者が決まら
  なかった。ここで詰まると**問い合わせ 1 通も出せない**。

  だが日本の配電・通信設備には制度的事実がある: 一般送配電事業者の供給区域と
  NTT 東西の営業区域は法令・会社公表で決まっており、**ある県に柱があるなら、
  その柱の所有者は限られた候補のいずれか**である。これは座標からの推測ではなく、
  区域の定義そのもの。

  したがってこの ns が返すのは:
  - `:owner/candidates` — その管轄に区域を持つ事業者（電力柱 ∪ 通信柱）
  - **確定ではない。** 1 本の柱が電力柱か通信柱か、共架柱かは区域からは分からない。

  そして候補があれば**問い合わせを組める** —— 実務でも所有者はここで確定する
  （「この座標の柱は御社の設備でしょうか」を代理店に聞く）。`denchu.order` は
  候補ルートでの `:inquiry-proposed` を許し、`inquiry-draft` は所有者確認を
  本文の主眼に据える。`:pole/owner` は `:unknown` のままで、**候補は柱ではなく
  経路に載る**。

  ## 境界は畳まない

  県境と区域境は一致しない。静岡県は富士川で東京電力パワーグリッドと中部電力
  パワーグリッドに分かれ、NTT は西日本だが熱海市・裾野市の一部が東日本。福井県は
  嶺南が関西電力送配電。こうした県は `:boundary?` を立てて**両方を候補に残す** ——
  片方に畳むと、畳んだ側の柱で必ず間違う。"
  (:require [kotoba.lang.text :as str]))

(def ^:const power-source
  "供給区域は電気事業法に基づく一般送配電事業者の区域。県単位の対応は各社の
  公表による。境界のある県は :boundary? で明示する。"
  {:kind :power
   :as-of "2026-08-04"
   :source-urls ["https://www.tepco.co.jp/pg/company/summary/area-office/shizuoka.html"]})

(def ^:const telecom-source
  {:kind :telecom
   :as-of "2026-08-04"
   :source-urls ["https://flets.com/misc/fletshikari/cross_area.html"]})

(def power-by-jurisdiction
  "ISO 3166-2:JP → 一般送配電事業者の候補。"
  {"JP-01" [:hepco-nw]
   "JP-02" [:tohoku-epco] "JP-03" [:tohoku-epco] "JP-04" [:tohoku-epco]
   "JP-05" [:tohoku-epco] "JP-06" [:tohoku-epco] "JP-07" [:tohoku-epco]
   "JP-15" [:tohoku-epco]
   "JP-08" [:tepco-pg] "JP-09" [:tepco-pg] "JP-10" [:tepco-pg] "JP-11" [:tepco-pg]
   "JP-12" [:tepco-pg] "JP-13" [:tepco-pg] "JP-14" [:tepco-pg] "JP-19" [:tepco-pg]
   "JP-22" [:tepco-pg :chuden-pg]
   "JP-20" [:chuden-pg] "JP-21" [:chuden-pg :kepco-t] "JP-23" [:chuden-pg]
   "JP-24" [:chuden-pg :kepco-t]
   "JP-16" [:rikuden-t] "JP-17" [:rikuden-t] "JP-18" [:rikuden-t :kepco-t]
   "JP-25" [:kepco-t] "JP-26" [:kepco-t] "JP-27" [:kepco-t]
   "JP-28" [:kepco-t :energia-nw] "JP-29" [:kepco-t] "JP-30" [:kepco-t]
   "JP-31" [:energia-nw] "JP-32" [:energia-nw] "JP-33" [:energia-nw]
   "JP-34" [:energia-nw] "JP-35" [:energia-nw]
   "JP-36" [:yonden-t] "JP-37" [:yonden-t] "JP-38" [:yonden-t] "JP-39" [:yonden-t]
   "JP-40" [:kyuden-t] "JP-41" [:kyuden-t] "JP-42" [:kyuden-t] "JP-43" [:kyuden-t]
   "JP-44" [:kyuden-t] "JP-45" [:kyuden-t] "JP-46" [:kyuden-t]
   "JP-47" [:okiden]})

(def telecom-by-jurisdiction
  "ISO 3166-2:JP → NTT 東西。静岡は西だが一部が東（`boundary-notes` 参照）。"
  (let [east ["JP-01" "JP-02" "JP-03" "JP-04" "JP-05" "JP-06" "JP-07" "JP-08"
              "JP-09" "JP-10" "JP-11" "JP-12" "JP-13" "JP-14" "JP-15" "JP-19" "JP-20"]
        west ["JP-16" "JP-17" "JP-18" "JP-21" "JP-23" "JP-24" "JP-25" "JP-26"
              "JP-27" "JP-28" "JP-29" "JP-30" "JP-31" "JP-32" "JP-33" "JP-34"
              "JP-35" "JP-36" "JP-37" "JP-38" "JP-39" "JP-40" "JP-41" "JP-42"
              "JP-43" "JP-44" "JP-45" "JP-46" "JP-47"]]
    (merge (into {} (map (fn [j] [j [:ntt-east]])) east)
           (into {} (map (fn [j] [j [:ntt-west]])) west)
           {"JP-22" [:ntt-west :ntt-east]})))

(def boundary-notes
  "区域境が県境と一致しない管轄。**畳まずに候補を複数返す**理由の記録。"
  {"JP-22" "静岡県: 電力は富士川を境に東（東京電力PG）／西（中部電力PG）。通信は NTT 西日本だが熱海市・裾野市の一部が NTT 東日本。"
   "JP-18" "福井県: 嶺南地域は関西電力送配電の区域。"
   "JP-24" "三重県: 一部地域が関西電力送配電の区域。"
   "JP-21" "岐阜県: 一部地域が関西電力送配電の区域。"
   "JP-28" "兵庫県: 一部地域が中国電力ネットワークの区域。"})

(defn jurisdiction? [j] (and (string? j) (contains? power-by-jurisdiction j)))

(defn boundary? [j] (contains? boundary-notes j))

(defn candidates
  "管轄 → 候補所有者。未収録の管轄は `nil`（空 vector ではない —— 空は
  『候補が無い』＝掲出不可と読めてしまう）。"
  [j]
  (when (jurisdiction? j)
    {:jurisdiction j
     :owner/candidates (vec (distinct (concat (get power-by-jurisdiction j)
                                              (get telecom-by-jurisdiction j))))
     :owner/power-candidates (get power-by-jurisdiction j)
     :owner/telecom-candidates (get telecom-by-jurisdiction j)
     :boundary? (boundary? j)
     :boundary-note (get boundary-notes j)
     :basis "供給区域・営業区域は法令および各社公表による制度的事実。柱 1 本の所有者を確定するものではない。"
     :sources [power-source telecom-source]}))

(defn coverage
  "収録した管轄の正直な申告。"
  []
  {:jurisdictions (count power-by-jurisdiction)
   :with-boundary-notes (count boundary-notes)
   :country "JP"
   :note (str "JP の 47 管轄を収録。うち " (count boundary-notes)
              " 件は区域境が県境と一致しないため候補を複数返す。"
              "JP 以外は未収録 —— 候補が出ないのは掲出不可ではなく未調査。")})

(defn describe
  "監査ログ用の一行。"
  [j]
  (if-let [c (candidates j)]
    (str j " → " (str/join "," (map name (:owner/candidates c)))
         (when (:boundary? c) (str " ⚠ " (:boundary-note c))))
    (str j " → 未収録")))
