(ns kuro.ansi
  "ANSI/VT の解釈 —— 端末エミュレーションの、正直に言える範囲。

  ここまで `kuro` は「1 command 入れて 1 receipt 出る」だけで、stdout は生の
  バイト列だった。実際のコマンド出力にはエスケープが混ざる（`git status` の
  色、テストランナーの進捗バー）。それを素のテキストとして扱うと、画面には
  `ESC[32m` が見え、`\\r` で上書きされるはずの進捗行が何十行にもなる。

  ## 実装している範囲

  - **SGR**（`CSI … m`）—— 太字 / 微光 / 斜体 / 下線 / 反転 / 取り消し線、
    前景・背景の 8 色 + bright 8 色 + 256 色 + 24-bit truecolor、および reset。
  - **CSI / OSC / その他エスケープの除去** —— 解釈しないものは*捨てる*。
    画面に生の制御列を出さない。
  - **`\\r` の行内上書き** —— 進捗バーが正しく 1 行に畳まれる。
  - **`\\b`（後退）とタブ展開**（既定 8 桁）。
  - **OSC 8 hyperlink は URI だけを捨てる** —— リンクされただけの語は
    画面に現れるべきなので、`ESC ] 8 ; … ESC \\` の URI 部分だけを
    除去する（`click` ごと消えたら log として嘘になる）。

  ## 実装していない範囲（ここが誤読されると困る）

  **これはスクリーンエミュレータではない。** カーソル位置指定（`CSI H`）、
  スクロール領域、代替画面、折り返し、スクロールバック
  グリッドは解釈せず**捨てる**。`vim` や `htop` の出力をここに通しても画面には
  ならない。行志向の出力（ビルドログ、テスト、git）を読めるようにするための層。

  唯一の例外が `CSI n K`（行消去）で、これは**捨てない** —— 進捗バーは
  `\\r` だけでは畳めず（上書きが短いと右側の残骸が残る）、実際のプログラムは
  その後ろに `CSI K` を出して行末までを消す。解釈して `lines` に渡すことで
  「進捗バーが 1 行になる」を実現する（`spans` が `{:erase n}` として残す）。

  完全な端末には PTY が要る（`kuro.host.node` は pipe しか持たない）。それは
  別の決定であって、この名前空間はその決定を先取りしない。

  純粋 `.cljc`。IO も状態も持たない。"
  (:require [kotoba.lang.text :as str]))

;; ---------------------------------------------------------------- SGR

(def ^:private base-colors
  ["black" "red" "green" "yellow" "blue" "magenta" "cyan" "white"])

(defn- named-color [n bright?]
  (when-let [c (get base-colors n)]
    (if bright? (str "bright-" c) c)))

(def empty-style
  "SGR reset 後の状態。style map に現れないキーは「指定なし」を意味する。"
  {})

(defn- extended-color
  "`38;5;n`（256 色）と `38;2;r;g;b`（truecolor）を読む。

  戻り値は [色 残りのパラメータ]。壊れた列（パラメータ不足）では色を付けず、
  残りをそのまま返す —— **不完全なエスケープで例外を投げない**。ログの末尾が
  切れているのは日常であって、それで receipt の描画全体を落とす理由はない。"
  [params]
  (case (first params)
    5 (if-let [n (second params)]
        [{:index n} (drop 2 params)]
        [nil (rest params)])
    2 (if (>= (count params) 4)
        [{:rgb (vec (take 3 (rest params)))} (drop 4 params)]
        [nil (rest params)])
    [nil (rest params)]))

