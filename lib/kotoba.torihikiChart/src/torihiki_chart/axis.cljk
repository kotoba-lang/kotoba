(ns torihiki-chart.axis
  "軸の目盛りとラベル。**ここも整数で閉じる。**

  `candle` が整数で集計する理由（同一性）は軸にも当てはまる —— 目盛りの位置が
  丸めで 1 tick ずれると、同じ板を見ている二人が違う価格線を見る。目盛り値も
  ドル表記も、float を経由せずに作る。

  ドル表記が地味に難しいのは、`68010` tick が `$68,010.00` になるまでに
  『tick → cent → ドルと小数部』という 2 段の除算があるからで、素直に
  `(/ cents 100.0)` と書くと 2 進小数で `.99999` が出る。`quot` と `rem` で
  整数のまま桁を作る。"
  (:require [kotoba.lang.text :as str]))

;; ── 目盛り ───────────────────────────────────────────────────────────────────

(def ^:private mantissas
  "目盛り幅の梯子。1 / 2 / 5 の 10 冪。人が読める間隔はこの 3 つしかない
  —— 3 や 7 刻みの軸は、目盛りの間隔を数えないと値が読めない。"
  [1 2 5])

(defn nice-step
  "`raw` 以上で最小の『1 / 2 / 5 × 10^k』。整数のみ、`raw < 1` でも 1 を返す。

  10 冪を掛けながら探すので、`raw` が大きくても有限回で止まる。"
  [raw]
  (loop [pow 1]
    (if-let [m (first (filter #(>= (* % pow) raw) mantissas))]
      (* m pow)
      (recur (* 10 pow)))))

(defn ticks
  "`[lo hi]` を覆う目盛り値のベクタ（昇順、両端を含みうる）。

  `target` は**目安**であって約束ではない —— 綺麗な間隔に丸める以上、本数は
  前後する。本数を約束すると間隔が汚くなり、軸として読めなくなる方を選ぶ
  ことになる。

  `lo` = `hi`（板が一点に潰れている）のときは 1 本だけ返す。0 除算を避ける
  ためではなく、値が 1 つしか無いときに複数の目盛りを描くのが嘘だから。"
  [[lo hi] target]
  (if (= lo hi)
    [lo]
    (let [span (- hi lo)
          step (nice-step (max 1 (quot span (max 1 target))))
          start (* step (quot lo step))
          start (if (< start lo) (+ start step) start)]
      (vec (take-while #(<= % hi) (iterate #(+ % step) start))))))

(defn height-ticks
  "block height 軸の目盛り。`heights` は実際に存在する足の height（昇順）。

  価格軸と違い **存在する height の中から選ぶ**。約定の無いブロック区間には
  足が無く、そこに目盛りを立てると『無い足を指す線』になる。

  `target` 本になるよう等間隔に間引く。最後の 1 本は必ず含める —— 右端は
  『今』であり、チャートを見る人が最初に見る場所。"
  [heights target]
  (let [v (vec heights)
        n (count v)]
    (cond
      (zero? n) []
      (<= n target) v
      :else (let [stride (max 1 (quot n target))]
              (->> (range 0 n stride)
                   (map v)
                   (#(if (= (last %) (peek v)) % (concat % [(peek v)])))
                   vec)))))

;; ── ラベル ───────────────────────────────────────────────────────────────────

(defn- group-digits
  "`68010` → `\"68,010\"`。3 桁区切り。負号は呼び出し側で付ける。

  右から数える。左から『3 桁ごと』で切ると桁数が 3 の倍数でないときに
  ずれる —— 先頭の group だけが短いのが正しい形。"
  [n]
  (->> (str n)
       reverse
       (partition-all 3)
       (map #(apply str (reverse %)))
       reverse
       (str/join ",")))

(defn format-usd
  "tick 値 → `\"$68,010.00\"`。

  `tick-cents` は 1 tick が何セントか（node の `/market` の `:tick`）。
  **整数のまま**桁を作る —— `(/ cents 100.0)` は 2 進小数なので、`$67,989.99`
  のような 1 セントずれた価格を平気で表示する。

  負値も扱う（含み損の表示に使う）。符号を先に外して絶対値で桁を作るのは、
  `rem` が負値に対して負を返す言語差を踏まないため。"
  [tick-cents level]
  (let [cents (* level tick-cents)
        neg? (neg? cents)
        a (if neg? (- cents) cents)
        d (quot a 100)
        c (rem a 100)]
    (str (when neg? "-") "$" (group-digits d) "."
         (when (< c 10) "0") c)))

(defn format-height
  "block height ラベル。**`#` を必ず前置する。**

  これは装飾ではない。この軸は時刻ではなくブロック番号で、1 ブロックの実時間は
  一定でないので（view change や Durable Object の eviction で伸びる）、
  等間隔のブロック足を等間隔の時間として読まれると誤読になる。`#4218` は
  時刻に見えないが `12:04` は時刻に見える —— 見た目でそれを防ぐ。"
  [h]
  (str "#" h))

(defn format-lots
  "lot 整数の出来高ラベル。4 桁以上は 3 桁区切り。

  単位を付けない —— lot が何を意味するかは市場ごとに違い（node の `/market` の
  `:lot`）、ここで `BTC` などと書くと市場を 1 つ仮定したことになる。"
  [lots]
  (group-digits lots))
