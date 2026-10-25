(ns kotoba.property.kanpou-chotatsu
  "官報 政府調達版の**落札者等の公示**から、誰がどの契約を幾らで受注したかを読む。

   ## なぜ原典なのか

   gBizINFO の調達情報は各省の公表データを集約したもので、読むのは安いが
   gBizINFO への依存が残る。落札公示は**発注者自身が官報に出した一次公告**で、
   同じ事実をこちらから取れば依存が消える。

   ## 何が入って、何が入らないか

   官報の政府調達版に載るのは **WTO 政府調達協定の対象案件**（一定金額以上）だけ。
   中小規模の受注は載らないので、**ここに無いことは受注が無いことではない**。
   実測 2026-08-18 の第152号は落札公示 1 件（長野自動車道の補強工事、73 億円）で、
   同じ号の大半は入札公告（これから発注するもの）である。

   ## 掲載順序は公告自身が宣言している

   各行の頭に丸数字の項番が振られ、その意味は section の冒頭に印字される:

     1 品目分類番号 / 2 調達件名及び数量 / 3 調達方法 / 4 契約方式 /
     5 落札決定日 / 6 落札者の氏名及び住所 / 7 落札価格 / 8 入札公告日 …

   項番は PDF の私用領域文字なので `kotoba.property.kanpou-pua` が区切りに直す。
   フィールドの意味を位置から推測する必要はない —— **版面が言っている**。

   属性は gBizINFO の調達レコードと**同じ `:grant/*`** にしてある。「国からこの
   会社に何が渡ったか」を出所を跨いで 1 クエリで聞けるようにするためで、出所を
   区別したいときは `:source/dataset` を見る。

   出典：官報（国立印刷局）https://kanpou.npb.go.jp/ を加工して作成"
  (:require [kotoba.lang.text :as str]
            [kotoba.property.kanpou-pua :as pua]))

(def source-id "kanpou-chotatsu-rakusatsu")
(def authority-id "JP/NPB-Kanpou")
(def dataset "kanpou-chotatsu")
(def licence "官報（国立印刷局）— 公告そのものは公表物")
(def attribution "出典：官報（国立印刷局）https://kanpou.npb.go.jp/ を加工して作成")

