(ns jpki.core
  "公的個人認証サービス（JPKI）の**署名用電子証明書**で作られた署名を、受け取って
  検証する側の実装。portable `.cljc`。

  ## これが埋める穴と、埋めない穴

  `cloud.itonami.app.esign` は立会人型（事業者署名型）である。三省 Q&A の整理では
  それでも電子署名法 2 条の電子署名に当たり得るし、固有性が十分なら 3 条の推定も
  及び得る。**当事者型は別の道**で、利用者本人の証明書で署名されるため 3 条の推定が
  最も素直に働く。日本でその証明書を一般に持っているのはマイナンバーカードの
  署名用電子証明書だけである。

  この namespace が実装するのは **検証側だけ**。カード側のセレモニー（NFC/PC-SC の
  APDU、署名用パスワードの入力、カード内での署名生成）はハードウェアと専用ドライバ
  を要し、ここには無い。**「JPKI 対応」と書けるのは、外部で作られた署名を受け取って
  検証できる、という意味においてだけである。**

  ## 失効確認はここでは完結しない（重要）

  JPKI の失効情報は誰でも引けるものではなく、**署名検証者として認定または届出を
  した事業者**だけが J-LIS の失効情報提供サービスに接続できる。したがって
  `verify-signature` は失効を確認しない。確認したふりもしない —
  `:revocation :not-checked` を必ず返し、`revocation-note` がその意味を文にする。

  失効確認なしの検証で言えるのは「この証明書が発行された時点でこの鍵が本人のもの
  だった」までで、「署名時点で有効だった」ではない。両者を混ぜないことが、この
  namespace の一番大事な仕事である。

  ## 基本4情報は要求されたときだけ読む

  署名用電子証明書は subjectAltName の otherName に氏名・生年月日・性別・住所を
  持つ（arc `1.2.392.200149.8.5`）。**これは個人情報そのもの**なので、
  `parse-certificate` は読まない。読むのは `basic-four` を明示的に呼んだときだけで、
  呼び出し側にその判断を残す。`x509.core/other-names` が要素のまま返すのも同じ
  理由による。

  ## テスト fixture は本物ではない

  実際の署名用電子証明書は個人情報を含み、公開リポジトリに置けない。テストは
  **JPKI と同じ形に作った合成証明書**に対して行っている。したがって検証されている
  のは構造の読み取りと拒否の条件であって、**実カードとの相互運用性ではない**。
  それは実カードでの検証が済むまで未証明のままである。"
  (:require [asn1.core :as asn1]
            [asn1.oid :as oid]
            [kotoba.lang.text :as str]
            [cms.core :as cms]
            [x509.core :as x509]))

(def schema "kotoba-lang.jpki.v1")

(def basic-four-fields
  "otherName の OID 名 → 基本4情報のどれか。値そのものは扱わない。"
  {:jpki-basic-four-name :name
   :jpki-basic-four-birth-date :birth-date
   :jpki-basic-four-sex :sex
   :jpki-basic-four-address :address})

(def issuer-hints
  "署名用電子証明書らしさを見分ける手がかり。

  **判定の根拠にはしない。** 発行者名は誰でも名乗れるので、これは「JPKI のつもりで
  渡された証明書か」を UI が案内するためのヒントであって、信頼の判断ではない。
  信頼は `verify-signature` に渡される root 証明書だけが決める。"
  {:organization "Japan Agency for Local Authority Information Systems"
   :organizational-unit-fragment "Japanese Public Key Infrastructure for digital signature"})

(defn signature-certificate-shaped?
  "この証明書が署名用電子証明書の形をしているか。

  `nonRepudiation` があること、CA でないこと、基本4情報の otherName を持つこと。
  **形の話であって、本物かどうかの話ではない** — 名前が示すとおり `shaped?` で
  終わっており、`verify-signature` の判断には使われない。"
  [certificate]
  (let [usage (x509/key-usage certificate)
        others (x509/other-names certificate)]
    (boolean (and (not (x509/ca? certificate))
                  usage
                  (contains? usage :non-repudiation)
                  (seq others)
                  (some (fn [[dotted _]]
                          (contains? basic-four-fields (oid/named dotted)))
                        others)))))

(defn basic-four
  "基本4情報（氏名・生年月日・性別・住所）。

  **明示的に呼ばれたときだけ読む。** `parse-certificate` に含めないのは、これが
  個人情報そのものであり、ログや画面に出るかどうかを呼び出し側が決めるべきだから。

  `:sex` は JIS X 0303 の 1=男性 / 2=女性 / 9=不明 をそのまま返す。数字を語に
  変換しないのは、変換した時点でこの namespace が分類の語彙を決めてしまうから。"
  [certificate]
  (let [others (x509/other-names certificate)]
    (reduce (fn [acc [dotted elements]]
              (if-let [field (get basic-four-fields (oid/named dotted))]
                (assoc acc field (some-> (first elements) asn1/string-value))
                acc))
            {}
            others)))

