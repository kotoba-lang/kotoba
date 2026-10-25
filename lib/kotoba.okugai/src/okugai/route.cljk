(ns okugai.route
  "地点 → **誰に照会できるか**の状態（媒体非依存の部分だけ）。

  屋外広告の出稿は在庫検索ではなく照会から始まる。だから台帳が答えるべき問いは
  『空いているか』ではなく『**この地点について誰に聞けるか**』で、その状態は 3 つ:

    :routable             媒体 repo が窓口（媒体社・指定代理店）を確定できた
    :operator-known       観測に `operator` があり、その名前に直接照会できる
    :candidate-by-catalog その法域でその媒体を売る事業者がカタログに在る
    :unresolved           照会先が分からない（＝掲出不可ではなく、未調査）

  媒体固有の窓口解決（電柱なら供給区域→指定代理店）は**この ns には無い** ——
  媒体 repo が `:routable` / `:candidate-by-area` に上書きする。ここが持つのは
  『観測に operator があれば媒体を問わず照会先になる』という一般則だけ。

  実測（2026-08-04、都心 bbox の `advertising=*` 46 件）: `operator` タグは 13 件
  （28%）に付いていた —— 千代田区・商工中金・株式会社アトレ・東上野車坂町会・
  駿台予備学校。電柱の operator 充足率が実質 0% だったのと対照的で、**広告物の方が
  照会先を観測から得やすい**。

  ⚠ ただし `operator` は『その広告物を運営する者』であって媒体社とは限らない
  （自社広告の看板なら広告主自身、公共掲示板なら自治体）。だから
  `:operator-known` は『照会先の手がかりがある』であって『買える』ではない。"
  (:require [kotoba.lang.text :as str]
            [okugai.facts :as facts]
            [okugai.operator :as operator]))

(def statuses #{:routable :operator-known :candidate-by-catalog :unresolved})

(defn- blank? [s] (or (nil? s) (str/blank? (str s))))

(defn stamp
  "地点に照会状態を刻む。既に媒体 repo が `:site/route-status` を付けていれば
  **上書きしない**（媒体固有の解決の方が強い）。

  強さの順: 媒体 repo の解決 > 観測の operator > 媒体社カタログ > unresolved。
  observation の operator を catalog より優先するのは、**その地点について
  観測された事実**の方が『この市場でこの媒体を売っている』という一般論より
  強いから。"
  [site]
  (cond
    (:site/route-status site) site

    (not (blank? (:site/operator-raw site)))
    (assoc site :site/route-status :operator-known)

    :else
    (let [iso3 (facts/iso3-of (:site/jurisdiction site))
          cands (when iso3 (operator/candidates-for {:jurisdiction iso3
                                                     :medium (:site/medium site)}))]
      (if (seq cands)
        (assoc site :site/route-status :candidate-by-catalog
               :site/operator-candidates (mapv (comp name :operator/id) cands))
        (assoc site :site/route-status :unresolved)))))

(defn stamp-all [sites] (mapv stamp sites))

(def reachable-statuses
  "照会を組んでよい状態。**`okugai.order` もここを見る** —— 状態の集合を 2 箇所に
  書くと、新しい解決経路（媒体社カタログ等）を足したとき片方だけ更新されて
  『照会先はあるのに governor が止める』になる（実際に一度そうなった）。"
  #{:routable :operator-known :candidate-by-area :candidate-by-catalog})

(defn reachable-status? [status] (contains? reachable-statuses status))

(defn reachable?
  "照会を組んでよい状態か。`:unresolved` だけが不可。"
  [site]
  (reachable-status? (:site/route-status site)))

(defn summary
  "地点列 → 照会状態の内訳。カバレッジ申告に使う。"
  [sites]
  (let [f (frequencies (map #(or (:site/route-status %) :unresolved) sites))]
    {:by-status (into {} (map (fn [[k v]] [(name k) v])) f)
     :reachable (count (filter reachable? sites))
     :total (count sites)
     :note "unresolved は掲出不可ではなく照会先が未調査。operator-known は照会先の手がかりがあるという意味で、その相手が売っているとは限らない。"}))
