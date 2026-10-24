(ns kyoninka.gbr-waste-carrier
  "England の controlled waste carrier 登録（upper tier）の手続き data。
  ADR-2607141620。

  **これは『許可』ではなく『登録』だが、未登録での運搬は刑事罰の対象**
  （Control of Pollution (Amendment) Act 1989 s.1）。手続き data としては
  sanpai / kobutsu と同じ形で持つ。

  法的根拠と所管庁は workspace 内の既存データ
  （`cloud-itonami-licensed-operator` の `[\"GBR\" :sector/industrial-waste-collection]`、
  `:rule/verification :primary-source-read` / `:rule/retrieved-at \"2026-07-26\"`）に
  由来する。窓口・手数料・有効期間・必要情報は GOV.UK と legislation.gov.uk の
  一次情報を 2026-08-07 に取得した。

  ## 日本の 2 本と決定的に違う点（読む前に知っておくこと）

  - **自ら排出した廃棄物でも構外へ運べば登録が要る。** s.1(2)(a) の除外は
    『同一構内の異なる場所の間』に限られ、廃掃法14条1項但書のような
    『自ら運搬する排出事業者』の一般除外が無い。ただし reg 24(5) の
    specified person（自ら生産した廃棄物のみを運ぶ者。**建設・解体廃棄物を除く**）に
    当たれば lower tier で無料・無期限。この 2 つの関係は
    `:procedure/legal-questions` の `:jibun-haishutsu` で保持する。
  - **`:procedure/standard-period-days` を収録していない。** Waste (England and Wales)
    Regulations 2011 reg 29 は Environment Agency の審査期間を定めておらず、
    EA が公表する標準処理期間も見つからなかった。**推測で埋めるより出さない**
    （ADR-2607141620 捏造ゼロ原則）。検索に出た『2 か月』『4 か月』は
    NIEA / Natural Resources Wales の値で England のものではない。
  - **手数料が整数ではない**（£191.02）。JPY には最小単位の端数が無いため
    既存 2 本では起きなかった。**この値が schema を直させた** —— 額は最小単位
    （pence）の整数 19102 で持ち、`:procedure/fee` の `:minor-unit` が 1 通貨単位
    あたりの最小単位数（GBP は 100）を持つ。浮動小数で金額を持たない。
  - **額を定めているのは法令ではなく Environment Agency**。2025-10 の £184 から
    2026-08 の £191.02 へ、法改正を経ずに動いている。全国一律なので単一の額を
    書けるが、`:set-by` の level は `:statute` ではなく `:national-authority`。

  収録値は :verify フラグ付き — 申請直前に GOV.UK で実値を確認すること
  （それ自体が step 1）。実際 2025-10 の Environment Agency blog は £184 / £125、
  2026-08 現在の GOV.UK は £191.02 / £130.25 で、**改定されている**。"
  (:require [kyoninka.schema :as schema]))

