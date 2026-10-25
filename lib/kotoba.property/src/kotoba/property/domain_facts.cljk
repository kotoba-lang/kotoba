(ns kotoba.property.domain-facts
  "会社のドメインについて、**レジストリが言っていること**と**こちらが引いた事実**を分けて持つ。

   ## なぜドメインが会社の面に載るか

   `.co.jp` は**登記された法人にしか割り当てられない**（1 法人 1 ドメイン）。JPRS の
   WHOIS はその `[組織名]` を返すので、**ドメインは法人番号への独立した経路**になる
   —— gBizINFO が「この会社はこの URL だと名乗った」と言うのに対し、レジストリは
   「このドメインはこの法人のものだ」と言う。両方あって初めて突き合わせができる。

   ## 3 つの出所を混ぜない

   | 接頭辞 | 何を言っているか | 出所 |
   |---|---|---|
   | `:registry/*` | レジストリの登録内容（組織名・登録年月日・状態） | JPRS WHOIS / RDAP |
   | `:dns/*` | **こちらが引いて返ってきた**レコード | 実測（node dns） |
   | `:company/*` | 法人番号側の identity | 既存の面 |

   `:registry/created-on` は「会社の設立日」ではない。**ドメインを取った日**である。

   ## 個人は持ち歩かない

   WHOIS の `Contact Information` ブロック（`[登録担当者]` `[Name]` `[Email]`
   `[Phone]` `[Postal Address]`）は**一切読まない**。パーサは名前を挙げた key しか
   拾わない allowlist で書いてある —— 「これは落とす」ではなく「これだけ拾う」に
   しておかないと、レジストリが項目を増やした日に個人が混ざる。

   RDAP 側も同じで、`entities` から取るのは role が `registrar` のものだけ
   （gTLD の registrant は基本 redact されているが、redact されていない日に
   拾わないことがここの目的）。"
  (:require [kotoba.lang.text :as str]))

(def dataset "domain-facts")

;; ---------- ホスト ----------

