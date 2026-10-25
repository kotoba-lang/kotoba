(ns kotoba.property.kanpou-kessan
  "官報の会社決算公告から、**非上場企業の決算期**を読む。

   ## なぜこれが要るか

   決算期はどの税制の窓に居るかを決めるのに、公開バルクがどこにも無い。
   gBizINFO の財務は EDINET 由来なので上場・有報提出会社だけ、法人番号 registry
   にも invoice registry にも事業年度は無い。残る公開経路は 1 つだけ ——
   **会社法 440 条の決算公告**で、官報に毎日載る。

   実測 2026-08-18 の号外 1 号だけで **152 件**（貸借対照表の要旨 185 箇所）。
   1 日あたりこの規模なので、年 4 万社程度が流れる。

   ## 3 つの制約を先に書く

   1. **無料で読めるのは直近 90 日だけ。** 過去分は買うしかないので、これは
      「今から貯める」データであって「今すぐ揃う」データではない。cell が
      毎日回して初めて意味を持つ、この workspace で最初の本当に日次な仕事。
   2. **公告の履行率が低い。** 義務ではあるが中小の大半は出していない。だから
      カバレッジは母集団の一部で、**出していない会社と決算期が無い会社は
      区別できない**（不在を 0 と読まない）。
   3. **法人番号が載っていない。** 商号と所在地しか無いので、法人番号への接続は
      名寄せになる —— それは `houjin-bangou-projection/resolve-names` の仕事で、
      同名 2 社を解決しない規律もそこが持つ。

   ## 代表者名は落とす

   公告には代表取締役の氏名が載る。`gbizinfo/basic-record` と同じ理由で捨てる。

   出典：官報（国立印刷局）https://kanpou.npb.go.jp/ を加工して作成"
  (:require [kotoba.lang.text :as str]
            [kotoba.property.kanpou-officer :as officer]))

(def source-id "kanpou-kessan-koukoku")
(def authority-id "JP/NPB-Kanpou")
(def dataset "kanpou-kessan")
(def licence "官報（国立印刷局）— 公告そのものは公表物")
(def attribution "出典：官報（国立印刷局）https://kanpou.npb.go.jp/ を加工して作成")

(def ^:private fullwidth-digits
  {"０" "0" "１" "1" "２" "2" "３" "3" "４" "4"
   "５" "5" "６" "6" "７" "7" "８" "8" "９" "9"})

