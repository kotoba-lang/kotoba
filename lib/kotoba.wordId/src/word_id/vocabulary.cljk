(ns word-id.vocabulary
  "語彙 —— 語と数字の対応、そして語彙が ID に使えるかの検査。

  ## 語彙サイズは素数でなければならない

  これは切りのよさの問題ではない。checksum は桁の重み付き和を語彙サイズで
  割った余りで、合成数を法にすると零因子ができる。1024 語なら、重みが 2 の
  桁を 512 ずらす誤りは余りを変えない —— **検出できない誤りが構造的に
  存在する**。素数体には零因子が無いので、1 語の置換と 2 語の入れ替えは
  必ず余りを変える（`word-id.core` の checksum の項）。

  だから `problems` は素数でない語彙を**拒否する**。警告ではない。通せば、
  検出できるはずの誤りを静かに取りこぼす ID が発行され続ける。

  ## 語彙に課す 3 つの構造

  | 規則 | 何のためか |
  |---|---|
  | 語が全て異なる | 同じ語が 2 つの数字を意味したら decode が一意でない |
  | 先頭 4 文字が一意 | `lant` まで打てば `lantern` に確定する（BIP-39 と同じ） |
  | 相互の編集距離が 2 以上 | 距離 1 の対が同居すると、1 文字の誤りが**別の正しい語**になる |

  3 つめが効く場面: `crest` と `chest` が同居する語彙では、`crest` の打ち
  間違いが `chest` という完全に正当な語になり、checksum が最終的に弾いても
  「どちらのつもりだったか」を言えない。距離 2 以上なら、距離 1 以内の綴りは
  常にちょうど 1 語に復元できる。

  ここには IO が無い。語彙は値として渡す。既定の英語語彙は
  `word-id.english/words`（生成物）にあり、それも値であってファイルではない。"
  (:require [kotoba.lang.text :as str]))

(def schema "word-id.vocabulary.v1")

(def min-length 4)
(def max-length 7)
(def prefix-length 4)

(def max-payload-words
  "payload の語数の上限。**5 は host の整数精度から出た値で、好みではない。**

  `code` は語彙サイズの payload 乗までの整数を取る。JavaScript の number が
  誤差なく表せるのは 2^53 までで、1021^5 = 1.1e15 はその中、1021^6 = 1.1e18 は
  外。6 語を許すと JVM では正しく、ブラウザでは静かに丸まる ID ができる。

  実用上も 5 語で 1021^5 ≈ 1,100 兆通りある。"
  5)

(defn- prime? [n]
  (and (integer? n) (> n 1)
       (or (= n 2)
           (and (odd? n)
                (loop [d 3]
                  (cond (> (* d d) n) true
                        (zero? (mod n d)) false
                        :else (recur (+ d 2))))))))