(defn url->host
  "`:web/url` からホストを取る。`www.` は落とす（同じドメインの別名なので）。"
  [url]
  (when-not (str/blank? (str url))
    (let [h (-> (str url)
                (str/replace #"^https?://" "")
                (str/replace #"[/?#].*$" "")
                (str/replace #":\d+$" "")
                str/lower
                str/trim)]
      (when (re-find #"^[a-z0-9.-]+\.[a-z]{2,}$" h)
        (str/replace h #"^www\." "")))))

(defn registrable-domain
  "WHOIS/RDAP に聞くべき単位まで縮める。`ir.example.co.jp` → `example.co.jp`。

   完全な公開接尾辞リストは持たない —— ここで要るのは `.jp` の 2 段構造
   （`co.jp` `or.jp` `ne.jp` …）と、それ以外の 1 段だけ。**知らない形は縮めない**
   （縮めすぎて別の会社に聞きに行くより、聞けない方がよい）。"
  [host]
  (when host
    (let [parts (str/split host #"\.")]
      (cond
        (< (count parts) 2) nil
        ;; 属性型 JP（co.jp / or.jp / ne.jp / ac.jp / go.jp / lg.jp …）
        (and (= "jp" (last parts))
             (>= (count parts) 3)
             (re-find #"^(co|or|ne|ac|ad|ed|go|gr|lg)$" (nth parts (- (count parts) 2))))
        (str/join "." (take-last 3 parts))
        :else (str/join "." (take-last 2 parts))))))

(defn jp-domain? [domain] (boolean (and domain (str/ends-with? domain ".jp"))))

(def attribute-type-jp-re
  ;; 属性型 JP ドメイン。**登録できるのは組織だけ**（co.jp は登記法人 1 法人 1 個、
  ;; or.jp は法人格のある非営利、ac.jp は学校…）。だから登録者名は組織名である。
  #"\.(co|or|ne|ac|ad|ed|go|gr|lg)\.jp$")

(def ^:private organization-markers
  ;; ⚠ **インラインの `(?i)` を書かない。** JVM は受けるが JS は
  ;; `Invalid group` で落ちる —— JVM のテストだけ緑になり、cljs で走らせた
  ;; 瞬間に壊れる（実測 2026-08-19、まさにそれを 1 回やった）。
  ;; 大小文字は入力側を小文字にして吸収する。
  #"株式会社|株式會社|有限会社|合同会社|合資会社|合名会社|相互会社|一般社団法人|公益社団法人|一般財団法人|公益財団法人|医療法人|学校法人|宗教法人|社会福祉法人|特定非営利活動法人|npo法人|行政書士法人|司法書士法人|税理士法人|弁護士法人|監査法人|協同組合|事業協同組合|信用金庫|信用組合|農業協同組合|組合|大学|高等学校|病院|市役所|町役場|村役場|\binc\b|\bcorp\b|\bcorporation\b|\bcompany\b|co\.,?\s*ltd|\bltd\b|\bllc\b|\bllp\b|\bgmbh\b|k\.k\.|kabushiki")

(defn organization-name?
  "その名前が**組織**を指していると言えるか。法人格の語が入っていれば言える。"
  [s]
  (boolean (and (not (str/blank? (str s)))
                (re-find organization-markers (str/lower (str s))))))

;; ---------- JPRS WHOIS ----------

(def ^:private jprs-fields
  "拾う key だけを名指しする allowlist。ここに無い行は読まない。"
  {"ドメイン名" :registry/domain
   "Domain Name" :registry/domain
   "組織名" :registry/registrant-name
   "登録者名" :registry/registrant-name
   "Registrant" :registry/registrant-name-en
   "Organization" :registry/registrant-name-en
   "組織種別" :registry/organization-type
   "Organization Type" :registry/organization-type-en
   "ネームサーバ" :registry/nameservers
   "Name Server" :registry/nameservers
   "署名鍵" :registry/signing-key
   "Signing Key" :registry/signing-key
   "登録年月日" :registry/created-on
   "Created on" :registry/created-on
   "接続年月日" :registry/connected-on
   "Connected Date" :registry/connected-on
   "Registered Date" :registry/created-on
   "有効期限" :registry/expires-on
   "Expires on" :registry/expires-on
   "状態" :registry/status
   "State" :registry/status
   "Status" :registry/status
   "最終更新" :registry/updated-at
   "Last Update" :registry/updated-at
   "Last Updated" :registry/updated-at})

(def ^:private multi-fields #{:registry/nameservers :registry/status})

(defn- normalize-date
  "`2000/03/29` `2026/04/01 01:00:49 (JST)` → `2000-03-29`。時刻は落とす。"
  [v]
  (when v
    (when-let [m (re-find #"(\d{4})[/-](\d{1,2})[/-](\d{1,2})" (str v))]
      (let [[_ y mo d] m]
        (str y "-" (if (= 1 (count mo)) (str "0" mo) mo) "-" (if (= 1 (count d)) (str "0" d) d))))))

(defn redact-personal-registrant
  "**汎用 `.jp` は個人でも登録できる。** 属性型（`co.jp` `or.jp` …）は組織に限られる
   ので登録者名は組織名だが、`example.jp` の `[登録者名]` は生身の人であることが
   ある —— 実測 2026-08-19、190 ドメインを引いた 1 件目のパスで `shikigaku.jp` の
   登録者として個人名を書き出していた（会社は登記法人なのに、ドメインは個人名義）。

   組織だと言い切れないときは名前を落とし、`:registry/registrant-withheld?` を残す
   —— **黙って消すと「レジストリが答えなかった」と区別が付かない。**"
  [m]
  (let [domain (:registry/domain m)
        nm (:registry/registrant-name m)]
    (if (or (str/blank? (str nm))
            (and domain (re-find attribute-type-jp-re domain))
            (organization-name? nm)
            (organization-name? (:registry/registrant-name-en m)))
      m
      (-> m
          (dissoc :registry/registrant-name :registry/registrant-name-en)
          (assoc :registry/registrant-withheld? true)))))

(defn parse-jprs-whois
  "JPRS の WHOIS 応答 → map。

   `Contact Information` 以降は**読む前に切る**。担当者ハンドル
   （`[登録担当者] TE347JP`）も allowlist に無いので入らない。"
  [text]
  (when-not (str/blank? (str text))
    (let [head (first (str/split (str text) #"Contact Information"))
          acc (reduce
               (fn [m line]
                 (if-let [[_ k v] (re-find #"\[([^\]]+)\]\s+(.*)$" line)]
                   (let [attr (get jprs-fields (str/trim k))
                         v (str/trim v)]
                     (cond
                       (nil? attr) m
                       (str/blank? v) (if (= attr :registry/signing-key) m m)
                       (multi-fields attr) (update m attr (fnil conj []) v)
                       :else (assoc m attr v)))
                   m))
               {}
               (str/split-lines head))]
      (when (seq acc)
        (redact-personal-registrant
         (cond-> (-> acc
                    (dissoc :registry/signing-key)
                    (assoc :registry/source "jprs-whois"))
          (:registry/domain acc) (assoc :registry/domain (str/lower (:registry/domain acc)))
          (:registry/created-on acc) (assoc :registry/created-on (normalize-date (:registry/created-on acc)))
          (:registry/connected-on acc) (assoc :registry/connected-on (normalize-date (:registry/connected-on acc)))
          (:registry/expires-on acc) (assoc :registry/expires-on (normalize-date (:registry/expires-on acc)))
          (:registry/updated-at acc) (assoc :registry/updated-at (normalize-date (:registry/updated-at acc)))
          ;; 署名鍵欄が空でないことが DNSSEC 署名の申告。空欄は「未署名」。
          true (assoc :registry/dnssec-signed?
                      (boolean (some-> (:registry/signing-key acc) str/trim seq)))
          (:registry/nameservers acc)
          (assoc :registry/nameservers (vec (distinct (map str/lower (:registry/nameservers acc)))))))))))

;; ---------- RDAP（gTLD） ----------

(defn- rdap-event [events action]
  (some (fn [e] (when (= action (get e "eventAction"))
                  (normalize-date (get e "eventDate"))))
        events))

(defn- rdap-registrar
  "role が registrar の entity の表示名だけを取る（vCard の `fn`）。
   registrant / technical / abuse は**見ない** —— redact されていない日に拾わない。"
  [entities]
  (some (fn [e]
          (when (some #{"registrar"} (get e "roles"))
            (some (fn [item]
                    (when (and (vector? item) (= "fn" (first item)))
                      (let [v (last item)] (when (string? v) v))))
                  (second (get e "vcardArray")))))
        entities))

(defn parse-rdap
  "RDAP の domain object（JSON を clj 化したもの、key は文字列）→ map。"
  [m]
  (when (map? m)
    (let [events (get m "events")
          ns- (->> (get m "nameservers") (keep #(get % "ldhName")) (map str/lower) distinct vec)]
      (cond-> {:registry/source "rdap"}
        (get m "ldhName") (assoc :registry/domain (str/lower (get m "ldhName")))
        (seq (get m "status")) (assoc :registry/status (vec (get m "status")))
        (seq ns-) (assoc :registry/nameservers ns-)
        (rdap-event events "registration") (assoc :registry/created-on (rdap-event events "registration"))
        (rdap-event events "expiration") (assoc :registry/expires-on (rdap-event events "expiration"))
        (rdap-event events "last changed") (assoc :registry/updated-at (rdap-event events "last changed"))
        (rdap-registrar (get m "entities")) (assoc :registry/registrar (rdap-registrar (get m "entities")))
        true (assoc :registry/dnssec-signed?
                    (boolean (get-in m ["secureDNS" "delegationSigned"])))))))

;; ---------- こちらが引いた DNS ----------

(def mail-providers
  "MX ホスト → 事業者。**知らない形は nil のまま**（`:unknown` は「自前」ではない）。"
  [[#"aspmx.*google|googlemail|google\.com$" "google"]
   [#"mail\.protection\.outlook\.com$|outlook\.com$" "microsoft"]
   [#"pphosted\.com$|proofpoint" "proofpoint"]
   [#"mimecast" "mimecast"]
   [#"cloudflare" "cloudflare"]
   [#"sakura\.ne\.jp$" "sakura"]
   [#"secureserver\.net$" "godaddy"]
   [#"kagoya\.net$" "kagoya"]
   [#"lolipop\.jp$|gmo|onamae" "gmo"]
   [#"nifty\.com$|ocn\.ad\.jp$|biglobe" "jp-isp"]
   [#"cybozu|kddi|iij\.ad\.jp$" "jp-enterprise"]])

(defn mail-provider [mx-hosts]
  (some (fn [[re label]]
          (when (some #(re-find re (str/lower (str %))) mx-hosts) label))
        mail-providers))

(defn dns-facts
  "引いた結果 → `:dns/*`。**引けなかったことと、無いことを分ける** ——
   `:dns/queried?` が false なら、以下の不在は事実ではなく未測定である。"
  [{:keys [ns mx txt queried? observed-at]}]
  (let [mx-hosts (vec (sort (distinct (map str/lower (or mx [])))))
        txt* (map str/lower (or txt []))]
    (cond-> {:dns/queried? (boolean queried?)
             :dns/observed-at observed-at}
      (seq ns) (assoc :dns/nameservers (vec (sort (distinct (map str/lower ns)))))
      (seq mx-hosts) (assoc :dns/mx mx-hosts)
      (mail-provider mx-hosts) (assoc :dns/mail-provider (mail-provider mx-hosts))
      queried? (assoc :dns/spf? (boolean (some #(str/starts-with? % "v=spf1") txt*))))))

;; ---------- record ----------

(defn record
  "1 ドメイン分。`:company/houjin-bangou` は web-presence 側から渡す。"
  [{:keys [host domain houjin-bangou legal-name registry dns dmarc? observed-at]}]
  (cond-> (merge {:domain/host host
                  :domain/name domain
                  :source/dataset dataset
                  :source/observed-at observed-at}
                 (dissoc registry :registry/domain)
                 dns)
    houjin-bangou (assoc :company/houjin-bangou houjin-bangou
                         :company/registration-no houjin-bangou)
    legal-name (assoc :company/legal-name legal-name)
    (some? dmarc?) (assoc :dns/dmarc? (boolean dmarc?))))

(defn registrant-agrees?
  "レジストリの `[組織名]` と法人番号側の商号が同じ会社を指しているか。

   表記は揺れる。空白（`株式会社 足立機械製作所`）だけでなく**全角と半角**でも揺れ、
   法人番号側は全角（`ＮＴＴインフラネット`）、レジストリは半角（`NTT`）を使う ——
   実測 2026-08-19、この 1 点で 38 件の「不一致」のうち 20 件以上が偽物だった。
   NFKC で均してから比べる。

   **違っていても record は捨てない** —— `:registry/name-agrees?` として残す。
   本物の不一致（親会社がグループのドメインを持つ、旧字体の商号）は消す対象ではなく、
   見る対象である。"
  [registrant legal-name]
  (when (and (not (str/blank? (str registrant))) (not (str/blank? (str legal-name))))
    (let [nfkc (fn [x] #?(:clj (java.text.Normalizer/normalize x java.text.Normalizer$Form/NFKC)
                          :cljs (.normalize (str x) "NFKC")))
          norm #(-> (str %) nfkc (str/replace #"[\s　・･]" "") str/lower)]
      (= (norm registrant) (norm legal-name)))))

(defn corpus-manifest
  [{:keys [observed-at record-count queried resolved-registry queried-dns]}]
  (cond-> {:corpus/manifest true
           :corpus/projection true
           :corpus/format :edn-lines
           :source/dataset dataset
           :source/authority "JP/JPRS + IANA RDAP + measured DNS"
           :source/attribution "出典：JPRS WHOIS（株式会社日本レジストリサービス）および各レジストリの RDAP。DNS レコードは当方が問い合わせて観測した値"
           :source/observed-at observed-at}
    queried (assoc :projection/queried queried)
    resolved-registry (assoc :projection/registry-answered resolved-registry)
    queried-dns (assoc :projection/dns-answered queried-dns)
    record-count (assoc :corpus/record-count record-count)))
