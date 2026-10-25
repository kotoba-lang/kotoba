(ns kotoba.property.kanpou-kaisan
  "官報の**解散公告**から「この会社は解散した」を集める。

   ## なぜこれが決定的か

   リード一覧・与信・調達先の判断で、最も強い 1 つの事実は「その会社がもう
   営業していない」である。解散は登記事項だが、**登記簿を横断で引く公開経路は無い**。
   官報の解散公告は会社法 499 条の債権者保護手続として**掲載が義務**で、
   1 件ごとに 商号・本店所在地・解散決議日・掲載日 が揃っている。

   ## 90 日窓であることが効き方を変える

   `kanpou.npb.go.jp` は直近 90 日しか無料で出さない。**収集しなかった日は永久に
   失われる**ので、これは「後でまとめて取る」ができないデータである
   （`kanpou-kessan` / `kanpou-chotatsu` と同じ性質）。

   ## 清算人は `:kaisan/liquidator` に取る

   各公告は末尾に「代表清算人 小林 祐季」の形で清算人を載せる。オーナー判断
   2026-09-08（`DATA-GOVERNANCE.md`）により、**法人の公告に印刷された役職と氏名は
   公開された法人情報として収集する。**

   商号の判定は従来どおり清算人行を**除いた**本文に対して行う（人名は法人格の語を
   持たないので `company-name-re` に当たらないが、住所や商号の断片と混ざる位置に
   在るため）。読むのと、名前の欄に入れるのは別の話である。

   1 ブロックに 2 名載る公告が在る（実測 2026-09-08、100 ブロック中 7 件）ので
   ベクタで持つ。折り返しで割れた行の連結は `kanpou-officer` が持つ。

   ## 縦書き PUA

   本文は縦書きで、句読点は `︑︒`、数字は Adobe-Npb1 の PUA。復号は
   `kanpou-pua/normalize`、和暦は `kanpou-kessan/wareki->date` を使う
   （**この 2 つを再実装しない**）。"
  (:require [kotoba.lang.text :as str]
            [kotoba.property.kanpou-kessan :as kk]
            [kotoba.property.kanpou-officer :as officer]))

(def dataset "kanpou-kaisan")
(def authority-id "JP/NPB-Kanpou")
(def licence "官報（国立印刷局）— 公告そのものは公表物")
(def attribution "出典：官報（国立印刷局）https://kanpou.npb.go.jp/ を加工して作成")

(def anchor "解散公告")