(defn- shaped? [w]
  (and (string? w)
       (re-matches #"[a-z]+" w)
       (<= min-length (count w) max-length)))

(defn edit-distance-le-1?
  "編集距離が 1 以下か。距離そのものは要らないので 2 と分かった時点で打ち切る。
  純関数。語彙の検査と `word-id.core` の綴り復元の両方が使う。"
  [a b]
  (let [la (count a) lb (count b)
        gap (- la lb)
        gap (if (neg? gap) (- gap) gap)]
    (cond
      (= a b) true
      (> gap 1) false
      (= la lb) (<= (count (remove true? (map = a b))) 1)
      :else
      (let [[s l] (if (< la lb) [a b] [b a])]
        (loop [i 0 j 0 skipped? false]
          (cond
            (= i (count s)) true
            (= j (count l)) false
            (= (nth s i) (nth l j)) (recur (inc i) (inc j) skipped?)
            skipped? false
            :else (recur i (inc j) true)))))))

(defn problems
  "この語彙が ID に使えない理由。使えるときは空。

  真偽値でなく理由の列を返すのは `credential-assurance/policy-issues` と
  同じ理由 —— 『使えない』とだけ言われた人には直しようがない。"
  [words]
  (let [words (vec words)
        n (count words)
        bad-shape (remove shaped? words)
        dupes (->> words frequencies (keep (fn [[w c]] (when (< 1 c) w))) sort)
        prefixes (->> (filter shaped? words)
                      (group-by #(subs % 0 prefix-length))
                      (keep (fn [[p ws]] (when (< 1 (count ws)) [p (sort ws)])))
                      sort)
        near (let [ws (vec (distinct (filter shaped? words)))]
               (->> (for [i (range (count ws))
                          j (range (inc i) (count ws))
                          :when (edit-distance-le-1? (ws i) (ws j))]
                      [(ws i) (ws j)])
                    sort
                    vec))]
    (cond-> []
      (not (prime? n))
      (conj {:word-id.vocabulary/issue :word-id.vocabulary/size-not-prime
             :word-id.vocabulary/size n
             :word-id.vocabulary/basis
             "checksum は桁の重み付き和を語彙サイズで割った余り。合成数を法にすると零因子ができ、検出できない 1 語の誤りが構造的に存在する"})

      (seq bad-shape)
      (conj {:word-id.vocabulary/issue :word-id.vocabulary/malformed-words
             :word-id.vocabulary/words (vec (take 10 bad-shape))
             :word-id.vocabulary/basis
             (str "a-z のみ、" min-length "〜" max-length " 文字")})

      (seq dupes)
      (conj {:word-id.vocabulary/issue :word-id.vocabulary/duplicate-words
             :word-id.vocabulary/words (vec (take 10 dupes))
             :word-id.vocabulary/basis "同じ語が 2 つの数字を意味すると decode が一意でない"})

      (seq prefixes)
      (conj {:word-id.vocabulary/issue :word-id.vocabulary/prefix-collision
             :word-id.vocabulary/pairs (vec (take 10 prefixes))
             :word-id.vocabulary/basis
             (str "先頭 " prefix-length " 文字で確定できなくなる")})

      (seq near)
      (conj {:word-id.vocabulary/issue :word-id.vocabulary/words-too-close
             :word-id.vocabulary/pairs (vec (take 10 near))
             :word-id.vocabulary/basis
             "編集距離 1 の対が同居すると、1 文字の誤りが別の正しい語になる"}))))

(defn of
  "語の列から語彙の値を作る。

  検査は**しない** —— `problems` が別にあるのは、壊れた語彙を持ったまま
  『どこが壊れているか』を問える必要があるから。検査したい呼び出し側は
  `problems` を先に呼ぶ。`word-id.english/vocabulary` は生成時に検査済み。"
  ([words] (of words {}))
  ([words {:keys [id payload-words] :or {payload-words 3}}]
   (let [words (vec words)]
     {:word-id.vocabulary/schema schema
      :word-id.vocabulary/id id
      :word-id.vocabulary/words words
      :word-id.vocabulary/size (count words)
      :word-id.vocabulary/payload-words payload-words
      :word-id.vocabulary/by-word (into {} (map-indexed (fn [i w] [w i]) words))
      :word-id.vocabulary/by-prefix
      (into {} (comp (filter #(<= prefix-length (count %)))
                     (map-indexed (fn [i w] [(subs w 0 prefix-length) i])))
            words)})))

(defn configuration-problems
  "語彙そのものではなく、その**使い方**が壊れている理由。
  `problems` と分けているのは、同じ語彙が payload 語数だけ違う 2 通りの
  使われ方をしうるため。"
  [{:keys [:word-id.vocabulary/payload-words :word-id.vocabulary/size]}]
  (cond-> []
    (not (and (integer? payload-words) (<= 1 payload-words max-payload-words)))
    (conj {:word-id.vocabulary/issue :word-id.vocabulary/payload-words-out-of-range
           :word-id.vocabulary/actual payload-words
           :word-id.vocabulary/allowed [1 max-payload-words]
           :word-id.vocabulary/basis
           "code は host の整数精度（JS number は 2^53）を超えてはならない"})

    (and (integer? payload-words) (integer? size)
         (<= 1 payload-words max-payload-words)
         (> (Math/pow size payload-words) 9007199254740992))
    (conj {:word-id.vocabulary/issue :word-id.vocabulary/capacity-exceeds-precision
           :word-id.vocabulary/capacity (Math/pow size payload-words)
           :word-id.vocabulary/basis
           "この語彙サイズとこの語数では code が 2^53 を超え、JS 側で静かに丸まる"})))

(defn word [vocabulary digit]
  (get (:word-id.vocabulary/words vocabulary) digit))

(defn digit [vocabulary w]
  (get (:word-id.vocabulary/by-word vocabulary) w))

(defn resolve-word
  "打たれた綴りを語彙の 1 語に読む。読めないときは nil。

  順序が意味を持つ:

    1. 完全一致          —— 何も直していないので `:exact`
    2. 先頭 4 文字一致    —— `lant` → `lantern`。prefix は一意なので曖昧さが無い
    3. 編集距離 1        —— `lantren` → `lantern`。語彙が距離 2 以上を保つので
                            距離 1 以内の語はたかだか 1 つ

  3 が一意になるのは語彙の構造（`problems` の `words-too-close`）が保証して
  いるからで、この関数の性質ではない。検査していない語彙を渡すと、ここは
  たまたま最初に見つかった語を返す —— そうならないために `problems` がある。"
  [vocabulary given]
  (let [w (-> (str given) str/trim str/lower)
        words (:word-id.vocabulary/words vocabulary)]
    (cond
      (str/blank? w) nil

      (digit vocabulary w)
      {:word-id/read-as w :word-id/digit (digit vocabulary w) :word-id/basis :exact}

      :else
      (let [p (when (<= prefix-length (count w)) (subs w 0 prefix-length))
            d (get (:word-id.vocabulary/by-prefix vocabulary) p)]
        (if (and d (str/starts-with? (nth words d) w))
          {:word-id/read-as (nth words d) :word-id/digit d :word-id/basis :prefix}
          (let [near (->> words
                          (keep-indexed (fn [i x] (when (edit-distance-le-1? w x) [i x])))
                          (take 2)
                          vec)]
            (when (= 1 (count near))
              (let [[i x] (first near)]
                {:word-id/read-as x :word-id/digit i
                 :word-id/basis :edit-distance-1}))))))))