(defn apply-sgr
  "SGR パラメータ列を現在の style に適用した新しい style。"
  [style params]
  (loop [style style params (seq params)]
    (if-not params
      style
      (let [p (first params) more (next params)]
        (cond
          (or (nil? p) (zero? p)) (recur empty-style more)
          (= p 1) (recur (assoc style :bold true) more)
          (= p 2) (recur (assoc style :dim true) more)
          (= p 3) (recur (assoc style :italic true) more)
          (= p 4) (recur (assoc style :underline true) more)
          (= p 7) (recur (assoc style :inverse true) more)
          (= p 9) (recur (assoc style :strike true) more)
          (= p 22) (recur (dissoc style :bold :dim) more)
          (= p 23) (recur (dissoc style :italic) more)
          (= p 24) (recur (dissoc style :underline) more)
          (= p 27) (recur (dissoc style :inverse) more)
          (= p 29) (recur (dissoc style :strike) more)
          (<= 30 p 37) (recur (assoc style :fg (named-color (- p 30) false)) more)
          (= p 39) (recur (dissoc style :fg) more)
          (<= 40 p 47) (recur (assoc style :bg (named-color (- p 40) false)) more)
          (= p 49) (recur (dissoc style :bg) more)
          (<= 90 p 97) (recur (assoc style :fg (named-color (- p 90) true)) more)
          (<= 100 p 107) (recur (assoc style :bg (named-color (- p 100) true)) more)
          ;; `seq` is required: (drop 2 '(5 214)) is an EMPTY seq, not nil, and
          ;; the loop's (if-not params …) treats it as "more parameters", reads
          ;; (first '()) = nil, and resets the style. Measured — every extended
          ;; colour silently became {} before this.
          (= p 38) (let [[c rest-params] (extended-color more)]
                     (recur (if c (assoc style :fg c) style) (seq rest-params)))
          (= p 48) (let [[c rest-params] (extended-color more)]
                     (recur (if c (assoc style :bg c) style) (seq rest-params)))
          :else (recur style more))))))

;; ------------------------------------------------------------ scanning

(def ^:private esc \u001b)

(defn- code
  "文字のコードポイント。**`int` は使えない** —— ClojureScript では文字は
   1 文字の文字列で、`(int \"m\")` は NaN になる。NaN との比較はすべて false
   なので、`scan-csi` は終端バイトを永遠に見つけられず『切れた CSI』として
   **全部捨てていた**。JVM のテストは緑のまま、cljs では出力が丸ごと消える
   —— まさにサーバが走る側だけが壊れていた（実測 2026-08-03）。"
  [c]
  #?(:clj (int c)
     :cljs (.charCodeAt (str c) 0)))

(defn- parse-params
  "ECMA-48: 省略されたパラメータは 0。したがって `CSI m` は `CSI 0 m`（reset）で
   あって「何もしない」ではない。空を [] にすると色が消えずに残り続ける。"
  [s]
  (if (str/blank? s)
    [0]
    (mapv #(if (str/blank? %) 0 (parse-long %))
          (str/split s #";" -1))))

(defn- scan-csi
  "`ESC [` の後ろを読む。[final-char params-string end-index] または nil。"
  [s i]
  (let [n (count s)]
    (loop [j i]
      (if (>= j n)
        nil                            ; 途中で切れている — 呼び出し側が捨てる
        (let [c (nth s j)]
          (if (<= 0x40 (code c) 0x7e)
            [c (subs s i j) (inc j)]
            (recur (inc j))))))))

(defn- scan-osc
  "`ESC ]` の後ろを BEL または ST（`ESC \\`）まで読み飛ばす。end-index。"
  [s i]
  (let [n (count s)]
    (loop [j i]
      (cond
        (>= j n) n
        (= (nth s j) \u0007) (inc j)
        (and (= (nth s j) esc) (< (inc j) n) (= (nth s (inc j)) \\)) (+ j 2)
        :else (recur (inc j))))))

(defn- merge-adjacent
  "style の等しい隣接 span を 1 つに畳む。

   ビルドツールは同じ SGR を各トークンの前に出し直すことが多く、畳まないと
   `[31ma[31mb[31mc` が 3 span になる。描画側が「span = 意味の単位」と読むので、
   冗長な分割は下流の見た目とテストの両方を壊す。"
  [out]
  (reduce (fn [acc e]
            (let [prev (peek acc)]
              (if (and prev (:text prev) (:text e) (= (:style prev) (:style e)))
                (conj (pop acc) (update prev :text str (:text e)))
                (conj acc e))))
          [] out))

(defn spans
  "文字列を `[{:text … :style {…}} …]` に。style が同じ隣接片は連結する。

  消去（`CSI n K`）だけは `{:erase n}` として残す —— `lines` が行を組み立てる
  ときに要る。それ以外の非 SGR エスケープは捨てる。

  解釈しないエスケープは捨てる。制御文字（`\\r` `\\b` タブ）はテキストとして
  残し、行の組み立ては `lines` が行う —— span 化と行の折り畳みは別の関心。"
  [s]
  (let [s (str s) n (count s)]
    (loop [i 0, style empty-style, buf "", out []]
      (let [flush (fn [out buf style]
                    (if (seq buf) (conj out {:text buf :style style}) out))]
        (if (>= i n)
          (merge-adjacent (flush out buf style))
          (let [c (nth s i)]
            (if (= c esc)
              (let [nx (when (< (inc i) n) (nth s (inc i)))]
                (cond
                  (= nx \[)
                  (if-let [[final params end] (scan-csi s (+ i 2))]
                    (cond
                      (= final \m)
                      (recur end (apply-sgr style (parse-params params))
                             "" (flush out buf style))

                      ;; **消去だけは捨てない。** 進捗バーは `\r` だけでは畳めない
                      ;; ——上書きが短いと右側の残骸が残る（実測: "progress\rdone"
                      ;; は実機でも "doneress"）。実際のプログラムは CR のあとに
                      ;; `CSI K` を出して行末までを消す。これを捨てると
                      ;; 「進捗バーが 1 行になる」という主張が嘘になる。
                      (= final \K)
                      (recur end style "" (conj (flush out buf style)
                                                {:erase (first (parse-params params))}))

                      ;; その他の CSI（カーソル移動・スクロール…）は捨てる
                      :else (recur end style buf out))
                    ;; 切れた CSI — 残り全部を捨てる
                    (recur n style buf out))

                  (= nx \]) (recur (scan-osc s (+ i 2)) style buf out)
                  (nil? nx) (recur n style buf out)
                  ;; ESC + 中間バイト(0x20–0x2F)* + 終端バイト。
                  ;; 「ESC + 1 文字」で済ませると `ESC ( B`（G0 文字集合指定、
                  ;; ncurses が普通に出す）の `B` が本文に混ざる —— 実測で出た。
                  :else
                  (let [end (loop [j (inc i)]
                              (if (and (< j n) (<= 0x20 (code (nth s j)) 0x2f))
                                (recur (inc j))
                                (min n (inc j))))]
                    (recur end style buf out))))
              (recur (inc i) style (str buf c) out))))))))

(defn plain
  "エスケープを除いた素のテキスト。"
  [s]
  (str/join (keep :text (spans s))))

;; --------------------------------------------------------------- lines

(defn- apply-controls
  "1 行分の entry 列に `\r`（行頭復帰）・`\b`（後退）・タブ展開・`CSI n K`
  （行消去）を適用して、最終的な span 列にする。

  上書きは**文字単位**で行う —— `\r` の後ろが短ければ既存の右側は残る（実機と
  同じ。だから進捗バーは `\r` だけでは畳めず、`CSI K` が要る）。"
  [entries tab-width]
  (let [put (fn [cells col ch style]
              (let [cells (if (< col (count cells))
                            cells
                            (into cells (repeat (- (inc col) (count cells)) [\space {}])))]
                (assoc cells col [ch style])))]
    (loop [entries (seq entries) col 0 cells []]
      (if-not entries
        (->> cells
             (partition-by second)
             (mapv (fn [group] {:text (str/join (map first group))
                                :style (second (first group))}))
             (filterv #(seq (:text %))))
        (let [{:keys [text style erase]} (first entries)]
          (cond
            erase
            (recur (next entries) col
                   (case erase
                     ;; 0: カーソルから行末まで / 1: 行頭からカーソルまで / 2: 行全体
                     0 (vec (take col cells))
                     1 (vec (map-indexed (fn [i c] (if (<= i col) [\space {}] c)) cells))
                     2 []
                     cells))

            text
            (let [[col cells]
                  (reduce (fn [[col cells] ch]
                            (case ch
                              \return [0 cells]
                              \backspace [(max 0 (dec col)) cells]
                              \tab (let [stop (* tab-width (inc (quot col tab-width)))]
                                     (loop [c col cells cells]
                                       (if (< c stop)
                                         (recur (inc c) (put cells c \space style))
                                         [c cells])))
                              [(inc col) (put cells col ch style)]))
                          [col cells] text)]
              (recur (next entries) col cells))

            :else (recur (next entries) col cells)))))))

(defn lines
  "テキストを**行ごとの span 列**にする。opts: `:tab-width`（既定 8）。

  `(lines \"\\u001b[32mok\\u001b[0m\\nprogress\\rdone\")`
  ;; => [[{:text \"ok\" :style {:fg \"green\"}}] [{:text \"done\" :style {}}]]

  span の style は改行をまたいで持続する（実際の端末と同じ）。"
  ([s] (lines s {}))
  ([s opts]
   (let [tab-width (:tab-width opts 8)]
     (loop [spans* (seq (spans s)), current [], out []]
       (if-not spans*
         (mapv #(apply-controls % tab-width) (conj out current))
         (let [{:keys [text style] :as entry} (first spans*)
               ;; erase entry には :text が無い。現在行にそのまま積む
               ;; （行の切り出しではなく、行内の消去を指示する control）。
               parts (when text (str/split text #"\n" -1))]
           (if (nil? parts)
             (recur (next spans*) (conj current entry) out)
             (if (= 1 (count parts))
             (recur (next spans*) (conj current {:text text :style style}) out)
             (let [head (conj current {:text (first parts) :style style})
                   mids (mapv (fn [p] [{:text p :style style}]) (butlast (rest parts)))
                   tail [{:text (last parts) :style style}]]
               (recur (next spans*) tail (into (conj out head) mids)))))))))))

(defn truncate-lines
  "先頭 `n` 行に切り詰め、切り捨てた行数を返す。

  `[lines dropped]`。receipt の stdout は 1 MiB まで許されるので、画面に
  そのまま出すと落ちる。**切ったことを黙らない**ために件数を返す。"
  [ls n]
  (if (<= (count ls) n)
    [ls 0]
    [(vec (take n ls)) (- (count ls) n)]))