(defn parse-certificate
  "署名用電子証明書として読める範囲。**基本4情報は含まない**（`basic-four` を参照）。"
  [data]
  (let [certificate (x509/parse data)]
    {:jpki/schema schema
     :jpki/certificate certificate
     :jpki/shaped? (signature-certificate-shaped? certificate)
     :jpki/serial-number (:x509/serial-number certificate)
     :jpki/subject (:text (:x509/subject certificate))
     :jpki/issuer (:text (:x509/issuer certificate))
     :jpki/not-before (:x509/not-before certificate)
     :jpki/not-after (:x509/not-after certificate)
     :jpki/key-usage (x509/key-usage certificate)
     ;; 呼び出し側が「これは JPKI のつもりで渡されたか」を案内できるように。
     ;; 信頼の判断ではない。
     :jpki/issuer-hint-matches?
     (let [issuer (:attributes (:x509/issuer certificate))
           subject (:attributes (:x509/subject certificate))]
       (boolean (or (= (:organization-name issuer) (:organization issuer-hints))
                    (some-> (:organizational-unit-name subject)
                            (str/includes? (:organizational-unit-fragment issuer-hints))))))}))

(defn revocation-note
  "失効未確認であることの説明文。

  返り値を作る側ではなく読む側のために here にある。「検証できました」とだけ書く
  UI は、失効確認をしていないという事実を隠す。"
  [{:keys [revocation]}]
  (when (= :not-checked revocation)
    (str "この検証では失効確認をしていません。JPKI の失効情報は署名検証者として"
         "認定・届出をした事業者だけが J-LIS から取得でき、この実装はそこに接続"
         "しません。したがって「証明書が発行された時点でこの鍵が本人のものだった」"
         "までは言えますが、「署名時点で有効だった」は言えません。")))

(defn- refused [reason detail]
  {:verified false :reason reason :detail detail :revocation :not-checked})

(defn verify-signature
  "外部で作られた CMS 署名を、JPKI 証明書のものとして検証する。

    :content    署名対象（detached 署名なので必須）
    :roots      信頼する CA 証明書（parsed）。**必須。** 空だと何も検証しない
    :at         署名時刻とみなす ISO instant。証明書の有効期間はここで見る
    :digest-fn / :verify-fn

  返すのは `{:verified bool :revocation :not-checked …}`。`:revocation` は常に
  返り、常に `:not-checked` である — 省略すれば「確認した」と読まれ、確認して
  いないのだから、それは嘘になる。"
  [signed-data {:keys [content roots at digest-fn verify-fn]}]
  (when (empty? roots)
    (throw (ex-info "信頼する root 証明書なしでは、この検証は何も検証しません。"
                    {:type :jpki/no-roots})))
  (let [signer (first (:cms/signer-infos signed-data))
        certificate (cms/certificate-for signed-data (:signer/sid signer))]
    (cond
      (nil? certificate)
      (refused :signer-certificate-not-found "署名者の証明書がメッセージにありません")

      ;; 形の確認は拒否の理由になる。当事者型を名乗る署名が nonRepudiation を
      ;; 持たない証明書で作られていたら、それは別物である。
      (not (signature-certificate-shaped? certificate))
      (refused :not-a-signature-certificate
               (str "署名用電子証明書の形をしていません（keyUsage="
                    (pr-str (x509/key-usage certificate)) "）"))

      (and at (not (x509/valid-at? certificate at)))
      (refused :certificate-not-valid-at-signing-time
               (str "署名時刻 " at " は証明書の有効期間 "
                    (:x509/not-before certificate) "–" (:x509/not-after certificate)
                    " の外です"))

      :else
      (let [issuer (first (filter #(:verified (x509/verify-signature certificate % verify-fn))
                                  roots))]
        (cond
          (nil? issuer)
          (refused :not-issued-by-a-trusted-root
                   "この証明書は、渡された root のどれからも発行されていません")

          :else
          (let [result (cms/verify-signer-info
                        signed-data signer
                        {:content content :digest-fn digest-fn :verify-fn verify-fn
                         :certificate certificate})]
            (if-not (:verified result)
              (refused (:reason result) (:detail result))
              {:verified true
               ;; 常に。省略は「確認した」と読まれる。
               :revocation :not-checked
               :certificate certificate
               :issuer (:text (:x509/subject issuer))
               :serial-number (:x509/serial-number certificate)
               :signing-time (:signing-time result)
               ;; 基本4情報は入れない。読むかどうかは呼び出し側が決める。
               :basic-four-available? (seq (x509/other-names certificate))})))))))

(defn presumption-note
  "電子署名法 3 条の推定について、この検証結果が支えるものと支えないもの。

  法律判断ではなく、**この実装が何を確かめたか**の要約。判断は弁護士のもので、
  その判断に必要な事実をここが正確に渡す。"
  [{:keys [verified revocation]}]
  (cond
    (not verified)
    "署名を検証できていないため、電子署名法 3 条の推定を論じる前提がありません。"

    (= :not-checked revocation)
    (str "本人の署名用電子証明書による署名として検証できました（当事者型）。"
         "ただし失効確認をしていないため、署名時点で証明書が有効だったことは"
         "この検証だけでは示せません。3 条の推定を主張するには、失効確認の記録が"
         "別途要ります。")

    :else
    "本人の署名用電子証明書による署名として検証でき、失効確認も行われています。"))
