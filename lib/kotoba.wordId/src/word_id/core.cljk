(ns word-id.core
  "語で表す ID。`sponge-pumpkin-cellar-nestle` のような、口で言えて書き取れる
  識別子と、その裏の整数（この例では 888,888,888）との**全単射**。

  ## これは符号化であって、名前ではない

  ID は保存する文字列ではなく、**整数の別の書き方**である。だから正規化も
  比較も衝突検査も、語ではなく数でできる。表示のときだけ語に戻す。
  `parse` が綴りの揺れ（大文字・区切り・打ち間違い・途中まで）を吸収して
  同じ整数に落とすのは、この向きが決まっているから。

  ## 形

      sponge  pumpkin  cellar  |  nestle
      └───── payload ─────┘      └ check ┘
        3 語 = 1021^3 通り         1 語

  `1021` は語彙サイズ（`word-id.english`）で、素数である必要がある。
  payload 3 語で 1,064,332,261 通り。

  ## checksum が catch するもの、しないもの

  検査は 1 本の合同式:

      2·d₀ + 3·d₁ + 4·d₂ + … + 1·c  ≡  0  (mod p)

  重みが全て相異なり p が素数（＝零因子が無い）なので、

  - **1 語の置換は必ず検出する** —— w·δ ≢ 0
  - **2 語の入れ替えは必ず検出する** —— (wᵢ-wⱼ)(dᵢ-dⱼ) ≢ 0

  **検出はするが、位置は特定しない。** どの位置の誤りでも同じずれを説明でき
  てしまうため、『3 語目が違う』とは言えない。言えるのは『1 語だけ直せば
  正しくなる候補が P+1 個ある』ことで、それが `repairs`。ここを『誤りを訂正
  できる』と書くと嘘になる。

  ## 語彙は渡す

  この ns は IO を持たず、語彙も持たない。既定の英語語彙は
  `word-id.english/vocabulary`。"
  (:require [kotoba.lang.text :as str]
            [word-id.vocabulary :as vocabulary]))

(def schema "word-id.core.v1")

(def separator "-")

(defn- size [v] (:word-id.vocabulary/size v))
(defn- payload-words [v] (:word-id.vocabulary/payload-words v))

(defn capacity
  "この語彙とこの語数で表せる ID の総数。"
  [v]
  (reduce * 1 (repeat (payload-words v) (size v))))

