(ns kotoba.property.intent-score
  "公開シグナルから **intent（いま動いている度合い）** を点数にする。I/O ゼロ。

   ## これは intent data ではない

   業界で intent data と呼ばれるのは、他社メディアでの検索・閲覧ログ（Bombora 等の
   publisher co-op）か、自社サイト訪問者の逆引きである。**ここが持っているのは
   どちらでもない** —— 公表された認定・調達・財務という**公開シグナル**だけ。
   だから予測力は本物の intent data より弱い。その差を名前で消さないために、
   この namespace は `intent-score` であって `intent-data` ではない。

   何を代理しているかは 1 行で言える: **『この会社は最近、設備投資の優遇を
   取りにいった』という公表事実**。

   ## 二段構えにする理由（この設計の要点）

   シグナルの被覆率が桁で違う（実測 2026-08-25、節税プール 16,947 社）:

     認定の種別・証明日・件数   100%
     政府調達の受注歴            3.9%
     決算月（財務ファイル）      2.2%

   これを 1 つの点数に畳むと、**測れなかった会社が「シグナルの無い会社」として
   下に沈む。** 決算月が取れないのはその会社が冷たいからではなく、財務ファイルが
   EDINET 由来で中小企業を載せていないからである。

   したがって:

     `:intent/base`   被覆 100% のシグナルだけで作る。**全社で比較可能。**
     `:intent/boost`  部分被覆のシグナル。**加点のみ。決して減点しない。**
     `:intent/measured` / `:intent/unmeasured`  どちらだったかを行に残す

   並べるのは `base`。`boost` は同点の並べ替えと注記に使う。**足して 1 列にしない。**

   ## 税務助言をしない

   認定は『いつ・どの計画が認定されたか』の公表事実であって、その企業がいま特定の
   税制を使えるという主張ではない。重みは「設備を買う意思にどれだけ近いか」を
   我々が置いた仮定で、**税制の強さの順位ではない。**"
  (:require [kotoba.lang.text :as str]))

(def dataset "lead-intent-score")

(def certification-weights
  "認定 -> 重み。**設備を買う意思にどれだけ近いか**で置いている。

   `経営力向上計画認定` が最大なのは、中小企業経営強化税制が設備の取得を前提に
   していて、認定と購入の距離が最も短いから。`事業継続力強化計画認定` は母数が
   最大（プールの大半）だが、防災計画そのものは設備購入を含まないことがあるので
   低い —— **母数が大きいことは、シグナルが強いことではない。**

   ⚠ この重みは仮定であって測定値ではない。返信率が測れたら、そこで直す。"
  {"経営力向上計画認定" 3.0
   "経営力向上計画に係る認定" 3.0
   "ＤＸ認定制度" 2.0
   "事業継続力強化計画認定" 1.0
   "連携事業継続力強化計画認定" 1.0})

(def half-life-months
  "リセンシーの半減期。12 ヶ月前の認定は今日の認定の半分の重み。

   ⚠ これも仮定。返信率で検証するまでは、順位を作るための単調な関数でしかない。"
  12.0)

