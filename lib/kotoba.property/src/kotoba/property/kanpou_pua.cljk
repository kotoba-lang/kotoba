(ns kotoba.property.kanpou-pua
  "官報 PDF の私用領域（PUA）文字を読む。

   国立印刷局の PDF は Adobe-Npb1 という独自の CID コレクションを使っていて、
   poppler はそれを Unicode に写せない。結果、**数字・カンマ・ハイフン・項番が
   U+E000 以降の私用領域のまま出てくる** —— 本文の漢字かなは正しく出るので、
   一見すると読めているように見えるのが厄介なところ。

   実測 2026-08-18 の政府調達版: 61 種 2,336 文字が PUA。落札公示の金額
   7,304,000,000円 は 7 + PUA + 304 + PUA … と刻まれており、**数字のある行だけが
   静かに壊れる**。

   ## 表は推測ではなく突き合わせで作った

   同じ値が版面の別の場所に平文で出るところを使って確かめてある:

   - 号外政府調達第 <3 文字> 号 は第 152 号 → E88B=1, E88F=5, E88C=2
   - 令和 <E892> 年 <E892> 月 <E88B><E892> 日 は 令和 8 年 8 月 18 日
   - ページ番号 <E88D><E891> = 37、次ページが <E88D><E892> = 38

   3 つが同じ写像を指すので E88A..E893 = 0..9 と確定できる。カンマとハイフンも
   出現位置（720<EA75>550kWh、〒980<E61C>8430）で確かめた。

   **確かめていない PUA は写像に入れない。** 項番（丸数字）は値ではなく区切りとして
   使うので、区切り文字に置き換える。"
  (:require [kotoba.lang.text :as str]))

(def digit-base
  "U+E88A..U+E893 = 0..9。上記の 3 通りの突き合わせで確定。"
  0xE88A)

(def pua->text
  "値として写してよいと確かめた PUA だけ。ここに無いものは意味を推測しない。"
  (merge (into {} (for [i (range 10)]
                    [(char (+ digit-base i)) (str i)]))
         {(char 0xEA75) ","
          (char 0xE61C) "-"
          (char 0xE209) "\""
          (char 0xE20A) "\""}))

(def marker-lo 0xE7B0)
(def marker-hi 0xE7DF)
(def marker-origin
  "落札公示の項番 1 が U+E7D1。掲載順序は公告自身が冒頭で宣言しているので、
   6 が落札者、7 が落札価格であることは版面から読める。"
  0xE7D0)

(def sep
  "項番の区切りに使う制御文字。本文に現れない値を選んでいる —— 丸数字をそのまま
   残すと、公告本文中の丸数字と区別がつかなくなる。"
  (str (char 0x1F)))

(defn code-point
  "文字（cljs では 1 文字の文字列）-> コードポイント。

   **`(int c)` を使わない。** ClojureScript では c は文字ではなく文字列で、
   `(int \"\\ue7d1\")` は NaN を返す —— 比較が全部 false になり、項番は「値でも
   区切りでもない何か」として素通りし、**出力からは空白と区別がつかない**。
   同じ罠を gbizinfo の決算月でも踏んでいる（そちらは月が全件 nil になった）。"
  [c]
  #?(:clj (int c) :cljs (.charCodeAt (str c) 0)))

(defn marker? [c]
  (let [n (code-point c)] (and (>= n marker-lo) (<= n marker-hi))))

(defn marker-index [c]
  (when (marker? c) (- (code-point c) marker-origin)))

(defn normalize
  "確かめた PUA を平文に写し、項番は 区切り+番号+区切り に置き換え、
   残りの PUA（罫線など）は空白にする。"
  [s]
  (when s
    (str/join
     (for [c (str s)]
       (cond
         (contains? pua->text c) (get pua->text c)
         (marker? c) (str sep (marker-index c) sep)
         (and (>= (code-point c) 0xE000) (<= (code-point c) 0xF8FF)) " "
         :else (str c))))))

(defn fields
  "normalize 済みテキスト -> {項番 文字列}。同じ項番が 2 回出たら**最初を採る**
   （段組の折り返しで同じ番号が再登場する）。"
  [s]
  (let [parts (str/split (str s) (re-pattern sep))]
    (loop [[a b & more] parts acc {}]
      (if (nil? b)
        acc
        (let [n (when (re-matches #"\d+" (str a))
                  #?(:clj (Long/parseLong (str a)) :cljs (js/parseInt (str a) 10)))]
          (recur (cons b more)
                 (if (and n (not (contains? acc n)))
                   (assoc acc n (str/trim b))
                   acc)))))))

(defn page-accounting
  "pdftotext の出力を頁に割り、**テキスト層の無い頁**を数える。

   官報の PDF は全頁にスキャン画像が敷かれており、その上にテキスト層が載る頁と
   **載らない頁**がある。実測 2026-08-19（90 日窓・220 PDF・16,086 頁）:
   テキスト層が無い頁は **5,210（32%）**、本紙では **57%**。裁判所公告
   （破産・特別清算・再生）はまるごとそちら側で、1 頁あたり 40 文字ほど
   （柱と頁番号だけ）しか取れない。

   なぜこれを記録するか: **歩留まりの分母が読めた頁に限られる**。
   「見出し 6,499 に対してレコード 5,777（89%）」は*読めた頁の中での*値で、
   読めない頁に載っていた公告は**分子にも分母にも入っていない**。この 2 つを
   区別しないと、源泉の 3 分の 1 が見えていないことが数字の上で消える。"
  [text]
  (let [pages (let [ps (str/split (str text) #"\f")]
                (if (and (seq ps) (str/blank? (last ps))) (butlast ps) ps))]
    {:pages (count pages)
     :pages-without-text (count (filter #(< (count (str/trim (str %))) 300) pages))}))
