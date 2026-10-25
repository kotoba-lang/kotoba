(ns kotoba.property.eu-contact
  "EU の法人 -> **公開連絡点**。I/O は 1 バイトも無い。

   `kotoba.property.contact-point`（日本）の EU 版。**判定の骨格は再利用し**、
   変えるのは 3 つだけ: 語彙（多言語）・メールの分類（GDPR で日本より厳しく）・
   チャネルの値域（EU ポータルのフォームという第 4 の面がある）。

   ## 1. GDPR — 個人のアドレスを日本より厳しく落とす

   日本側の規則は『迷ったら `:personal` に倒す』。EU ではこれを**もう一段厳しく**する:

     JP  local part が role 語彙に在る、**または** `sales.` `info-` 等の前置きで
         始まれば `:role`
     EU  local part 全体が role 語彙に在るときだけ `:role`。
         唯一の例外は role 語 + 国/言語コード（`info-de` `contact.uk`）

   `sales.john@` は日本の規則では `:role` に落ちるが、EU では `:personal` になる。
   **GDPR の下では、識別された自然人の業務用アドレスも個人データである** ——
   誤って 1 件の窓口を落とす方が、誤って 1 人の個人データを営業台帳に載せるより安い。

   ## 2. TED を取り込まない（決定）

   TED（Tenders Electronic Daily）は EU で**唯一、落札者のメールが構造化
   フィールドで返る**面である。それでも母集団に入れない。理由は 1 つ:

   ADR-2608251500 の実測サンプルで、スウェーデンの落札 3 社の
   `organisation-email-tenderer` は **3 件とも個人名のアドレス**だった
   （`ragnar.johansson@svevia.se` 等）。上の分類器を当てれば 3 件とも
   `:personal` として落ちるので、**TED が唯一持っていた利点は出力に残らない。**
   残るのは『個人データを含む一括取得を毎日回している』という事実だけで、
   GDPR 第 14 条（本人以外から取得した個人データの通知義務）を果たす体制は無い。

   **利点が出力に残らない取得を行わない。** これは能力の問題ではなく設計判断であり、
   TED の面が要るなら Art. 14 の通知経路を先に作る。

   ## 3. EU ポータルのフォームは連絡点として記録するが、営業に使わない

   CORDIS の `contactForm` は **100% 埋まっている**（実測 2026-08-25、母集団
   8,831 法人の全件）。桁違いに被覆が良いが、これは欧州委員会の
   Funding & Tenders ポータルが**そのプロジェクトについて参加者に連絡する**ために
   置いているフォームであって、その企業が自ら公開した営業窓口ではない。

   - 日本側の契約は『こちらが探しに行って、実際に取得できた**その会社の**連絡点』を
     載せる。ポータルのフォームはその会社の面ではない。
   - EU の機関が別目的で提供している経路に商用の勧誘を流すことになる。

   だから `:eu-portal-form` という**別のチャネル値**として台帳に残し、
   **営業用 TSV からは既定で外す**（件数は必ず印字する）。事実は消さない、
   使わないだけである。

   ## 4. 〒 の抽出はしない

   日本側の `extract-site-postal-code` は `〒` を見る。EU の郵便番号は国ごとに
   形が違い（`46100` `KY16 9AJ` `02-662` `1040`）、**サイト本文から誤りなく
   拾う規則が書けない。** CORDIS が 98.5% で持っているので、**推測しない。**

   出典：CORDIS（欧州委員会）https://cordis.europa.eu/（CC BY 4.0）+
   各社の自己公表ページ（`:source/observed-at` に取得時刻）"
  (:require [kotoba.lang.text :as str]
            [kotoba.property.contact-point :as cp]
            [kotoba.property.eu-cordis :as eu]))

(def dataset "eu-lead-contact-point")
(def authority-id "EU/EC-CORDIS+self-published")
(def attribution
  "出典：CORDIS（欧州委員会）https://cordis.europa.eu/ Horizon Europe projects（CC BY 4.0）を加工して作成。連絡点は各社の自己公表ページ。")