(def ^:private furniture-re
  ;; 段組の間に running head が挟まる。フィールド値がそこまで伸びるので切る。
  #"\s*\d*\s*令和\s*\d+\s*年\s*\d+\s*月\s*\d+\s*日\s*[月火水木金土日]曜日")

(defn- clean [v]
  (when v
    (-> (str v)
        ;; 段組の折り返しで、次の公示のヘッダがフィールド値の末尾に流れ込む。
        ;; 契約責任者以降は別の公示のものなので落とす —— 実測で 673 件中 7 件の
        ;; 社名に「契約責任者…中国支社長本園民雄」がくっついており、**担当者の
        ;; 氏名が社名フィールドに入っていた**。
        (str/split #"契約責任者") first
        (str/replace (re-pattern pua/sep) " ")
        (as-> x (first (str/split x furniture-re)))
        (str/replace #"\(号外政府調達第[^)]*\)" "")
        str/trim)))

(defn- squeeze
  "社名は段の折り返しで途中に改行が入る（鹿島建設株式 / 会社）。空白を落とす。"
  [v]
  (when v (str/replace (str v) #"[\s　]" "")))

(defn wareki-ymd
  "落札公示の日付は 和暦の 年.月.日（8. 6. 8 = 令和8年6月8日）。西暦へ。

   **元号が印字されない**ので、令和として読む。号自体が令和の官報なので同じ紙面の
   日付と矛盾しないが、改元をまたぐと壊れる —— そのときはここが直す場所。"
  [v]
  (when-let [m (re-find #"(\d{1,2})\s*[.．]\s*(\d{1,2})\s*[.．]\s*(\d{1,2})" (str v))]
    (let [n (fn [x] #?(:clj (Long/parseLong x) :cljs (js/parseInt x 10)))
          y (+ 2018 (n (nth m 1)))
          mo (n (nth m 2))
          d (n (nth m 3))]
      (when (and (<= 1 mo 12) (<= 1 d 31))
        (str y "-" (when (< mo 10) "0") mo "-" (when (< d 10) "0") d)))))

(def ^:private prefecture-re
  #"(北海道|東京都|京都府|大阪府|(?:青森|岩手|宮城|秋田|山形|福島|茨城|栃木|群馬|埼玉|千葉|神奈川|新潟|富山|石川|福井|山梨|長野|岐阜|静岡|愛知|三重|滋賀|兵庫|奈良|和歌山|鳥取|島根|岡山|広島|山口|徳島|香川|愛媛|高知|福岡|佐賀|長崎|熊本|大分|宮崎|鹿児島|沖縄)県)")

(def ^:private branch-re
  #"(本店|本社|支店|支社|支店営業部|営業所|営業部|事業所|出張所|センター|工場)$")

(def ^:private ligatures
  {"㈱" "株式会社" "㈲" "有限会社" "㈳" "社団法人" "㈶" "財団法人"})

(def max-name-length
  "これを超えたら社名ではない。

   1 行に複数の落札者が並ぶ公示がある（№1、241〜244…：株式会社A…№2〜5…：株式会社B…）。
   そのまま名前として通すと、**照合に失敗するだけで、失敗したことは出力に出ない**。
   長さで弾いて数える。"
  40)

(defn- name+address
  "6 の値 -> [社名 住所 支店]。

   住所の付き方は 3 通りある: 括弧で囲む / 直に続ける（アクセンチュア株式会社東京都
   港区赤坂…）/ 書かない。**括弧しか見ていなかったとき、589 名のうち 403 が
   未一致だった** —— 社名に住所がくっついたまま照合していたためで、法人番号側には
   当然そんな名前は無い。"
  [v]
  (when v
    (let [v (-> (squeeze (clean v))
                (str/replace #"^[\d,]+円" "")
                (as-> x (reduce-kv (fn [acc a b] (str/replace acc a b)) x ligatures)))
          [name address]
          (cond
            (re-find #"[（(]" v)
            (let [m (re-find #"^(.*?)[（(]([^）)]{4,})[）)]" v)]
              (if m [(nth m 1) (nth m 2)] [(str/replace v #"[（(].*$" "") nil]))

            (re-find prefecture-re v)
            (let [at (str/index-of v (second (re-find prefecture-re v)))]
              [(subs v 0 at) (subs v at)])

            :else [v nil])
          branch (second (re-find branch-re (str name)))
          name (if branch (str/replace name branch-re "") name)]
      (when-not (str/blank? name)
        [name address branch]))))

(defn- amount-yen [v]
  (when-let [m (re-find #"([\d,]{2,})\s*円" (str (clean v)))]
    (str/replace (second m) "," "")))

(defn- put [m k v] (if (or (nil? v) (str/blank? (str v))) m (assoc m k v)))

(defn row->record
  "1 行分の項番マップ -> 受注レコード。**6（落札者）と 7（落札価格）の両方**が
   無いものはレコードにしない —— section 冒頭の掲載順序の凡例も同じ項番を持つので、
   それを弾く床でもある。社名が長すぎる行（1 行に複数落札者）は `nil` を返し、
   呼び出し側が数える。"
  [fields {:keys [published-at agency agency-code contract-officer]}]
  (let [[name address branch] (name+address (get fields 6))
        amount (amount-yen (get fields 7))]
    (when (and (not (str/blank? (str name)))
               (<= (count name) max-name-length)
               amount)
      (cond-> {:source/dataset dataset
               ;; gBizINFO の調達レコードと同じ属性。出所は :source/dataset。
               :grant/kind "procurement"
               :company/legal-name name
               :grant/amount-yen amount}
        true (put :grant/title (clean (get fields 2)))
        true (put :grant/date (wareki-ymd (get fields 5)))
        true (put :award/item-class (clean (get fields 1)))
        true (put :award/method (clean (get fields 3)))
        true (put :award/contract-type (clean (get fields 4)))
        true (put :award/announced-at (wareki-ymd (get fields 8)))
        true (put :company/address address)
        true (put :award/branch branch)
        true (put :grant/ministry agency)
        ;; 契約責任者欄をそのまま。`:grant/ministry` は組織名だけに保つが、
        ;; **落とすのではなく別の欄に置く** —— 法人の公告に印刷された役職と氏名は
        ;; 公開された法人情報で、この workspace はそれを収集する（オーナー判断
        ;; 2026-09-08、DATA-GOVERNANCE.md）。切り出した「人の部分」ではなく印刷
        ;; されたままの 1 行を持つのは、どこで切るかを推測しないため —— 病院長 の
        ;; 「長」のように、役職の一部が組織名の末尾と繋がって印刷される。
        true (put :award/contract-officer contract-officer)
        true (put :award/agency-code agency-code)
        true (put :award/published-at published-at)))))

(def ^:private agency-re #"契約責任者\s*([^（(\n]{2,60})")
(def ^:private officer-title-re
  ;; 発注機関の表記には担当者の役職と氏名が続く（支社長 金田 泰明 /
  ;; 財務担当理事 鈴木 康晴 / 理事 井上 賢一）。役職語で切って組織名だけを残す。
  ;;
  ;; **最初の版は「支社長」等しか知らず、「財務担当理事 鈴木 康晴」がそのまま
  ;; committed data に入った** —— 公表物であっても個人名を持ち歩かない、という
  ;; 線を自分で越えていた。役職語は広く採り、それでも残る「姓 名」は下の
  ;; `trailing-personal-name-re` が落とす。
  #"(代表執行役|執行役|支社長|支店長|工場長|支所長|事務局長|事務所長|病院長|院長|総長|学長|校長|園長|館長|センター長|社長|副社長|専務|常務|部長|次長|課長|所長|局長|署長|統括|総括|理事長|理事|監事|参事|審議官|管理官|会長|責任者|担当官|支出負担行為担当官|分任支出負担行為担当官)")

(def ^:private head-and-name-re
  ;; 「…宇都宮病院長 杉山公美弥」— 組織名の末尾が 長 で、その後ろに氏名が続く形。
  ;; 役職語リストで切ると 病院 の途中を割ってしまうので、こちらを先に当てる。
  ;; 姓と名の間に空白が無い氏名（杉山公美弥）もあるので、空白は 長 の直後だけを見る。
  #"長[\s　]+[一-龥ぁ-んァ-ヶ]{2,10}\s*$")

(def ^:private trailing-role-re
  ;; 役職語で切ると「…国立印刷局財務担当」のように担務が残る。組織名の末尾に
  ;; 付く担務も落とす。
  ;; 担務は列挙する。`[^\s]{0,6}担当$` のようなワイルドカードは
  ;; 「独立行政法人国立印刷局財務担当」から**組織名まで削って**
  ;; 「独立行政法人国」にした（実測）。
  #"(?:財務|会計|経理|総務|契約|調達|人事|管理|支出)?担当$")

(def ^:private trailing-personal-name-re
  ;; 「… 鈴木 康晴」「… 井上 賢一」— 末尾の 姓+空白+名。組織名は空白で切れた
  ;; 2 語で終わらないので、これで落ちるのは実質的に人名だけ。
  #"[\s　][一-龥ぁ-んァ-ヶ]{1,5}[\s　]+[一-龥ぁ-んァ-ヶ]{1,5}\s*$")

(def ^:private agency-furniture-re
  ;; 段組の running head が発注機関の位置に流れ込むことがある（「月曜日」など）。
  #"^(月曜日|火曜日|水曜日|木曜日|金曜日|土曜日|日曜日|官|報|令和.*)$")

(def ^:private agency-code-re #"◎調達機関番号\s*(\d{2,4})")

(defn parse-section
  "政府調達版 1 号分のテキスト -> 受注レコード。

   行は項番 1 で始まるので、そこで割る。発注機関は**走査しながら憶える**:
   契約責任者の行は掲載順序の凡例より前に出るが、凡例自身も項番 1 を含むので、
   直前のチャンクだけを見ると発注機関が見えない（実測でそうなった）。"
  [text published-at]
  (let [n (pua/normalize text)
        chunks (vec (str/split n (re-pattern (str pua/sep "1" pua/sep))))]
    (loop [i 0 agency nil code nil officer nil acc []]
      (if (>= i (count chunks))
        acc
        (let [chunk (nth chunks i)
              raw-responsible (some-> (last (re-seq agency-re chunk)) second str/trim clean)
              agency' (or (some-> raw-responsible
                                  (str/replace head-and-name-re "")
                                  (str/split officer-title-re) first
                                  (str/replace trailing-personal-name-re "")
                                  str/trim
                                  (str/replace trailing-role-re "")
                                  str/trim
                                  (as-> a (when-not (or (str/blank? a)
                                                        (re-matches agency-furniture-re a))
                                            a)))
                          agency)
              ;; 組織名と印刷された 1 行が違うときだけ持つ（普通の行で同じ値を
              ;; 2 度書かないため）。組織名が採れなかった行 —— running head が
              ;; 流れ込んだ「月曜日」など —— では持たない。
              officer' (if (and raw-responsible agency'
                                (not= raw-responsible agency')
                                (str/starts-with? raw-responsible agency'))
                         raw-responsible
                         (if raw-responsible nil officer))
              code' (or (some-> (last (re-seq agency-code-re chunk)) second) code)
              rec (when (pos? i)
                    (let [fields (assoc (pua/fields (str pua/sep "1" pua/sep chunk)) 1
                                        (clean (first (str/split chunk (re-pattern pua/sep)))))]
                      (row->record fields {:published-at published-at
                                           :agency agency'
                                           :agency-code code'
                                           :contract-officer officer'})))]
          (recur (inc i) agency' code' officer' (if rec (conj acc rec) acc)))))))

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
