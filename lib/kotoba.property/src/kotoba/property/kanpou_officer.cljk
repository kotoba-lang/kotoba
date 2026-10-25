(ns kotoba.property.kanpou-officer
  "官報の公告に印刷された役職者の行を読む。

   オーナー判断 2026-09-08（`DATA-GOVERNANCE.md`）: **法人の公告に印刷された
   役職と氏名は公開された法人情報であり、収集する。** 決算公告が代表取締役を
   名乗るのも、解散公告が清算人を名乗るのも、公告そのものが法定だからである。

   ## 折り返しで名前が割れる — これが読み手の全部

   官報は 2 段組で、PDF のテキスト列は段の幅で行を割る。**割れ目は姓と名の間の
   空白に来る**ので、役職者行は 2 行で届くことがある:

       代表清算人 大堀
       力

   最初の行だけを保存すれば **名が黙って欠けた姓**になり、後から読む誰にも
   それが欠けていることは分からない。だから続きの行を連結する。

   ## 連結してよいと判断した根拠（実測 2026-09-08、号外第200号）

   1 号分の役職者行 181 本の内訳:

   | 形 | 本数 | 扱い |
   |---|---|---|
   | 役職 + 2 語（`荒木 真哉`） | 121 | そのまま完全 |
   | 役職 + 3 字以上の 1 語（`杉山公美弥`） | 22 | そのまま完全（姓名間に空白が無い印刷） |
   | 役職 + 2 字以下の 1 語 | 38 | **次の行が名だった（標本 8 件すべて）** |

   `大堀`/`力`、`劉`/`永強`、`尤`/`振宇`、`翁`/`嘉俊`、`江`/`勝弘`、`金`/`爀`、
   `矢澤`/`学`、`陳`/`美娟`。連結しなければ 21% を落とすか、姓だけを名として
   書き出すことになる。

   ⚠ **連結は姓と名の間に空白を 1 つ置く。** 官報は姓名を空白で区切って印刷する
   ので、これは区切りの捏造ではなく復元である。ただし**割れ目が姓の途中に来た
   公告があれば、空白は間違った位置に入る** —— 実測した 8 件はすべて姓と名の
   境界で割れていたが、それは 8 件の観測であって不変条件ではない。

   ## 連結しない条件

   続きの行は 1〜4 字の漢字・かなだけで、法人格の語も数字も含まないこと。
   次の公告の見出し（`解散公告`）や住所行を名として吸い込まないための床である。"
  (:require [kotoba.lang.text :as str]))

(def ^:private name-continuation-re
  ;; 続きの行として認める形。漢字・ひらがな・カタカナ・長音・中黒だけの 1〜4 字。
  #"^[一-龥ぁ-んァ-ヶー・]{1,4}$")

(def ^:private not-a-name-re
  ;; 見出し・法人格・体裁語。1〜4 字に収まってしまうものを名指しで外す。
  #"(公告|株式会社|有限会社|合同会社|貸借対照表|官報|決算|解散|清算|破産|以上|記)")

(defn name-after
  "`line` の役職語より後ろ、氏名として印刷された部分。

   役職は複合する（`代表取締役` + `社長`）。役職語だけを削ると残りの `社長` が
   姓として読め、**折り返しで割れた行が完全な氏名に見える** —— 実測 2026-09-08、
   最初の版がこれで `代表取締役社長 中澤` を完全と判定した。だから役職語の後ろの
   **最初の空白まで**を役職の続きとして落とす。空白が無い行（`代表取締役杉山公美弥`）
   では、役職語の直後からすべてを氏名とする。"
  [line title-re]
  (when-let [m (re-find title-re (str line))]
    (let [m (if (vector? m) (first m) m)
          idx (str/index-of line m)
          after (subs line (+ idx (count m)))
          title-tail (re-find #"^[^\s　]*[\s　]+" after)]
      (str/trim (if title-tail (subs after (count title-tail)) after)))))

(defn- whole-name-after?
  "役職語の後ろが、完全な氏名として読める形か。

   2 語（`荒木 真哉`）か、3 字以上の 1 語（`杉山公美弥`）だけを完全とする。
   2 字以下の 1 語は折り返しで割れた姓の形なので、ここでは完全としない。"
  [line title-re]
  (let [parts (remove str/blank? (str/split (str (name-after line title-re)) #"[\s　]+"))]
    (boolean (or (>= (count parts) 2)
                 (and (= 1 (count parts)) (>= (count (first parts)) 3))))))

(defn whole-officer-line
  "`line` が、それ自身で完全な役職者行ならその行、でなければ nil。

   **連結を試みない版。** 次の行が氏名の続きだと言えない位置 —— 決算公告で
   商号の 1 行「上」に代表者が来る形 —— で使う。そこで連結すると、続きとして
   商号を吸い込む。"
  [line title-re]
  (let [l (str/trim (str line))]
    (when (and (re-find title-re l) (whole-name-after? l title-re)) l)))

(defn officer-line
  "`lines` の `i` 番目を役職者行として読む。読めなければ nil。

   割れている行は次の行を連結して返す。連結しても完全にならない場合は nil を
   返す —— **欠けた名前を書き出すより、欄が無い方がよい。**"
  [lines i title-re]
  (let [line (str/trim (str (nth lines i nil)))]
    (when (re-find title-re line)
      (if (whole-name-after? line title-re)
        line
        (let [nxt (str/trim (str (nth lines (inc i) nil)))]
          (when (and (seq nxt)
                     (re-matches name-continuation-re nxt)
                     (not (re-find not-a-name-re nxt))
                     ;; 役職の後ろに 1 字以上あること。役職だけで終わる行
                     ;; （`株式会社かんぽ生命保険 代表執行役`）に次の行の語を
                     ;; 名として付けない。
                     (seq (str (name-after line title-re))))
            (str line " " nxt)))))))

(defn officer-lines
  "`lines` の中の役職者行を、印刷順に、割れたものは連結して返す。

   1 ブロックに 2 人以上載る公告が在る（実測 2026-09-08、100 ブロック中 7 件が
   清算人 2 名）ので、1 人に畳まない。"
  [lines title-re]
  (into [] (keep #(officer-line lines % title-re)) (range (count lines))))