(def procedure
  {:procedure/id :gbr-waste-carrier
   :procedure/name "controlled waste carrier 登録（upper tier・England / Environment Agency）"
   :procedure/law "Control of Pollution (Amendment) Act 1989 s.1（無登録運搬の罪）／Waste (England and Wales) Regulations 2011 (SI 2011/988) Part 8（登録手続・reg 24〜34）"
   ;; ISO 3166-1 alpha-3。**England のみの制度**で、Scotland (SEPA) /
   ;; Wales (Natural Resources Wales) / Northern Ireland (DAERA) は別手続き。
   ;; 国より細かい単位は :procedure/window が持つ（schema.cljc の約束）。
   :procedure/jurisdiction "GBR"
   ;; **法域コードより狭い。** この登録制度は England のみ —— Wales(NRW)・
   ;; Scotland(SEPA)・Northern Ireland(NIEA) は別制度で、"GBR" 全域を覆わない。
   :procedure/extent "England"
   ;; 出所。**docstring ではなく data として持つ**（query から引けるように）。
   :procedure/source-urls
   [
                        "https://environmentagency.blog.gov.uk/2025/10/01/register-as-a-waste-carrier-broker-or-dealer-at-gov-uk/"
                        "https://www.gov.uk/government/publications/reforming-the-waste-carrier-broker-and-dealer-system/reforming-the-waste-carrier-broker-and-dealer-system"
                        "https://www.gov.uk/register-renew-waste-carrier-broker-dealer-england"
                        "https://www.gov.uk/waste-carrier-or-broker-registration"
                        "https://www.legislation.gov.uk/ukdsi/2026/9780348282726"
                        "https://www.legislation.gov.uk/ukpga/1989/14/section/1"
                        "https://www.legislation.gov.uk/ukpga/1989/14/section/3"
                        "https://www.legislation.gov.uk/ukpga/1990/43/section/34"
                        "https://www.legislation.gov.uk/uksi/2011/988/part/8"
                        "https://www.legislation.gov.uk/uksi/2011/988/regulation/24"
                        "https://www.legislation.gov.uk/uksi/2011/988/regulation/26"
                        "https://www.legislation.gov.uk/uksi/2011/988/regulation/29"
                        "https://www.legislation.gov.uk/uksi/2011/988/regulation/31"
                        "https://www.legislation.gov.uk/uksi/2011/988/regulation/33"
   ]
   :procedure/authority "Environment Agency（England）"
   :procedure/window "GOV.UK オンライン申請サービス『Register or renew as a waste carrier, broker or dealer』。照会は nccc-carrierbroker@environment-agency.gov.uk / 03708 506 506（月〜金 8:00-18:00）"
   :procedure/fee {;; **£191.02。最小単位（pence）の整数で持つ** —— 浮動小数で
                   ;; 金額を持たないため。`:minor-unit` が 1 通貨単位あたりの
                   ;; 最小単位数（GBP は 100）。schema をこの形に直した契機が
                   ;; まさにこの値で、JPY だけの間は顕在化しなかった。
                   :amount 19102
                   :minor-unit 100
                   :currency "GBP"
                   :kind :upper-tier-registration
                   ;; **法令本文に額は無い。** 額は Environment Agency の
                   ;; charging scheme にあり、法改正なしに改定される —— 実際
                   ;; 2025-10 £184 -> 2026-08 £191.02 と動いた。全国一律なので
                   ;; 単一の額を書けるが、それは法定額だからではない。
                   :set-by {:level :national-authority
                            :body "Environment Agency（England）"
                            :basis "Waste (England and Wales) Regulations 2011 (SI 2011/988) Part 8 に基づく Environment Agency の課金。額は法令本文ではなく GOV.UK 掲載の課金表にある"}
                   :verify (schema/unverified "GOV.UK『Register or renew as a waste carrier, broker or dealer』で最新額を確認。2025-10 の EA blog は £184、2026-08 の GOV.UK は £191.02 —— 実際に改定されている")}
   ;; :procedure/standard-period-days は**意図的に無い**。reg 29 は審査期間を
   ;; 定めておらず、EA の公表標準処理期間も確認できなかった。ns docstring 参照。
   ;; reg 31(2)「For other persons registration is for three years unless revoked」。
   ;; specified person（= lower tier）は reg 31(1) で無期限だが、他人の廃棄物を
   ;; 事業として運ぶ本手続きは該当しない。
   :procedure/valid-years 3

   :procedure/requirements
   [{:requirement/id :upper-tier-scope
     :requirement/name "upper tier 該当性（specified person でないこと）"
     :requirement/detail "reg 24(5) の specified person（慈善団体・voluntary organisation・waste collection/disposal/regulation authority・自ら生産した廃棄物のみを運ぶ者〈建設・解体廃棄物を除く〉・animal by-products / 鉱山採石廃棄物 / 農業廃棄物のみを扱う者）に当たらない場合は upper tier。他人の controlled waste を事業として運搬する ITAD 型の回収は upper tier で、有料・3年更新。"
     :requirement/blocking? true}
    {:requirement/id :role-carrier-broker-dealer
     :requirement/name "carrier / broker / dealer の別の確定"
     :requirement/detail "reg 25「No person may act as a broker of or dealer in controlled waste unless registered」。自ら運搬せず処分を手配するだけのスキームでも broker / dealer として登録が要る。申請時に carrier / broker / dealer のどれとして登録するかを申告する。"
     :requirement/blocking? true}
    {:requirement/id :no-relevant-offence
     :requirement/name "relevant offence の有罪判決に係る拒否事由"
     :requirement/detail "reg 29(5)：申請者または other relevant person が relevant offence（Theft Act 1968・Environmental Protection Act 1990・Fraud Act 2006 等、26 区分超と教唆・共謀・幇助）の有罪判決を受けており、かつ登録させることが undesirable と Environment Agency が判断する場合、登録を拒否しうる。拒否権限の制限は Control of Pollution (Amendment) Act 1989 s.3。"
     :requirement/blocking? true}
    {:requirement/id :duty-of-care
     :requirement/name "duty of care（登録後の継続義務）"
     :requirement/detail "Environmental Protection Act 1990 s.34：controlled waste を import / produce / carry / keep / treat / dispose する者、および broker / dealer は、廃棄物を authorised person（または authorised transport purposes の者）にのみ引き渡す等の合理的措置を講じる義務を負う。登録の要件ではないが、登録後に必ず伴う。"
     :requirement/blocking? false}]

   ;; **GOV.UK が『you'll need』として挙げるのはこの 3 点のみ。**
   ;; 日本の手続きのような証明書類の束は要求されていない（法人登記情報・
   ;; 住所等が要るかはページに記載が無いので**書かない**）。
   :procedure/documents
   [{:document/id :officer-identities :document/name "組織の executive / owner / director / partner の氏名と生年月日" :document/who :officers}
    {:document/id :environmental-offences :document/name "上記の者が犯した environmental offence の詳細" :document/who :officers}
    {:document/id :payment-method :document/name "支払手段（デビットカードまたはクレジットカード）" :document/who :company}]

   :procedure/steps
   [{:step/id :verify-current-rules :step/order 1 :step/requires-human true
     :step/title "GOV.UK / Environment Agency で最新の手数料・tier 判定・申請経路を確認"
     :step/detail "収録値は 2026-08-07 取得の標準値。手数料は実際に改定されている（2025-10 £184 → 2026-08 £191.02）ので、申請直前に必ず再取得する。"
     :step/errand {:kind :verify-authority-info :draft-via :tayori
                   :evidence-schema {:authority :string :verified :map
                                     :source :string :date :iso-date}}}
    {:step/id :determine-tier :step/order 2 :step/requires-human false
     :step/title "upper tier / lower tier の判定（reg 24(5) specified person 該当性）"
     :step/detail "自ら生産した廃棄物のみを運ぶなら lower tier（無料・無期限）。ただし建設・解体廃棄物は除かれ、他人の廃棄物を運ぶなら upper tier。"}
    {:step/id :determine-role :step/order 3 :step/requires-human false
     :step/title "carrier / broker / dealer のどれとして登録するかの確定（reg 25）"
     :step/detail "運搬の主体になるか、処分を手配するだけかでロールが変わる。両方に該当することもある。"}
    {:step/id :collect-documents :step/order 4 :step/requires-human false
     :step/title "申請に必要な情報の収集（:procedure/documents のチェックリスト消化）"
     :step/errand {:kind :collect-documents :draft-via nil
                   :evidence-schema {:doc :keyword :obtained-date :iso-date}}}
    {:step/id :submit :step/order 5 :step/requires-human true
     :step/title "GOV.UK オンラインサービスから申請し登録手数料を納付"
     :step/detail "提出と支払いを伴うので human gate。reg 29：登録されると Environment Agency が certificate of registration を交付する。無登録で運搬すると unlimited fine。"}
    {:step/id :respond-to-review :step/order 6 :step/requires-human true
     :step/title "審査対応（照会への応答、拒否された場合の不服申立て）"
     :step/detail "拒否・取消しに対する不服申立ては Control of Pollution (Amendment) Act 1989 s.4 により、reg 33 で『refusal or revocation から 28 日以内』に Secretary of State（Wales は Welsh Ministers）へ到達させる必要がある。"}
    {:step/id :post-registration :step/order 7 :step/requires-human true
     :step/title "登録後の義務対応（登録証の提示、duty of care、登録内容の変更届）"
     :step/detail "警察官・Environment Agency / 地方自治体の authorised officer の求めに応じて登録の証明を提示する。EPA 1990 s.34 の duty of care を継続的に負う。登録内容の更新は £49.62、事業形態の変更に伴う新規登録は £191.02。"}
    {:step/id :renew :step/order 8 :step/requires-human true
     :step/title "3 年ごとの更新（upper tier）"
     :step/detail "reg 31(2) により upper tier 登録は 3 年。更新手数料 £130.25（2026-08 時点の GOV.UK 公表値、要再確認）。lower tier は更新不要。"}]

   ;; 結論を出さずに保持する法的論点
   :procedure/legal-questions
   [{:question/id :jibun-haishutsu
     :question/title "自ら排出した廃棄物を自ら運ぶ場合の扱い（s.1(2)(a) と reg 24(5) の関係）"
     :question/detail "COPA(A) 1989 s.1(2)(a) の除外は『同一構内の異なる場所の間』の運搬に限られ、日本の廃掃法14条1項但書より狭い —— 構外へ運べば s.1 の登録義務が及ぶ。一方 reg 24(5) の specified person は『自ら生産した廃棄物のみを運ぶ者（建設・解体廃棄物を除く）』を含み、GOV.UK も『registration is usually free if you only transport waste you produce yourself』と述べる。つまり『登録は要るが lower tier で無料』という整理になるはずだが、ITAD で引き取った顧客資産が『自ら生産した廃棄物』に当たらないことの帰結（= upper tier 確定）を条文で押さえきれていない。"
     :question/status :open}
    {:question/id :carrier-vs-broker
     :question/title "運搬を第三者に委託するスキームで carrier 登録が要るか、broker / dealer 登録か"
     :question/detail "s.1 は『運搬する』行為を捕捉するので、自社が運搬に関与しなければ carrier としては及ばない（workspace の licensed-operator catalog も :route/defer をこの理由で :conditional としている）。ただし reg 25 は broker / dealer に別の登録義務を課しており、処分の手配のみを行う形でも登録から逃れられない可能性が高い。どちらのロールで登録すべきかはスキーム確定後に決める。"
     :question/status :open}
    {:question/id :cbd-reform
     :question/title "登録制の環境許可（environmental permit）制への置換"
     :question/detail "GOV.UK『Reforming the waste carrier, broker and dealer system』は『We will replace existing registrations with a \"standard rules\" environmental permit or a registered exemption』と述べる。upper tier 登録者は更新期限の到来時に permit を申請する（3 年かけて段階移行）、lower tier 登録者は system が live になってから 12 か月以内に exemption 登録か permit 申請をし、その後 lower tier 登録は消滅する。**実施日は当該ページに記載が無い**（『Once the new system is \"live\"』という表現のみ）。取得すべき手続きが登録から permit に変わりうるので、申請前に現況を確認する。"
     :question/status :open}
    {:question/id :digital-waste-tracking
     :question/title "Digital Waste Tracking (England) Regulations 2026 が carrier に課す義務の範囲"
     :question/detail "SI 2026/729 は 2026-10-01 施行（reg 1(1)）。本則の記録義務の名宛人は permitted facility の operator（reg 4(4)、荷受けの翌々営業日終わりまでに記録）であり、waste carrier / broker / dealer は Schedule 1 の情報要件に現れる。**carrier 自身が負う義務の内容と開始時期を一次資料で確定できていない**（商用解説記事は carrier の対応を 2027-10 とするが、SI 本文でその日付を確認できなかった）。登録手続きとは別に、運用開始前に確定させる。"
     :question/status :open}]})