(defn- weights
  "payload の重みは 2,3,4,…、check 桁の重みは 1。

  check 桁に 1 を与えて payload に 2 から振るのは、**全ての重みを相異ならせる**
  ため。check 桁と payload 桁の入れ替えも検出したいので、check 桁だけ別扱いに
  はできない。"
  [v]
  (conj (vec (map #(+ % 2) (range (payload-words v)))) 1))

(defn- weighted-sum [v digits]
  (mod (reduce + 0 (map * (weights v) digits)) (size v)))

(defn check-digit
  "payload の桁から check 桁を出す。合同式 Σwᵢdᵢ + c ≡ 0 を c について解くだけ。"
  [v payload]
  (let [p (size v)
        s (mod (reduce + 0 (map * (weights v) payload)) p)]
    (mod (- p s) p)))

(defn code->digits [v code]
  (let [p (size v)]
    (->> (range (payload-words v))
         (map (fn [i]
                (let [place (reduce * 1 (repeat (- (payload-words v) 1 i) p))]
                  (mod (quot code place) p))))
         vec)))

(defn digits->code [v payload]
  (let [p (size v)]
    (reduce (fn [acc d] (+ (* acc p) d)) 0 (take (payload-words v) payload))))

(defn text
  "語の列を表示形に。区切りは `-`。`parse` は区切りを問わないので、これは
  『どう見せるか』を 1 箇所に決めているだけ。"
  [words]
  (str/join separator words))

(defn encode
  "整数 → ID。範囲外の code は issue を返す（例外にしない —— 呼び出し側が
  発行器なら、範囲外は再抽選すべき値であって停止すべき事故ではない）。"
  [v code]
  (if-not (and (integer? code) (<= 0 code) (< code (capacity v)))
    {:word-id/issues [{:word-id/issue :word-id/code-out-of-range
                       :word-id/actual code
                       :word-id/capacity (capacity v)}]}
    (let [payload (code->digits v code)
          digits (conj payload (check-digit v payload))
          words (mapv #(vocabulary/word v %) digits)]
      {:word-id/code code
       :word-id/digits digits
       :word-id/words words
       :word-id/text (text words)})))

(defn decode
  "語の列 → 整数。語は語彙に**厳密に**在ること。綴りの揺れを許すのは `parse`。"
  [v words]
  (let [expected (inc (payload-words v))
        words (vec words)]
    (if (not= expected (count words))
      {:word-id/issues [{:word-id/issue :word-id/wrong-word-count
                         :word-id/actual (count words)
                         :word-id/expected expected}]}
      (let [digits (mapv #(vocabulary/digit v %) words)
            unknown (->> (map vector words digits)
                         (keep (fn [[w d]] (when (nil? d) w)))
                         vec)]
        (cond
          (seq unknown)
          {:word-id/issues [{:word-id/issue :word-id/unknown-words
                             :word-id/words unknown}]}

          (not (zero? (weighted-sum v digits)))
          {:word-id/issues [{:word-id/issue :word-id/checksum-mismatch
                             :word-id/words words
                             :word-id/basis
                             "1 語の置換か 2 語の入れ替えがある。どの語かはこの検査では決まらない"}]}

          :else
          {:word-id/code (digits->code v digits)
           :word-id/digits digits
           :word-id/words words
           :word-id/text (text words)})))))

(defn repairs
  "1 語だけ差し替えれば checksum が通る ID を、位置ごとに全て挙げる。

  checksum は位置を特定しないので、返るのは P+1 個の**同格の候補**であって
  訂正結果ではない。UI が『もしかして』を出すための材料で、自動で採用しては
  ならない —— どれも等しく正当な ID である。"
  [v words]
  (let [expected (inc (payload-words v))
        digits (mapv #(vocabulary/digit v %) words)]
    (when (and (= expected (count words)) (every? some? digits))
      (let [p (size v)
            ws (weights v)
            s (weighted-sum v digits)]
        (->> (range expected)
             (keep (fn [i]
                     ;; 位置 i の桁を δ ずらして和を 0 にする: wᵢ·δ ≡ -s
                     (let [w (nth ws i)
                           inv (loop [k 1] (if (= 1 (mod (* w k) p)) k (recur (inc k))))
                           delta (mod (* inv (- p s)) p)
                           fixed (mod (+ (nth digits i) delta) p)]
                       (when (not= fixed (nth digits i))
                         (let [repaired (assoc (vec words) i (vocabulary/word v fixed))]
                           {:word-id/position i
                            :word-id/was (nth words i)
                            :word-id/read-as (vocabulary/word v fixed)
                            :word-id/words repaired
                            :word-id/text (text repaired)
                            :word-id/code (digits->code
                                           v (assoc (vec digits) i fixed))})))))
             vec)))))

(defn parse
  "人が打った文字列 → ID。区切り・大文字小文字・前後の空白・途中までの綴り・
  1 文字の打ち間違いを吸収する。

  直した箇所は `:word-id/corrections` に**必ず載せる**。黙って直すと、利用者は
  自分の控えと画面の食い違いに気づけない。"
  [v s]
  (let [tokens (->> (str/split (str/lower (str s)) #"[^a-z]+")
                    (remove str/blank?)
                    vec)
        expected (inc (payload-words v))]
    (if (not= expected (count tokens))
      {:word-id/issues [{:word-id/issue :word-id/wrong-word-count
                         :word-id/actual (count tokens)
                         :word-id/expected expected
                         :word-id/given tokens}]}
      (let [reads (mapv #(vocabulary/resolve-word v %) tokens)
            unreadable (->> (map vector tokens reads)
                            (keep (fn [[t r]] (when (nil? r) t)))
                            vec)]
        (if (seq unreadable)
          {:word-id/issues [{:word-id/issue :word-id/unknown-words
                             :word-id/words unreadable}]}
          (let [words (mapv :word-id/read-as reads)
                corrections (->> (map vector tokens reads)
                                 (keep (fn [[t r]]
                                         (when (not= :exact (:word-id/basis r))
                                           {:word-id/given t
                                            :word-id/read-as (:word-id/read-as r)
                                            :word-id/basis (:word-id/basis r)})))
                                 vec)
                result (decode v words)]
            (cond-> result
              (seq corrections) (assoc :word-id/corrections corrections)
              (:word-id/issues result) (assoc :word-id/repairs (repairs v words)))))))))

;; ---------------------------------------------------------------------------
;; 発行
;; ---------------------------------------------------------------------------

(def ^:private draw-bytes 2)
(def ^:private draw-range 65536)

(defn digits-from-bytes
  "エントロピーの byte 列から payload の桁を引く。**一様**であること。

  1 桁につき 2 byte を読み、`65536 mod p` 個の上端を捨ててから余りを取る
  （棄却抽出）。`(mod n p)` をそのまま使うと、小さい数字が 1/65536 だけ多く
  出る —— 実害の無さそうな偏りだが、ID 空間の一様性は衝突確率の前提なので、
  『たぶん問題ない』で通さない。1021 語なら棄却率は 192/65536 ≈ 0.29%。

  byte が尽きたら issue を返す。足りない分を 0 で埋めない（エントロピーの
  ふりをした定数が混ざる）。"
  [v bytes]
  (let [p (size v)
        limit (- draw-range (mod draw-range p))]
    (if (> p draw-range)
      {:word-id/issues [{:word-id/issue :word-id/vocabulary-too-large
                         :word-id/size p :word-id/max draw-range}]}
      (loop [remaining (seq bytes) digits [] consumed 0]
        (cond
          (= (count digits) (payload-words v))
          {:word-id/digits digits :word-id/bytes-consumed consumed}

          (< (count remaining) draw-bytes)
          {:word-id/issues
           [{:word-id/issue :word-id/insufficient-entropy
             :word-id/bytes-consumed consumed
             :word-id/digits-drawn (count digits)
             :word-id/digits-needed (payload-words v)
             :word-id/basis
             "棄却抽出なので必要な byte 数は入力に依る。尽きたら足して呼び直す"}]}

          :else
          (let [[a b & rest'] remaining
                n (+ (* 256 (bit-and a 255)) (bit-and b 255))]
            (if (< n limit)
              (recur rest' (conj digits (mod n p)) (+ consumed draw-bytes))
              (recur rest' digits (+ consumed draw-bytes)))))))))

(defn mint
  "エントロピーから ID を 1 つ。乱数生成は**しない** —— byte を受け取る。

  この ns が CSPRNG を持たないのは移植性のためではなく検査可能性のため。
  固定の byte 列を渡せば結果が決まるので、発行の正しさをテストで固定できる。"
  [v bytes]
  (let [drawn (digits-from-bytes v bytes)]
    (if (:word-id/issues drawn)
      drawn
      (let [payload (:word-id/digits drawn)]
        (assoc (encode v (digits->code v payload))
               :word-id/bytes-consumed (:word-id/bytes-consumed drawn))))))
