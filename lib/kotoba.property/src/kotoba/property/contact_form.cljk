(ns kotoba.property.contact-form
  "問い合わせページの HTML -> **こちらから正直に埋めて送れるか**の判定。I/O は 1 バイトも無い。

   `contact-point` が答えるのは『そこに連絡点が在るか』（200 が返り、form か mailto か
   連絡を表す語 + 入力欄が在る）まで。**それは到達可能性であって、送信可能性ではない。**
   200 で入力欄が在っても、CAPTCHA が在れば送れないし、JS が描くフォームなら静的取得
   では埋められないし、必須項目に『お客様番号』が在れば**正直には**埋められない。
   ここはその差を測る。

   ## CAPTCHA は検出するだけで、回避しない

   `captcha-kind` は種別を返して終わる。回避の手掛かりになる情報（フレームの
   token・sitekey・エンドポイント）は**一切保持しない**。これはこのワークスペースの
   安全床（CAPTCHA / bot 検出の回避をしない）であって、判定の都合ではない。

   ## 『取りに行けなかった』と『取れたがフォームが無かった』を同じ値にしない

   `:fetch-failed` と `:js-only` は別の答えである。混ぜると、**測れなかった分が
   「JS フォーム」として数えられる** —— 分母が減らないまま『静的には埋められない』
   という結論だけが太る。同じ理由で `:robots-disallowed` も独立させる。

   ## class は 1 つ、signal は全部

   `:form/class` は下記の優先順位で 1 つに畳むが、`:form/signals` には観測した
   ものを全部残す。優先順位はこちらの都合（何を先に諦めるか）であって観測ではない
   ので、**畳んだ結果しか残さないと、別の優先順位で数え直せなくなる。**

     robots-disallowed > fetch-failed > captcha > external > js-only
     > field-unfillable > submittable

   CAPTCHA を external より先に置くのは、**過小報告する方向が危ないから**である
   （外部サービスに飛ばした先に CAPTCHA が在っても、こちらは `:external` としか
   記録しない —— だから少なくとも見えた CAPTCHA は CAPTCHA として数える）。

   ## 必須判定は下界である

   HTML から読める必須は `required` / `aria-required` / class / ラベル近傍の
   『必須』相当語まで。**JS でだけ検証しているフォームは optional に見える。**
   だから `:submittable` は『少なくとも HTML 上は正直に埋まる』であって、
   『送れば通る』ではない。この差は測っていない —— 測るには送る必要があり、
   それはこの層の仕事ではない。"
  (:require [kotoba.lang.text :as str]
            [kotoba.property.contact-point :as cp]))

(def dataset "lead-contact-form")

(def classes
  "`:form/class` の値域。**閉じている** —— 新しい終わり方はここに足す。"
  #{:submittable :captcha :js-only :external :field-unfillable
    :fetch-failed :robots-disallowed})

(def ^:private class-order
  "畳む順。左が強い。"
  [:robots-disallowed :fetch-failed :captcha :external :js-only
   :field-unfillable :submittable])

(def max-parse-bytes
  "解析に回す HTML の上限。これを超えた分は切る（切ったことは記録に残す）。
   フォームは普通ページ前半に在るが、**切ったことを黙らない**。"
  1500000)

;; ---------------------------------------------------------------------------
;; タグと属性