(def statuses
  "`:lead/status` の値域。**閉じている。** 日本と同じ 6 値に
   `:no-participation`（母集団に入る参加が 1 件も無い）は足していない ——
   母集団の作り方でそれは起きない。"
  #{:ok :no-website :fetch-failed :no-contact-point :robots-disallowed :unresolved})

(def channels
  "`channel` の値域。日本の 3 値に `eu-portal-form` を足した 4 値。"
  #{"web" "post" "eu-portal-form" "none"})

;; ---------------------------------------------------------------------------
;; 多言語の語彙
;;
;; EN / DE / FR / ES / IT / NL / PT / SV / PL / DA / FI。母集団の上位 15 か国
;; （実測 2026-08-25: DE ES FR IT UK NL EL BE SE AT CH PT DK FI IE）を覆う。
;; ⚠ EL（ギリシャ）の語彙は入っていない —— **入っていないことを書いておく**。
;; ギリシャ語のサイトは英語の `contact` に当たったときだけ拾える。

(def contact-href-re
  #"(?i)(contact|kontakt|contatt|contacto|contato|impressum|imprint|legal-notice|mentions-legales|aviso-legal|inquir|enquir|anfrage|demande|about-?us/contact|support/?$|/form)")

(def contact-text-re
  #"(?i)(contact|kontakt|contatt|contacto|contato|contactez|impressum|imprint|mentions? l[ée]gales|aviso legal|kontakta oss|neem contact|get in touch|write to us|schreiben sie uns|anfrage|enquiry|inquiries)")

(def strong-path-re
  #"(?i)/(contact|contacts|kontakt|contatti|contacto|contato|contactez|impressum|imprint|mentions-legales|aviso-legal|inquiry|enquiry|anfrage|form)")

(def decoy-path-re
  ;; `contact-page?` は通るが営業窓口ではない面。日本語版と同じ役割。
  #"(?i)/(company|corporate|about|ueber-uns|über-uns|chi-siamo|quienes-somos|a-propos|profile|access|career|careers|jobs|karriere|recruit|privacy|datenschutz|politique|policy|cookie|news|blog|press|investors?|ir)(/|$)")

(def common-contact-paths
  "autodiscovery が空振りしたときの当て先。**当てただけでは載せない。**
   `/impressum` を上位に置くのは、**独語圏では法律上その面に連絡先を載せる義務が
   ある**ため（DE は母集団最大の国）。"
  ["/contact" "/contact/" "/contact-us" "/en/contact" "/kontakt" "/kontakt/"
   "/impressum" "/contatti" "/contacto" "/contato" "/contactez-nous"
   "/mentions-legales" "/aviso-legal" "/about/contact" "/company/contact"])

(def solicitation-forbidden-re
  "相手のページが営業目的の連絡を断っている文言。**多言語。**
   日本語版の `cp/solicitation-forbidden-re` は EU では 1 語も当たらない。

   ⚠ 語彙の網羅は主張しない。**当たらなかったことを『断っていない』の証明に
   しない** —— 断り書きが読めない言語で書かれていれば false になる。"
  #"(?i)(no\s+(unsolicited|cold)\s+(sales|marketing|calls|emails|approaches)|not\s+accept\s+(unsolicited\s+)?(sales|marketing|commercial)|no\s+solicitation|unsolicited\s+(sales|commercial|marketing)\s+(enquiries|inquiries|emails|calls)\s+(are\s+)?(not|will\s+not)|please\s+(do\s+not|no)\s+(sales|marketing|cold)|keine\s+(werbung|akquise|kaltakquise|vertriebsanfragen)|werbeanrufe\s+unerw[üu]nscht|keine\s+unaufgeforderte[nr]?\s+(werbung|zusendung)|pas\s+de\s+(d[ée]marchage|prospection|sollicitation)|d[ée]marchage\s+(commercial\s+)?(interdit|refus)|no\s+se\s+admite[n]?\s+(publicidad|ofertas\s+comerciales)|no\s+aceptamos\s+(publicidad|ofertas)|non\s+si\s+accettano\s+(offerte|proposte)\s+commercial|niente\s+pubblicit|geen\s+(ongevraagde\s+)?(reclame|acquisitie|verkoop)|acquisitie\s+naar\s+aanleiding.{0,40}niet\s+op\s+prijs|ingen\s+telefonf[öo]rs[äa]ljning|undanbeder\s+oss)")

(def vocabulary
  "`contact-point` の各関数に渡す語彙一式。**1 か所に束ねる** —— 呼び手が
   1 つだけ渡し忘れて日本語の既定に落ちるのを防ぐ。"
  {:href-re contact-href-re
   :text-re contact-text-re
   :strong-re strong-path-re
   :decoy-re decoy-path-re})

;; ---------------------------------------------------------------------------
;; メールの分類（日本より厳しい）

(def region-suffixes
  "role 語に続いてよい語。国コード・言語コード・部門の一般名だけ。
   **人名がここに入らないことがこの表の唯一の仕事。**"
  #{"de" "at" "ch" "fr" "be" "nl" "es" "pt" "it" "se" "dk" "no" "fi" "pl" "cz"
    "uk" "gb" "ie" "eu" "en" "us" "jp" "global" "intl" "international"
    "group" "hq" "team" "office" "web" "site" "mail" "all" "general" "main"})

(defn classify-email
  "アドレス -> `:role` / `:personal`。**日本版より厳しい。**

   `:role` になるのは 2 つの形だけ:
     1. local part 全体が `cp/role-locals` に在る（`info` `contact` `sales`）
     2. role 語 + 区切り + 国/言語/部門コード（`info-de` `contact.eu` `sales_uk`）

   `sales.john` は 2 の形に見えるが `john` が `region-suffixes` に無いので
   `:personal` になる。**これが日本版との差そのもの。**"
  [email]
  (let [local (-> (str email) (str/split #"@") first str str/trim str/lower)
        parts (remove str/blank? (str/split local #"[._\-+]"))]
    (cond
      (contains? cp/role-locals local) :role
      (and (= 2 (count parts))
           (contains? cp/role-locals (first parts))
           (contains? region-suffixes (second parts))) :role
      :else :personal)))

(defn extract-emails
  "HTML -> 公開メール。抽出は `contact-point/extract-emails` を使い、
   **分類だけ EU の厳しい方に差し替える。**"
  [html]
  (mapv (fn [m] (assoc m :kind (classify-email (:email m))))
        (cp/extract-emails html)))

;; ---------------------------------------------------------------------------
;; レコード

(defn- put [m k v]
  (if (or (nil? v) (and (string? v) (str/blank? v)) (and (coll? v) (empty? v)))
    m
    (assoc m k v)))

(defn ->record
  "CORDIS の法人 + 観測 -> 1 社 1 レコード。

   `org` は `eu-cordis/organisation` の出力。`observation` は収集器が実際に
   取れたもの。**status が `:ok` 以外でもレコードは作る**（日本と同じ理由:
   消すと次の run が同じ法人をまた見に行って同じ理由でまた消える）。"
  [org observation]
  (let [status (:status observation)
        _ (assert (contains? statuses status) (str "unknown lead status: " status))
        emails (->> (:emails observation)
                    (filter #(= :role (:kind %)))
                    (map :email)
                    distinct vec)
        personal-n (count (filter #(= :personal (:kind %)) (:emails observation)))]
    (-> {:source/dataset dataset
         :source/authority authority-id
         :company/cordis-organisation-id (:organisation-id org)
         :company/jurisdiction (or (:country org) "EU")
         :lead/status status}
        (put :company/vat-number (:vat org))
        (put :company/legal-name (:name org))
        (put :company/short-name (:short-name org))
        (put :company/street (:street org))
        (put :company/postal-code (:post-code org))
        (put :company/city (:city org))
        (put :company/location (eu/postal-address org))
        (put :company/sme (:sme org))
        (put :company/ec-contribution-eur (:ec-contribution org))
        (put :web/url (cp/normalise-url (:url org)))
        (put :web/url-source (when (:url org) "cordis"))
        ;; **EU ポータルのフォーム。営業に使わない**（この ns の docstring 3 節）。
        ;; 事実として残すが、`:contact/form-url` とは別のキーにして
        ;; 混ざらないようにする —— 同じキーに入れたら区別は失われる。
        (put :contact/eu-portal-form (:contact-form org))
        (put :contact/form-url (:contact-url observation))
        (put :contact/emails emails)
        (put :contact/personal-emails-excluded (when (pos? personal-n) personal-n))
        (put :contact/solicitation-forbidden? (:solicitation-forbidden? observation))
        (put :source/observed-at (:observed-at observation))
        (put :lead/intent-signal (:intent-signal observation))
        (put :lead/note (:note observation)))))

(defn channel
  "この行にどう連絡するか。**`eu-portal-form` は営業チャネルではない** ——
   値域に在るのは『そこに面がある』という事実を消さないためで、
   `contactable?` は false を返す。"
  [record]
  (cond
    (or (:contact/form-url record) (seq (:contact/emails record))) "web"
    (and (not (str/blank? (str (:company/legal-name record))))
         (not (str/blank? (str (:company/street record))))
         (not (str/blank? (str (:company/city record))))) "post"
    (:contact/eu-portal-form record) "eu-portal-form"
    :else "none"))

(defn contactable?
  "outbound に出してよい行か。**チャネルと営業お断りを見る。status は見ない。**

   ⚠ 日本版は `(= :ok (:lead/status ...))` を条件にしている。EU で同じにすると
   **郵送の行が全部 false になる** —— 実測 2026-08-25、母集団上位 3,000 のうち
   2,456 が `:no-website`（登記に相当する URL が無い）で、そのほとんどは
   番地も郵便番号も市も揃っている。`:no-website` は『連絡できない』ではなく
   『web の面が無い』であって、**郵送のチャネルはそれと独立に成立する。**

   status は既にチャネルに畳まれている: `web` は観測して連絡点が取れた行にしか
   付かず、`post` は registry 側の住所だけで決まる。

   ⚠ **代償を書いておく。** `post` の行は相手のサイトを読んでいない（読めなかった、
   または無い）ので、**営業お断りの記載を観測していない。** 断り書きが在っても
   `false` として通る。日本側の郵送チャネルも同じ性質だが、EU は郵送が
   母集団の 9 割なので影響が大きい。web の行だけは実際に読んで確かめている。"
  [record]
  (and (not (:contact/solicitation-forbidden? record))
       (contains? #{"web" "post"} (channel record))))

(defn coverage
  "レコード列 -> 何を測れて何を測れなかったかの 1 entity。

   **`:scanned` は分母であって成果ではない。**"
  [records]
  {:source/dataset dataset
   :coverage/scanned (count records)
   :coverage/by-status (frequencies (map :lead/status records))
   :coverage/by-channel (frequencies (map channel records))
   :coverage/contactable (count (filter contactable? records))
   ;; **web と post を分けて数える。** 合計だけ見ると、相手のページを実際に読んで
   ;; 営業お断りを確かめた行と、住所しか見ていない行が同じ顔で並ぶ。
   :coverage/contactable-web (count (filter #(and (contactable? %) (= "web" (channel %))) records))
   :coverage/contactable-post (count (filter #(and (contactable? %) (= "post" (channel %))) records))
   ;; 郵送の行のうち、相手のページを一度も読めていない = 営業お断りが未観測の件数。
   :coverage/post-solicitation-unobserved
   (count (filter #(and (= "post" (channel %))
                        (contains? #{:no-website :fetch-failed :robots-disallowed} (:lead/status %)))
                  records))
   :coverage/solicitation-forbidden (count (filter :contact/solicitation-forbidden? records))
   :coverage/with-form-url (count (filter :contact/form-url records))
   :coverage/with-role-email (count (filter #(seq (:contact/emails %)) records))
   :coverage/with-vat (count (filter :company/vat-number records))
   :coverage/with-street (count (filter :company/street records))
   :coverage/with-own-website (count (filter :web/url records))
   ;; **営業には使わないが、被覆は測って残す** —— 使わない判断をした面が
   ;; どれだけ大きかったかを、次に読む人が見られるように。
   :coverage/with-eu-portal-form (count (filter :contact/eu-portal-form records))
   :coverage/personal-emails-excluded (reduce + 0 (keep :contact/personal-emails-excluded records))})