(defn months-between
  "ISO の日付 2 つ -> 概算の月数（負にならない）。日の差は無視する ——
   半減期 12 ヶ月に対して日の精度は意味を持たない。"
  [from-iso to-iso]
  (let [parse (fn [s] (let [[y m] (str/split (str s) #"-")]
                        (when (and y m)
                          [#?(:clj (parse-long y) :cljs (js/parseInt y 10))
                           #?(:clj (parse-long m) :cljs (js/parseInt m 10))])))]
    (when-let [[fy fm] (parse from-iso)]
      (when-let [[ty tm] (parse to-iso)]
        (max 0 (+ (* 12 (- ty fy)) (- tm fm)))))))

(defn decay
  "経過月数 -> 0..1 の重み。半減期で指数的に落とす。"
  [months]
  (if (nil? months)
    ;; **日付が読めなかったときに 1.0 を返さない。** 読めなかった認定が
    ;; 今日の認定と同じ重みになると、壊れたデータが最も熱いリードになる。
    0.0
    ;; `double` は ClojureScript に無い。half-life が double なので、
    ;; そのまま割れば両方で浮動小数になる。
    (Math/pow 0.5 (/ months half-life-months))))

(defn stacking-multiplier
  "**種類**の数に応じた倍率。同じ認定を何度も更新しているのと、別々の制度を
   3 つ取りにいっているのは別の話なので、行数ではなく distinct な種類で数える。"
  [n-distinct-kinds]
  (case (int (max 0 n-distinct-kinds))
    0 0.0
    1 1.0
    2 1.3
    (min 1.6 (+ 1.3 (* 0.15 (- n-distinct-kinds 2))))))

(defn base-score
  "被覆 100% のシグナルだけで作る点数。**全社で比較可能。**

   `certs` は `[{:kind \"経営力向上計画認定\" :date \"2026-04-10\"} ...]`。
   `as-of` は基準日（ISO）。純関数にするために引数で受ける —— ここで
   『今日』を読むと、同じ入力が日によって別の答えを返す。"
  [certs as-of]
  (let [known (filter #(contains? certification-weights (:kind %)) certs)
        per-kind (->> known
                      (group-by :kind)
                      ;; 同じ認定を複数回持つ会社は、**最新の 1 件だけ**を数える。
                      ;; 更新のたびに線形に加算すると、古い認定を積んだ会社が
                      ;; 今日認定された会社を追い越す。
                      (map (fn [[kind rs]]
                             ;; ⚠ `max-key` を使わない。**数値しか比較できない。**
                             ;; ClojureScript では `>` が JS の文字列比較に落ちるので
                             ;; 黙って動き、JVM では ClassCastException になる ——
                             ;; 「片方の runtime でだけ通る」形。`sort-by` は
                             ;; `compare` を使うので両方で文字列を並べられる。
                             (let [latest (last (sort-by :date rs))]
                               (* (get certification-weights kind)
                                  (decay (months-between (:date latest) as-of)))))))]
    (* (reduce + 0.0 per-kind)
       (stacking-multiplier (count (distinct (map :kind known)))))))

(def boost-weights
  "部分被覆のシグナル -> 加点。**減点は無い。**"
  {:procurement 1.0          ;; 政府調達の受注歴（予算を執行したことがある）
   :fiscal-year-end-near 2.0 ;; 決算月が近い（取れた社にだけ効く）
   :listed-financials 0.5})  ;; 財務が公開されている（規模の裏付けが取れる）

(defn fiscal-month-near?
  "決算月が `as-of` の翌月から 3 ヶ月以内か。節税の設備投資は期末に寄るので、
   ここが唯一の『いつ当てるか』のシグナルになる —— ただし**取れる会社が
   2.2% しかない**（実測）ので、これを必須条件にしない。"
  [fiscal-end-month as-of]
  (when (and fiscal-end-month as-of)
    (let [[_ m] (str/split (str as-of) #"-")
          cur #?(:clj (parse-long m) :cljs (js/parseInt m 10))
          ahead (mod (- fiscal-end-month cur) 12)]
      (and (>= ahead 1) (<= ahead 3)))))

(defn score
  "1 社分のシグナル -> 点数と、**どれが測れてどれが測れなかったか**。

   `signals` は
   `{:certs [...] :procurement? bool-or-nil :fiscal-end-month int-or-nil}`。
   **nil は『測れなかった』であって『無い』ではない** —— だから
   `:intent/unmeasured` に名前が残り、点数には影響しない。"
  [signals as-of]
  (let [{:keys [certs procurement? fiscal-end-month]} signals
        base (base-score (or certs []) as-of)
        measured (cond-> #{:certifications}
                   (some? procurement?) (conj :procurement)
                   (some? fiscal-end-month) (conj :fiscal-year-end))
        unmeasured (cond-> #{}
                     (nil? procurement?) (conj :procurement)
                     (nil? fiscal-end-month) (conj :fiscal-year-end))
        boost (cond-> 0.0
                (true? procurement?) (+ (:procurement boost-weights))
                (some? fiscal-end-month) (+ (:listed-financials boost-weights))
                (fiscal-month-near? fiscal-end-month as-of) (+ (:fiscal-year-end-near boost-weights)))]
    {:source/dataset dataset
     :intent/base (/ (Math/round (* 1000.0 base)) 1000.0)
     :intent/boost (/ (Math/round (* 1000.0 boost)) 1000.0)
     :intent/measured (vec (sort (map name measured)))
     :intent/unmeasured (vec (sort (map name unmeasured)))
     :intent/as-of as-of}))

(defn rank
  "会社の列 -> base の降順、同点は boost の降順。

   **base + boost で並べない。** 足すと、決算月が取れた 2.2% の会社が、
   取れなかった 97.8% の上に、シグナルの強さではなく**被覆の差**で乗る。"
  [scored]
  (vec (sort-by (fn [s] [(- (:intent/base s)) (- (:intent/boost s))]) scored)))