(defn- parse-int
  "Portable digits->long. `js/parseInt` does not exist on the JVM, and this
   namespace is .cljc because the parser has to be testable without Node."
  [s]
  (when (and s (re-matches #"\d+" (str s)))
    #?(:clj (Long/parseLong (str s))
       :cljs (js/parseInt (str s) 10))))

(def ^:private kanji-digits
  {"〇" 0 "零" 0 "一" 1 "二" 2 "三" 3 "四" 4 "五" 5 "六" 6 "七" 7 "八" 8 "九" 9})

(defn kanji->int
  "「三十一」-> 31, 「八」-> 8, 「元」-> 1. Only the range a date or a period
   number needs (< 1000), which is all 官報 uses in these positions.

   Measured: 52 of the dates in one issue's 決算公告 section are written this way
   — a parser that only reads Arabic numerals silently treats every 縦書き notice
   as unparseable."
  [s]
  (when (and s (re-matches #"[〇零一二三四五六七八九十百元]+" (str s)))
    (if (= "元" s)
      1
      (let [chars (vec (str s))]
        (loop [i 0 total 0 current 0]
          (if (>= i (count chars))
            (+ total current)
            (let [c (str (nth chars i))]
              (cond
                (= c "百") (recur (inc i) (+ total (* 100 (max 1 current))) 0)
                (= c "十") (recur (inc i) (+ total (* 10 (max 1 current))) 0)
                :else (recur (inc i) total (+ (* 10 current) (get kanji-digits c 0)))))))))))

(defn normalize-digits [s]
  (when s (reduce-kv (fn [acc z a] (str/replace acc z a)) (str s) fullwidth-digits)))

(def ^:private era-base
  ;; 元年 = base + 1. Only the eras a current 公告 can carry.
  {"令和" 2018 "平成" 1988 "昭和" 1925})

(defn wareki->date
  "「令和８年６月20日現在」/「令和八年三月三十一日現在」 -> {:year :month :day}.

   Both numeral systems occur in the same issue (縦書き notices use kanji), and
   元年 is written 元 rather than 1 — a year that would otherwise parse as 0."
  [s]
  (when-let [m (re-find #"(令和|平成|昭和)\s*(元|[0-9０-９]{1,2}|[〇零一二三四五六七八九十]{1,3})\s*年\s*([0-9０-９]{1,2}|[〇零一二三四五六七八九十]{1,3})\s*月\s*([0-9０-９]{1,2}|[〇零一二三四五六七八九十]{1,4})\s*日"
                        (str s))]
    (let [[_ era y mo d] m
          num (fn [x] (or (parse-int (normalize-digits x)) (kanji->int x)))
          y (if (= "元" y) 1 (num y))
          mo (num mo)
          d (num d)]
      (when (and (get era-base era) y mo d (<= 1 mo 12) (<= 1 d 31))
        {:year (+ (get era-base era) y) :month mo :day d}))))

(defn- iso-date [{:keys [year month day]}]
  (when (and year month day)
    (str year "-" (when (< month 10) "0") month "-" (when (< day 10) "0") day)))

(def ^:private header-re
  ;; pdftotext spaces the headline out («第 71 期決算公告», «第 47 期 決 算 公 告»),
  ;; so every character between the digits and 告 has to tolerate whitespace.
  #"第\s*([0-9０-９]+)\s*期\s*決\s*算\s*公\s*告")

(def ^:private form-token-re
  ;; Every legal form that files a 決算公告, not just the four company types.
  ;; Measured in one issue: 一般社団法人・公益財団法人・社会福祉法人・公益信託 all
  ;; appear, and each one a pattern misses is a whole notice lost.
  #"(株式会社|有限会社|合同会社|合名会社|合資会社|相互会社|信用金庫|信用組合|labour|一般社団法人|一般財団法人|公益社団法人|公益財団法人|社会福祉法人|学校法人|医療法人|宗教法人|特定非営利活動法人|協同組合|農業協同組合|生活協同組合|公益信託|企業年金基金|健康保険組合)")

(def ^:private representative-re #"代表|理事長|組合長|会長|社長")

(def ^:private address-re
  #"(都|道|府|県|市|区|郡|町|村)")

(def ^:private officer-line-re
  ;; The line before the company name is USUALLY the address, but in some
  ;; notices it is the representative. `address-re` only asks whether one of
  ;; nine characters appears anywhere in the line, and those characters are
  ;; also ordinary in Japanese surnames -- 田村, 上村, 中島, 大川. So a line
  ;; that is a person passes the address test on the strength of their name.
  ;;
  ;; Measured 2026-09-08: two records in the committed projection carried
  ;; `:company/address "代表取締役 田村 圭二"` and `"代表取締役 上村 昌志"`,
  ;; published 2026-08-21 and 2026-08-25. Both got in through 村.
  ;;
  ;; The line is kept, as `:company/representative` -- an officer named in a
  ;; company's own statutory notice is public corporate information and this
  ;; workspace collects it (owner decision 2026-09-08, DATA-GOVERNANCE.md).
  ;; What this regex is for is the OTHER half of that: a person is not an
  ;; address. Putting them in `:company/address` is a wrong value that reads as
  ;; a right one, which is the failure this whole parser is written against.
  #"(代表取締役|取締役|代表社員|業務執行社員|代表理事|理事長|理事|監事|組合長|会長|社長|専務|常務|執行役|清算人|代表者|代表)")

(def ^:private officer-title-re
  ;; 役職語だけ。「完全な氏名が続いているか」と「折り返しで割れた行の連結」は
  ;; `kanpou-officer` が持つ —— 決算公告と解散公告で同じ判断をするため。
  #"(代表取締役|取締役|代表社員|業務執行社員|代表理事|理事長|理事|監事|組合長|会長|社長|専務|常務|執行役|清算人|代表者)")

(def ^:private page-furniture-re
  ;; The two-column layout interleaves running heads into the text stream.
  #"^(官|報|火曜日|月曜日|水曜日|木曜日|金曜日|土曜日|日曜日|\(号外第.*|令和\s+年.*|\s*)$")

(def ^:private anchor-re
  ;; The parenthesised date on the balance sheet — or the property list, for a
  ;; trust — is the anchor, NOT the headline.
  ;;
  ;; Measured on 号外第184号: 154 headlines but 185 balance sheets, because a
  ;; notice's headline is not always 「第N期決算公告」. Splitting on the headline
  ;; therefore loses whole notices before any field is read, and the loss is
  ;; invisible — every remaining notice parses fine.
  ;; The date can sit a line break away from the heading, so the gap tolerates
  ;; whitespace rather than requiring the paren to be adjacent.
  #"(?:貸借対照表の要旨|貸借対照表|財産目録)[\s\S]{0,12}?[（(]([^）)]{6,40})[）)]")

(def ^:private period-re #"第\s*([0-9０-９]+|[〇零一二三四五六七八九十]{1,4})\s*期")

(defn- anchor-indexes
  "Start offsets of every anchor in the text, in order. Portable: `re-seq` gives
   the matches but not where they are, so the scan walks the string."
  [text]
  (loop [from 0 acc []]
    (let [rest-text (subs text from)
          m (re-find anchor-re rest-text)]
      (if-not m
        acc
        (let [whole (first m)
              at (+ from (str/index-of rest-text whole))]
          (recur (+ at (count whole)) (conj acc {:at at :date-text (second m)})))))))

(defn split-blocks
  "Whole-section text -> one block per notice, anchored on the balance-sheet
   date.

   Two windows, and they are not interchangeable: `:head` is the run BEFORE the
   anchor, where the name, address and period sit, and `:body` is the run AFTER
   it, where the table figures do. Reading 資本金 out of `:head` takes the
   PREVIOUS notice's capital — measured: 株式会社本田 came out with トヨタＬ＆Ｆ
   福島's 30,000千円, a wrong number that looks entirely valid."
  [text]
  (let [anchors (vec (anchor-indexes text))]
    (map-indexed (fn [i {:keys [at date-text]}]
                   (let [prev-end (if (zero? i) 0 (:at (nth anchors (dec i))))
                         next-at (if (< (inc i) (count anchors))
                                   (:at (nth anchors (inc i)))
                                   (count text))
                         head (subs text (max prev-end (- at 900)) at)
                         body (subs text at (min next-at (+ at 1200)))]
                     {:text head
                      :body body
                      :date-text date-text
                      ;; The LAST 第N期 before the anchor, not the first: the
                      ;; two-column layout puts the neighbouring notice's period
                      ;; earlier in the same window, and taking the first one
                      ;; attaches 株式会社本田's balance sheet to 第43期 instead
                      ;; of 第71期 — again a wrong field that looks valid.
                      :period (let [ms (re-seq period-re head)]
                                (when (seq ms)
                                  (let [v (second (last ms))]
                                    (or (parse-int (normalize-digits v))
                                        (kanji->int v)))))}))
                 anchors)))

(defn- clean-lines [text]
  (->> (str/split-lines text)
       (map str/trim)
       (remove #(re-matches page-furniture-re %))))

(defn block->record
  "One block -> a company record, or nil without both a name and a date."
  [{:keys [period text body date-text]} published-at]
  (let [lines (vec (clean-lines text))
        name-idx (last (keep-indexed (fn [i l]
                                       (when (and (re-find form-token-re l)
                                                  (not (re-find representative-re l))
                                                  (<= (count l) 40))
                                         i))
                                     lines))
        name (when name-idx (nth lines name-idx))
        line-above (when (and name-idx (pos? name-idx)) (nth lines (dec name-idx)))
        address (when (and line-above
                           (re-find address-re line-above)
                           (not (re-find officer-line-re line-above))
                           (>= (count line-above) 5))
                  line-above)
        ;; 代表者は商号の**下**に来るのが普通で、上に来る公告もある。実測
        ;; 2026-09-08、号外第200号の 2 日分 74 レコードでは上に来た行は 0 件
        ;; だった —— 上だけを見ていた最初の版は、住所欄の誤りは直したが代表者を
        ;; ほとんど 1 件も集めなかった。
        ;;
        ;; 下の行は折り返しで割れるので連結を許す。上の行は許さない ——
        ;; そこで連結すれば「続き」として商号を吸い込む。
        representative (or (when name-idx
                             (officer/officer-line lines (inc name-idx) officer-title-re))
                           (when line-above
                             (officer/whole-officer-line line-above officer-title-re)))
        bs-date (wareki->date date-text)
        capital (some-> (re-find #"資\s*本\s*金\s*([\d,]+)" (str body)) second (str/replace "," ""))]
    (when (and name bs-date)
      (cond-> {:source/dataset dataset
               :company/legal-name name
               ;; The whole point of the dataset: the same attribute gBizINFO
               ;; fills for listed companies, filled here for unlisted ones.
               :company/fiscal-year-end-month (:month bs-date)
               :company/fiscal-year-end (iso-date bs-date)}
        period (assoc :kessan/period period)
        address (assoc :company/address address)
        representative (assoc :company/representative representative)
        published-at (assoc :kessan/published-at published-at)
        ;; 千円単位で刷られるので、そのまま円として読ませない。
        capital (assoc :company/capital-stock-yen (str (* 1000 (parse-int capital))))))))

(defn parse-section
  "pdftotext output of the 決算公告 pages -> records."
  [text published-at]
  (keep #(block->record % published-at) (split-blocks text)))

(defn corpus-manifest
  [{:keys [observed-at issues record-count window-days]}]
  (cond-> {:corpus/manifest true
           :corpus/projection true
           :corpus/format :edn-lines
           :source/dataset dataset
           :source/authority authority-id
           :source/licence licence
           :source/attribution attribution
           :source/observed-at observed-at}
    issues (assoc :corpus/issues (vec issues))
    window-days (assoc :corpus/window-days window-days)
    record-count (assoc :corpus/record-count record-count)))