(def ^:private resolution-kinds
  ;; 何によって解散したか。**株主総会の決議**（株式会社）と**総社員の同意**
  ;; （合同会社・合名会社）で法的な経路が違うので、同じ値に潰さない。
  [[#"株主総会の?決議" :shareholder-resolution]
   [#"総社員の同意" :unanimous-member-consent]
   [#"定款所定の解散事由" :articles-provision]
   [#"存続期間の満了" :term-expiry]])

(defn resolution-kind [block]
  (some (fn [[re k]] (when (re-find re (str block)) k)) resolution-kinds))

(def ^:private liquidator-line-re
  ;; ここから先は個人。**行に到達したら読むのをやめる。**
  #"(代表)?清算人|破産管財人|管財人")

(def ^:private company-name-re
  ;; 法人格を名前の中に持つものだけを会社と認める。解散公告は法人にしか出ないが、
  ;; 縦書きの折り返しで住所の断片が混ざるので、**法人格の語を要求する**方が確実。
  #"(株式会社|有限会社|合同会社|合名会社|合資会社|一般社団法人|一般財団法人|医療法人|学校法人|宗教法人|社会福祉法人|特定非営利活動法人|協同組合|企業組合|信用金庫|信用組合|農業協同組合|相互会社)")

(def ^:private address-head-re
  ;; 都道府県か政令市の始まり。官報は「北海道旭川市…」「仙台市若林区…」の両形を使う。
  #"^(北海道|青森県|岩手県|宮城県|秋田県|山形県|福島県|茨城県|栃木県|群馬県|埼玉県|千葉県|東京都|神奈川県|新潟県|富山県|石川県|福井県|山梨県|長野県|岐阜県|静岡県|愛知県|三重県|滋賀県|京都府|大阪府|兵庫県|奈良県|和歌山県|鳥取県|島根県|岡山県|広島県|山口県|徳島県|香川県|愛媛県|高知県|福岡県|佐賀県|長崎県|熊本県|大分県|宮崎県|鹿児島県|沖縄県|札幌市|仙台市|さいたま市|千葉市|横浜市|川崎市|相模原市|新潟市|静岡市|浜松市|名古屋市|京都市|大阪市|堺市|神戸市|岡山市|広島市|北九州市|福岡市|熊本市)")

(def ^:private wareki-re
  #"(令和|平成|昭和)\s*(元|[0-9０-９]{1,2}|[〇零一二三四五六七八九十]{1,3})\s*年\s*([0-9０-９]{1,2}|[〇零一二三四五六七八九十]{1,3})\s*月\s*([0-9０-９]{1,2}|[〇零一二三四五六七八九十]{1,4})\s*日")

(defn- iso [{:keys [year month day]}]
  (when (and year month day)
    (str year "-" (when (< month 10) "0") month "-" (when (< day 10) "0") day)))

(defn block-dates
  "ブロックに出てくる和暦日付**すべて**を ISO で返す。

   ⚠ **位置で決議日を決められない。** 官報は縦書き段組みで、pdftotext は列を
   交互に出す。実測 2026-08-19: 「当社は︑株主総会の決議により令和八年六月三十日を
   もって解散」という公告で、**掲載日（七月二十二日）が「により解散」より前に
   現れ**、前置から拾う実装は掲載日を決議日として書き出した（179 件）。
   日付は前にも後にも来る。"
  [s]
  (->> (re-seq wareki-re (str s))
       (keep (fn [m] (iso (kk/wareki->date (first m)))))
       distinct
       vec))

(defn resolution-date
  "掲載日を除いた候補のうち**最も早いもの**を決議日とする。

   候補が 0 件なら入れない（決議日を持たない公告が実在する）。2 件以上あるのは
   第二回公告（第一回の掲載日も載る）で、そこでは早い方が決議日である ——
   遅い方を採ると第一回掲載日を決議日として書くことになる。

   **掲載日より後の日付は採らない**（決議が公告より後には来ない）。"
  [dates published-at]
  (let [cands (->> dates
                   (filter #(and % published-at (neg? (compare % published-at))))
                   sort)]
    (first cands)))

(defn- tidy [s]
  (-> (str s)
      (str/replace #"[︑︒、。]" "")
      (str/replace #"[\s　]+" "")
      str/trim))

(defn split-blocks
  "本文を 解散公告 ごとに切る。**見出しの数を返せることが要件**（歩留まりを
   隠さないため） —— 見出し N 件に対してレコードが N/3 件しか出ないパーサは、
   静かな日と同じ顔をする。"
  [text]
  (when text
    (let [t (str text)
          idxs (loop [from 0 acc []]
                 (let [i (str/index-of t anchor from)]
                   (if (nil? i) acc (recur (+ i (count anchor)) (conj acc i)))))]
      (mapv (fn [[a b]] (subs t a (or b (count t))))
            (map vector idxs (concat (rest idxs) [nil]))))))

(defn block->record
  "1 ブロック -> 1 レコード。読めなければ nil（推測しない）。

   `published-at` は号の日付（呼び出し側が渡す）。ブロック内の和暦日付は 2 つ出る:
   **解散を決議した日**と**掲載日**。前者が先に現れるので、最初の日付を決議日と
   して採り、掲載日は号から採る（本文の掲載日に頼ると、折り返しで拾い損なう）。"
  [block published-at]
  (let [lines (->> (str/split-lines (str block))
                   (map str/trim)
                   (remove str/blank?))
        ;; ⚠ **位置で切らない。** 縦書きの段組みでは商号が「代表清算人 …」の
        ;; **後ろ**に来ることがある（実測 2026-08-19: 112 見出しのうち 4 件がこれで
        ;; 落ちた）。個人名を避ける根拠は位置ではなく **法人格の語を要求すること**
        ;; —— 人名は `company-name-re` に当たらない。清算人行そのものだけ外す。
        body (remove #(re-find liquidator-line-re %) lines)
        ;; 読む位置は `lines`（清算人行を外す前）。`body` から読むと、外した行を
        ;; 探すことになる。
        liquidators (officer/officer-lines lines liquidator-line-re)
        joined (str/join "" body)
        ;; ⚠ **ブロックの最初の日付を決議日にしない。** 決議日を本文に持たない公告
        ;; （「…法律第二〇六条第二号の規定により解散」）では、最初に見つかる和暦は
        ;; **掲載日**で、それを決議日として書き出していた（実測 2026-08-19）。
        resolved (resolution-date (block-dates joined) published-at)
        ;; 段組みで商号が 2 行に割れることがある（`Ｓｅｔｉａ Ｏｓａｋａ特` +
        ;; `別目的会社`）。単独行に法人格が無ければ、隣接 2 行の連結も試す ——
        ;; ただし**住所で始まる行は連結の先頭にしない**（住所と商号が混ざる）。
        pairs (map (fn [[a b]] [a (str a b)]) (partition 2 1 body))
        name-line (or (some (fn [l] (when (re-find company-name-re l) l)) body)
                      (some (fn [[a ab]]
                              (when (and (not (re-find address-head-re (tidy a)))
                                         (re-find company-name-re ab))
                                ab))
                            pairs))
        addr-line (some (fn [l] (when (re-find address-head-re (tidy l)) l)) body)]
    (when (and name-line (re-find company-name-re (tidy name-line)))
      (cond-> {:source/dataset dataset
               :company/legal-name (tidy name-line)
               :kaisan/published-at published-at
               :kaisan/kind (or (resolution-kind joined) :unknown)}
        addr-line (assoc :company/address (tidy addr-line))
        resolved (assoc :kaisan/resolved-on resolved)
        ;; ⚠ `tidy` を当てない。**空白を畳むと姓と名の境界が消える** ——
        ;; 商号や住所では折り返しの空白は雑音だが、氏名ではそれが構造である
        ;; （`宮下 宏明` と `宮下宏明` は、後から姓を取り出せるかが違う）。
        ;; 句読点だけを落とす。
        (seq liquidators) (assoc :kaisan/liquidator
                                 (mapv #(str/trim (str/replace % #"[︑︒、。]" ""))
                                       liquidators))))))

(defn parse-section [text published-at]
  (keep #(block->record % published-at) (split-blocks text)))

(defn corpus-manifest
  [{:keys [observed-at record-count headlines issues window-days ambiguous-count
           pages pages-without-text]}]
  (cond-> {:corpus/manifest true
           :corpus/projection true
           :corpus/format :edn-lines
           :source/dataset dataset
           :source/authority authority-id
           :source/licence licence
           :source/attribution attribution
           :source/observed-at observed-at}
    window-days (assoc :corpus/window-days window-days)
    ;; 歩留まり: 見出し何件に対してレコード何件か。**これが無いと、
    ;; 3 分の 2 を静かに落としたパーサが「静かな日」と同じ顔をする。**
    headlines (assoc :projection/headlines headlines)
    issues (assoc :projection/issues issues)
    ;; **源泉のどれだけを読めなかったか。** 官報の PDF は全頁に画像が敷かれ、
    ;; テキスト層が載らない頁がある（実測 2026-08-19: 窓の 32%、本紙は 57%）。
    ;; 上の歩留まりは*読めた頁の中での*値なので、この 2 つが無いと
    ;; 「源泉の 3 分の 1 が見えていない」ことが数字から消える。
    pages (assoc :projection/source-pages pages)
    pages-without-text (assoc :projection/source-pages-without-text pages-without-text)
    (some? ambiguous-count) (assoc :corpus/ambiguous-count ambiguous-count)
    record-count (assoc :corpus/record-count record-count)))