(def ^:private attr-re
  #"(?is)([a-zA-Z_:][-a-zA-Z0-9_:.]*)(?:\s*=\s*(?:\"([^\"]*)\"|'([^']*)'|([^\s\"'>]+)))?")

(defn attrs
  "**タグ名を含まない属性テキスト**（`<input` と `>` の間）-> 属性 map。
   キーは小文字文字列。値の無い属性（`required` `disabled`）は空文字を値に持つ
   —— **`contains?` で『在る』を問えるようにするため**。nil にすると『無い』と
   区別できない。

   ⚠ **タグ名を渡さない。** 一度ここで先頭のタグ名を落とす実装にしていたが、
   呼び手は全員 `<(input|form|...)\b([^>]*)>` の 2 群目（= 既にタグ名の無い文字列）を
   渡していたので、**最初の属性が毎回タグ名として捨てられていた** ——
   `<input type=\"password\">` の `type` が消えて全項目が `text` に見え、
   ログインフォームが問い合わせフォームとして数えられていた（実測 2026-08-26。
   テストが両方向を見ていたので landing 前に出た）。"
  [tag-inner]
  (reduce (fn [m [_ k v1 v2 v3]]
            (assoc m (str/lower k) (or v1 v2 v3 "")))
          {}
          (re-seq attr-re (str tag-inner))))

(defn- located
  "`re-seq` の結果に、元文字列上の開始位置を付ける。位置が要るのは
   **入力欄の周りのテキストを見ないと『必須』が読めない**ため（日本語のフォームは
   `required` 属性ではなく `<span>必須</span>` で表すことが多い）。"
  [s re]
  (loop [ms (re-seq re s) pos 0 acc []]
    (if-let [m (first ms)]
      (let [whole (if (coll? m) (first m) m)
            i (or (str/index-of s whole pos) pos)]
        (recur (rest ms) (+ i (count whole))
               (conj acc {:m m :start i :end (+ i (count whole))})))
      acc)))

(def ^:private form-re #"(?is)<form\b([^>]*)>(.*?)</form>")
(def ^:private field-re #"(?is)<(input|textarea|select)\b([^>]*)>")
(def ^:private label-for-re
  #"(?is)<label[^>]*\bfor\s*=\s*[\"']([^\"']+)[\"'][^>]*>(.*?)</label>")

(defn label-map
  "`for=` を持つ `<label>` -> `{id テキスト}`。**id が無いフォームには効かない**ので、
   これだけに頼らず近傍テキストも見る（`field-context` 参照）。"
  [html]
  (reduce (fn [m [_ id inner]]
            (assoc m (str/trim id) (cp/strip-tags inner)))
          {}
          (re-seq label-for-re (str html))))

(defn form-regions
  "HTML -> `[{:attrs .. :body .. }]`。

   `</form>` を書かないページが実在するので、`<form` は在るのに 1 件も取れなかった
   ときは **最初の `<form` から末尾まで**を 1 領域として拾う。落とすと『フォームが
   無い』（= `:js-only`）に化けて、静的に埋められるフォームが JS 扱いになる。"
  [html]
  (let [h (str html)
        regions (mapv (fn [{[_ a b] :m}] {:attrs (attrs a) :body b})
                      (located h form-re))]
    (if (seq regions)
      regions
      (when-let [i (str/index-of h "<form")]
        [{:attrs (attrs (or (second (re-find #"(?is)<form\b([^>]*)>" (subs h i))) ""))
          :body (subs h i)
          :unclosed? true}]))))

;; ---------------------------------------------------------------------------
;; 項目の意味

(def unfillable-re
  "**こちらが真実の値を持っていない**必須項目。捏造すれば埋まるが、それは
   このタスクの目的（正直に連絡する）を壊す。既存顧客向けの窓口を、新規の
   問い合わせ窓口と同じ数に混ぜないための列でもある。"
  #"(?i)(お客様番号|お客さま番号|顧客番号|会員番号|会員id|カスタマーid|契約番号|契約者番号|加入者番号|受付番号|問合せ番号|注文番号|受注番号|伝票番号|請求書番号|請求番号|製造番号|製品番号|シリアル|保険証番号|証券番号|証書番号|学籍番号|社員番号|口座番号|支店番号|ご登録のメールアドレス|登録済みのメール|既にご利用|既存のお客様|serial[\s_-]*(no|number)|customer[\s_-]*(no|number|code|id)|account[\s_-]*(no|number|id)|contract[\s_-]*(no|number|id)|order[\s_-]*(no|number|id)|invoice[\s_-]*(no|number)|policy[\s_-]*(no|number)|membership[\s_-]*(no|number|id)|reference[\s_-]*(no|number)|kundennummer|vertragsnummer|num[eé]ro\s+de\s+(client|contrat)|n[uú]mero\s+de\s+(cliente|contrato))")

(def ^:private kind-rules
  "上から順に当てる。**順序が意味**（会社名を人名より先に見ないと『会社名』が
   `名` で人名に落ちる）。"
  [[:email       #"(?i)(e-?mail|メール|メアド|courriel|correo|posta\s+elettronica|e-?post|(^|[^a-z0-9])mail([^a-z0-9]|$))"]
   [:phone       #"(?i)(電話|でんわ|携帯|tel(ephone)?\b|phone|telefon|t[ée]l[ée]phone|tel[ée]fono|telefono|mobile|handy)"]
   [:kana        #"(?i)(フリガナ|ふりがな|カナ|kana|furigana)"]
   [:company     #"(?i)(会社名|会社|法人名|法人|企業名|企業|貴社|御社|団体名|組織名|屋号|事業所|company|corporate|organi[sz]ation|firma|unternehmen|soci[ée]t[ée]|entreprise|empresa|azienda|bedrijf)"]
   [:person-name #"(?i)(お名前|氏名|名前|担当者|ご担当|姓|名\b|your[\s_-]*name|full[\s_-]*name|first[\s_-]*name|last[\s_-]*name|surname|\bname\b|nom\b|nombre|nome|vorname|nachname)"]
   [:department  #"(?i)(部署|部門|所属|department|abteilung|service|departamento)"]
   [:position    #"(?i)(役職|職位|肩書|job[\s_-]*title|position|funktion|cargo)"]
   [:website     #"(?i)(url|ホームページ|ウェブサイト|website|homepage|web\b|sitio\s+web)"]
   [:address     #"(?i)(住所|所在地|郵便番号|〒|都道府県|市区町村|番地|建物|address|zip|postal|postcode|plz|stra[sß]e|city|stadt|ville|ciudad|country|land\b|pays|pa[ií]s|prefecture)"]
   [:subject     #"(?i)(件名|題名|表題|種別|区分|カテゴリ|お問い合わせ項目|ご用件|用件|subject|betreff|objet|asunto|oggetto|onderwerp|topic|category|reason|inquiry[\s_-]*type)"]
   [:message     #"(?i)(内容|本文|詳細|ご相談|ご要望|コメント|message|nachricht|mensaje|messaggio|bericht|comment|enquiry|inquiry|body|remarks|beschreibung|description)"]
   [:consent     #"(?i)(同意|承諾|プライバシー|個人情報|privacy|consent|agree|terms|dsgvo|gdpr|datenschutz|politique\s+de\s+confidentialit)"]])

(defn field-kind
  "1 項目 -> 意味。`type` と、名前 / ラベル / placeholder / id から決める。

   **`id` は最後に見る。** `id` は DOM の識別子で、使い回しと書き換え忘れが起きる
   —— 実測 2026-08-26、ある窓口の『会社名・団体名』欄が `id=\"kana\"` を持って
   いた（隣のフリガナ欄からのコピー）ため、`name` を無視して `:kana` に分類されて
   いた。`name` は送信されるキー、ラベルは人が読む語で、どちらも `id` より
   その欄の意味に近い。

   **`:unfillable` は形より先に見る。** 『ご登録のメールアドレス』はメール欄の形を
   しているが、こちらには真実の値が無い。形で先に分類すると、その差が消える。"
  [{:keys [type name id label placeholder]}]
  (let [t (str/lower (str type))
        primary (str/lower (str/join " " (remove str/blank? [name label placeholder])))
        fallback (str/lower (str id))
        by-rules (fn [hay] (some (fn [[k re]] (when (re-find re hay) k)) kind-rules))]
    (cond
      (= t "file") :file-upload
      (= t "password") :password
      (re-find unfillable-re primary) :unfillable
      (and (str/blank? primary) (re-find unfillable-re fallback)) :unfillable
      (= t "textarea") :message
      (= t "email") :email
      (= t "tel") :phone
      (= t "url") :website
      :else
      (or (by-rules primary)
          (by-rules fallback)
          (cond
            (contains? #{"checkbox" "radio" "select"} t) :choice
            :else :other)))))

(def unfillable-kinds
  "**正直には埋められない**項目の種別。`:file-upload` を入れるのは、添付を必須に
   する窓口には送るべき添付が無いから（空のファイルを作って出すのは捏造である）。"
  #{:unfillable :password :file-upload})

(defn honestly-fillable?
  "その項目に、こちらが真実の値を書けるか。"
  [field]
  (not (contains? unfillable-kinds (:field/kind field))))

;; ---------------------------------------------------------------------------
;; 必須

(def required-word-re
  #"(?i)(必須|必ず入力|required|requis|obligatoire|pflichtfeld|erforderlich|obbligatorio|obligatorio|verplicht|p[åa]kr[æa]vet)")

(defn- trim-partial-head
  "窓の先頭が**タグの途中**から始まっているなら、最初の `>` までを捨てる。

   ⚠ これが無いと、直前の入力欄の属性テキストが本文に化ける。実測 2026-08-26:
   `... name=\"email\" required><label>電話番号</label>` を途中で切ると
   `il\" required` が**本文**として残り、`required` の語に当たって
   **任意の電話欄が必須として数えられていた**（テストが両方向を見ていたので出た）。
   窓の途中から始まったかは局所的に判る —— 外側から始まったなら、最初に出会う
   特別な文字は `<` のはずである。"
  [s]
  (let [i< (str/index-of s "<") i> (str/index-of s ">")]
    (if (and i> (or (nil? i<) (< i> i<))) (subs s (inc i>)) s)))

(defn- trim-partial-tail
  "窓の末尾がタグの途中で終わっているなら、最後の `<` から先を捨てる（同じ理由）。"
  [s]
  (let [l< (str/last-index-of s "<") l> (str/last-index-of s ">")]
    (if (and l< (or (nil? l>) (> l< l>))) (subs s 0 l<) s)))

(defn field-context
  "入力欄の前後のテキスト。前 140 / 後 90 字。

   ⚠ **窓 1 つで『必須』を判定すると、冒頭の『＊印は必須項目です』が最初の欄を
   必須にする。** だから `＊` 単体は必須の根拠にしない（`required-word-re` に
   入れていない）—— 記号だけの印は、注記と印字の区別がつかない。"
  [body start end]
  (let [a (max 0 (- start 140))
        b (min (count body) (+ end 90))]
    (str (cp/strip-tags (trim-partial-head (subs body a start)))
         " "
         (cp/strip-tags (trim-partial-tail (subs body end b))))))

(defn field-required?
  "HTML から読める範囲での必須。**下界であって真値ではない**（JS でだけ検証する
   フォームは optional に見える）。"
  [a label context]
  (boolean
   (or (contains? a "required")
       (= "true" (str/lower (str (get a "aria-required"))))
       (re-find #"(?i)(require|必須|hissu|mandatory)" (str (get a "class")))
       (re-find #"(?i)(require|必須)" (str (get a "data-validate") (get a "data-rule") (get a "data-required")))
       (re-find required-word-re (str label))
       (re-find required-word-re (str context)))))

;; ---------------------------------------------------------------------------
;; フォーム 1 つ

(def ^:private ignorable-types #{"hidden" "submit" "button" "image" "reset"})

(defn form-fields
  "フォーム領域 -> 項目の列。hidden / submit / button は落とす（人が埋めるものではない）。"
  [{:keys [body]} labels]
  (->> (located (str body) field-re)
       (keep (fn [{[_ tag inner] :m :keys [start end]}]
               (let [a (attrs inner)
                     tag (str/lower tag)
                     t (if (= tag "input") (str/lower (str (get a "type" "text"))) tag)]
                 (when-not (contains? ignorable-types t)
                   (let [id (not-empty (str (get a "id")))
                         nm (not-empty (str (get a "name")))
                         label (or (get labels id)
                                   (not-empty (str (get a "aria-label")))
                                   (not-empty (str (get a "title"))))
                         ctx (field-context (str body) start end)
                         base {:type t :name nm :id id :label label
                               :placeholder (not-empty (str (get a "placeholder")))}]
                     {:field/name nm
                      :field/type t
                      :field/label (or label (not-empty (str (get a "placeholder"))))
                      :field/required? (field-required? a label ctx)
                      :field/kind (field-kind base)})))))
       ;; 同名の radio / checkbox 群は 1 項目として数える。**選択肢の数は項目数ではない。**
       (reduce (fn [acc f]
                 (if (and (:field/name f)
                          (contains? #{"radio" "checkbox"} (:field/type f))
                          (some #(and (= (:field/name %) (:field/name f))
                                      (= (:field/type %) (:field/type f))) acc))
                   (if (:field/required? f)
                     (mapv #(if (and (= (:field/name %) (:field/name f))
                                     (= (:field/type %) (:field/type f)))
                              (assoc % :field/required? true) %) acc)
                     acc)
                   (conj acc f)))
               [])
       vec))

(def ^:private search-re #"(?i)(^|[/_?&\-])(s|q|search|keyword|kw|query|検索)($|[/_?&\-=])")
(def ^:private newsletter-re #"(?i)(newsletter|mailmag|メルマガ|メールマガジン|subscribe|購読|signup|sign-up)")

(defn form-shape
  "フォームの性格。**1 ページに複数のフォームが在るのが普通**（検索・ログイン・
   メルマガ・本命）なので、どれが問い合わせ窓口かを決めないと、検索窓を
   『2 項目の submittable なフォーム』として数えてしまう。"
  [{:keys [attrs] :as region} fields]
  (let [action (str (get attrs "action"))
        names (str/lower (str/join " " (keep :field/name fields)))
        n (count fields)]
    {:action action
     :field-count n
     :textarea? (boolean (some #(= "textarea" (:field/type %)) fields))
     :email? (boolean (some #(= :email (:field/kind %)) fields))
     :login? (boolean (some #(= :password (:field/kind %)) fields))
     :search? (boolean (and (<= n 2)
                            (or (re-find search-re action)
                                (re-find search-re names)
                                (some #(= "search" (:field/type %)) fields))))
     :newsletter? (boolean (and (<= n 2)
                                (some #(= :email (:field/kind %)) fields)
                                (or (re-find newsletter-re action)
                                    (re-find newsletter-re names))))
     :unclosed? (boolean (:unclosed? region))}))

(defn form-score
  "問い合わせ窓口らしさ。大きいほど良い。**0 以下なら窓口ではない**として扱う。"
  [shape]
  (+ (if (:textarea? shape) 120 0)
     (if (:email? shape) 40 0)
     (if (re-find #"(?i)(contact|inquir|otoiawase|toiawase|mail|form|entry|confirm|send)" (str (:action shape))) 25 0)
     (* 3 (:field-count shape))
     (if (:search? shape) -300 0)
     (if (:login? shape) -200 0)
     (if (:newsletter? shape) -150 0)))

(defn inquiry-shaped?
  "そのフォームで**問い合わせが成立しうるか**。用件を書く場所（`:message`）か、
   返事の宛先（`:email`）が少なくとも 1 つ要る。

   点数だけで決めると足りない。実測 2026-08-26、点数は正でも次のものが
   『送れるフォーム』として数えられていた —— FAQ のカテゴリ選択（`:choice` 1 本）、
   地域切り替え（`:address` だけ）、Cookie 同意、入力欄 1 本の断片。**19 件**、
   JP 111 のうち 7・EU 42 のうち 12 が該当した。どれも用件を書く場所も宛先も
   持たないので、埋めても相手に何も届かない。"
  [{:keys [fields]}]
  (boolean (some #(contains? #{:message :email} (:field/kind %)) fields)))

(defn pick-inquiry-form
  "領域の列 -> 問い合わせ窓口らしい 1 つ（`{:region :fields :shape :score}`）。
   窓口の形をしていなければ nil —— **『フォームが在る』と『問い合わせフォームが
   在る』は別の主張**である。"
  [regions labels]
  (->> regions
       (map (fn [r]
              (let [fields (form-fields r labels)
                    shape (form-shape r fields)]
                {:region r :fields fields :shape shape :score (form-score shape)})))
       (filter inquiry-shaped?)
       (sort-by (fn [x] (- (:score x))))   ;; ⚠ max-key は数値専用。sort-by で並べる
       first
       (#(when (and % (pos? (:score %))) %))))

;; ---------------------------------------------------------------------------
;; CAPTCHA — 検出するだけ。回避しない。

(def captcha-rules
  "**種別だけを返す。** sitekey / token / チャレンジのエンドポイントは読まないし
   記録もしない —— それは回避の材料であって、計測の材料ではない。

   ⚠ **語が在ることを根拠にしない。実際のマークアップを求める。** 実測 2026-08-26、
   `\\bcaptcha\\b` を素で当てていたとき、Wix のページが持つ JS モジュール一覧
   （`\"assetsLoader\",\"businessLogger\",\"captcha\",\"clickHandlerRegistrar\"...`）と
   ベンダの宣伝文（\"security guards ... such as smart CAPTCHA\"）に当たって、
   **CAPTCHA の無いフォームが 2 件『CAPTCHA 有り』として数えられていた**。
   CAPTCHA は送れない側に数えられるので、この向きの誤りは**送れる数を過小に見せる**。"
  [[:recaptcha        #"(?i)(g-recaptcha|grecaptcha|recaptcha/api|/recaptcha/|recaptcha\.net|recaptcha[_-](response|token))"]
   [:hcaptcha         #"(?i)(h-captcha|hcaptcha\.com|js\.hcaptcha)"]
   [:turnstile        #"(?i)(cf-turnstile|challenges\.cloudflare\.com)"]
   [:friendly-captcha #"(?i)(friendlycaptcha|friendly-challenge)"]
   [:geetest          #"(?i)(geetest\.com|gt_captcha|initGeetest)"]
   [:aws-waf          #"(?i)aws-waf(-|_)?captcha"]
   [:altcha           #"(?i)(altcha-widget|altcha\.js|<altcha)"]
   ;; 自前の画像 CAPTCHA。**入力欄か画像そのもの**を求める（語ではなく物）。
   [:image-captcha    #"(?i)(画像認証|認証コード|キャプチャ|<input[^>]{0,200}(name|id|class)\s*=\s*[\"'][^\"']{0,40}captcha|<img[^>]{0,200}captcha)"]])

(defn captcha-kind
  "見つかった最初の種別。無ければ nil。順序は具体的なものから。"
  [html]
  (let [h (str html)]
    (some (fn [[k re]] (when (re-find re h) k)) captcha-rules)))

;; ---------------------------------------------------------------------------
;; 外部フォームサービス

(def form-service-rules
  [[:google-forms   #"(?i)docs\.google\.com/forms"]
   [:microsoft-forms #"(?i)forms\.office\.com"]
   [:hubspot        #"(?i)(js\.hsforms\.net|hsforms\.(net|com)|hbspt\.forms|forms\.hubspot)"]
   [:formrun        #"(?i)form\.run"]
   [:typeform       #"(?i)typeform\.com"]
   [:jotform        #"(?i)jotform\.(com|co)"]
   [:wufoo          #"(?i)wufoo\.com"]
   [:formstack      #"(?i)formstack\.com"]
   [:cognito-forms  #"(?i)cognitoforms\.com"]
   [:paperform      #"(?i)paperform\.co"]
   [:zoho-forms     #"(?i)(forms\.zohopublic|zoho\.(com|eu)/forms)"]
   [:salesforce     #"(?i)(webto\.salesforce\.com|web2lead|salesforce\.com/servlet/servlet\.WebToLead)"]
   [:marketo        #"(?i)(marketo\.net|mktoforms|munchkin\.js)"]
   [:pardot         #"(?i)(pardot\.com|go\.pardot|pi\.pardot)"]
   [:surveymonkey   #"(?i)surveymonkey\.(com|co)"]
   [:tayori         #"(?i)tayori\.com"]
   [:formzu         #"(?i)formzu\.(net|com)"]
   [:formmailer     #"(?i)formmailer\.jp"]
   [:satori         #"(?i)satori\.marketing"]
   [:cuenote        #"(?i)cuenote\.jp"]
   [:bme-jp         #"(?i)bme\.jp"]
   [:shanon         #"(?i)(shanon\.co\.jp|smartseminar)"]
   [:activecampaign #"(?i)activehosted\.com"]
   [:mailchimp      #"(?i)(list-manage\.com|mailchimp\.com)"]
   [:brevo          #"(?i)(sendinblue\.com|brevo\.com)"]
   [:pipedrive      #"(?i)pipedrivewebforms\.com"]
   [:freshworks     #"(?i)freshworks\.com/crm/web-forms"]
   [:zendesk        #"(?i)zendesk\.com/embeddable"]
   [:kintone        #"(?i)(kintone\.com|kintoneapp\.com|form\.kintoneapp)"]])

(defn- service-of [s]
  (some (fn [[k re]] (when (re-find re (str s)) k)) form-service-rules))

(def ^:private iframe-re #"(?is)<iframe\b[^>]*\bsrc\s*=\s*[\"']([^\"']+)[\"']")
(def ^:private script-src-re #"(?is)<script\b[^>]*\bsrc\s*=\s*[\"']([^\"']+)[\"']")

(defn external-form
  "問い合わせの経路そのものが外部サービスか。`{:service .. :via ..}` か nil。

   **スクリプトが在るだけでは external にしない。** メルマガ用の Mailchimp が
   置いてあるページに自前の問い合わせフォームが在ることは普通にあり、それを
   external と数えると『自分のサイトで受けている窓口』が消える。script を
   根拠にするのは、**自前のフォームが 1 つも無いとき**だけ。"
  [html final-url native-form]
  (let [h (str html)
        iframes (map second (re-seq iframe-re h))
        scripts (map second (re-seq script-src-re h))
        action (str (get-in native-form [:shape :action]))]
    (cond
      (service-of final-url) {:service (service-of final-url) :via :url}
      (some service-of iframes) {:service (some service-of iframes) :via :iframe}
      (and (seq action) (service-of action)) {:service (service-of action) :via :action}
      (and (nil? native-form) (some service-of scripts))
      {:service (some service-of scripts) :via :embedded-script}
      :else nil)))

;; ---------------------------------------------------------------------------
;; フォームが無かった理由

(def ^:private js-app-re
  #"(?i)(__NEXT_DATA__|__NUXT__|data-reactroot|ng-version|id=[\"']app[\"']|id=[\"']root[\"']|window\.__INITIAL|createApp\(|vue(\.min)?\.js|react-dom|gatsby|svelte)")

(defn loose-field-count
  "`<form>` の外に在る、人が埋める入力欄の数。

   **『欄が 1 つも無い』と『欄は在るが form 要素が無い』は別の観測**である。
   後者は submit 先（action / method）が HTML に書かれていないので JS が送っている
   —— 静的には埋められないが、*連絡窓口としては在る*。実測 2026-08-26、
   ある窓口は `<input>` 5 本 + `<textarea>` 1 本を持ちながら `<form>` が 0 本だった。"
  [html]
  (->> (re-seq field-re (str html))
       (remove (fn [[_ tag inner]]
                 (let [tag (str/lower tag)
                       t (if (= tag "input")
                           (str/lower (str (get (attrs inner) "type" "text")))
                           tag)]
                   (contains? ignorable-types t))))
       count))

(defn no-form-reason
  "form を採れなかったときの理由。**全部を『JS が描いている』に畳まない** ——
   `mailto:` しか無いページは『送れない』ではなく『メールでなら送れる』であり、
   検索窓しか無いページは『窓口が別の場所に在る』である。"
  [html regions picked]
  (let [h (str html)]
    (cond
      (and (seq regions) (nil? picked)) :only-search-or-login-form
      (>= (loose-field-count h) 2) :fields-without-form
      (re-find #"(?i)mailto:" h) :mailto-only
      (re-find js-app-re h) :js-rendered
      :else :no-form-in-html)))

;; ---------------------------------------------------------------------------
;; 1 URL を分類する

(defn- ok-status? [s] (and (number? s) (<= 200 s 299)))

(defn classify
  "1 URL の観測 -> 1 レコード。

   `observation` は収集器が実際に取れたもの:
     `{:url .. :final-url .. :http-status .. :body .. :robots-disallowed? ..
       :observed-at .. :solicitation-re ..}`

   **body が無くても、status が悪くてもレコードは作る。** 落とすと次の run が
   同じ URL を見に行って同じ理由でまた落とす。"
  [{:keys [url final-url http-status body robots-disallowed? observed-at
           solicitation-re] :as observation}]
  (let [raw (str body)
        truncated? (> (count raw) max-parse-bytes)
        h (if truncated? (subs raw 0 max-parse-bytes) raw)
        fetched? (and (ok-status? http-status) (not (str/blank? h)))
        labels (when fetched? (label-map h))
        regions (when fetched? (form-regions h))
        picked (when fetched? (pick-inquiry-form regions labels))
        cap (when fetched? (captcha-kind h))
        ext (when fetched? (external-form h (or final-url url) picked))
        fields (:fields picked)
        required (filterv :field/required? fields)
        unfillable (filterv (complement honestly-fillable?) required)
        forbidden? (when fetched?
                     (cp/solicitation-forbidden? h (or solicitation-re nil)))
        signals (cond-> []
                  cap (conj :captcha)
                  ext (conj :external)
                  picked (conj :native-form)
                  (seq unfillable) (conj :unfillable-required)
                  (some #(and (= :phone (:field/kind %)) (:field/required? %)) fields)
                  (conj :phone-required)
                  forbidden? (conj :solicitation-forbidden)
                  (and fetched? (re-find #"(?i)mailto:" h)) (conj :mailto)
                  truncated? (conj :body-truncated))
        klass (cond
                robots-disallowed? :robots-disallowed
                (not fetched?) :fetch-failed
                cap :captcha
                ext :external
                (nil? picked) :js-only
                (seq unfillable) :field-unfillable
                :else :submittable)]
    (cond-> {:source/dataset dataset
             :form/url url
             :form/class klass
             :form/signals signals
             :http/status http-status}
      final-url (assoc :form/final-url final-url)
      observed-at (assoc :source/observed-at observed-at)
      cap (assoc :form/captcha-kind cap)
      ext (assoc :form/external-service (:service ext)
                 :form/external-via (:via ext))
      forbidden? (assoc :form/solicitation-forbidden? true)
      (and fetched? (nil? picked))
      (assoc :form/no-form-reason (no-form-reason h regions picked))
      picked (assoc :form/action (not-empty (get-in picked [:shape :action]))
                    :form/field-count (count fields)
                    :form/required-count (count required)
                    :form/fields fields)
      (seq unfillable) (assoc :form/unfillable-required
                              (mapv (fn [f] (select-keys f [:field/name :field/label :field/kind]))
                                    unfillable)))))

;; ---------------------------------------------------------------------------
;; 集計

(defn sendable?
  "**送ってよい**行か。`:submittable` であることと、相手が営業を断っていないこと。
   片方だけ見ると、断っている窓口に送るか、送れない窓口を数に入れるかになる。"
  [record]
  (and (= :submittable (:form/class record))
       (not (:form/solicitation-forbidden? record))))

(defn field-histogram
  "レコード列 -> `{kind {:forms n :required n}}`。分母は**フォームの数**であって
   項目の数ではない（1 フォームに『姓』『名』が在っても人名を要求する
   フォームは 1 つ）。"
  [records]
  (reduce
   (fn [acc r]
     (let [fs (:form/fields r)
           kinds (into {} (map (fn [[k v]] [k (boolean (some :field/required? v))])
                               (group-by :field/kind fs)))]
       (reduce (fn [a [k req?]]
                 (-> a
                     (update-in [k :forms] (fnil inc 0))
                     (update-in [k :required] (fnil + 0) (if req? 1 0))))
               acc kinds)))
   {}
   records))

(defn coverage
  "レコード列 -> 何を測れて何を測れなかったかの 1 entity。

   **`:coverage/scanned` は分母であって成果ではない。** `:coverage/sendable` が
   『実際に送れる数』で、それ以外は全部その手前の段である。"
  [records]
  (let [subm (filterv #(= :submittable (:form/class %)) records)]
    {:source/dataset dataset
     :coverage/scanned (count records)
     :coverage/by-class (frequencies (map :form/class records))
     :coverage/fetch-failed-by-status (frequencies (map :http/status
                                                        (filter #(= :fetch-failed (:form/class %)) records)))
     :coverage/js-only-by-reason (frequencies (map :form/no-form-reason
                                                   (filter #(= :js-only (:form/class %)) records)))
     :coverage/captcha-by-kind (frequencies (map :form/captcha-kind
                                                 (filter #(= :captcha (:form/class %)) records)))
     :coverage/external-by-service (frequencies (map :form/external-service
                                                     (filter #(= :external (:form/class %)) records)))
     :coverage/unfillable-by-kind (frequencies (mapcat #(map :field/kind (:form/unfillable-required %))
                                                       records))
     :coverage/solicitation-forbidden (count (filter :form/solicitation-forbidden? records))
     :coverage/sendable (count (filter sendable? records))
     :coverage/submittable-field-kinds (field-histogram subm)
     :coverage/submittable-phone-required
     (count (filter (fn [r] (some #(and (= :phone (:field/kind %)) (:field/required? %))
                                  (:form/fields r)))
                    subm))
     :coverage/submittable-median-required
     (let [xs (sort (map :form/required-count subm))]
       (when (seq xs) (nth xs (quot (count xs) 2))))}))
