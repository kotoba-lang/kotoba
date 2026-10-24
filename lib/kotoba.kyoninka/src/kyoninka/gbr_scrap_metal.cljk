(ns kyoninka.gbr-scrap-metal
  "scrap metal licence（英国）の手続き data。Scrap Metal Dealers Act 2013。
  日本の古物商許可（`kyoninka.kobutsu`）に対応する位置づけだが、**捕捉範囲が違う** ——
  英国は中古品全般ではなく金属くずだけを免許制にしている
  （`cloud-itonami-licensed-operator` の catalog `[\"GBR\" :sector/scrap-metal-dealing]`）。

  収録値は :verify フラグ付き — 申請直前に発給する council の公式ページで実値・様式を
  確認すること（それ自体が step 1）。

  ## 日本の 2 手続きと構造が違う点（値を写す前に読むこと）

  - **発給者が国でも都道府県でもなく地方自治体（council）** で、**手数料は自治体が
    自分で決める**（Schedule 1 para 6(1)）。全国一律の額は存在しない ——
    だから `:procedure/fee` に `:amount` を**書かない**。実測した幅は
    site licence 新規で £181（Leeds）〜 £804.78（Kirklees）で 4 倍以上開く。
    `:verify` が「最新額を確認せよ」ではなく「**そもそも額はここでは決まらない**」を
    表している点が kobutsu / sanpai と異なる。
  - **標準処理期間の全国値も存在しない。** Home Office の supplementary guidance にも
    法にも決定期限が無く、公表するかは council 次第（Leeds は 28 日と自ら公表、
    Peterborough / Buckinghamshire / Kirklees は公表していない）。よって
    `:procedure/standard-period-days` にも `:value` を書かない。
  - **免許は 1 自治体につき 1 枚**（s.2(9)）。site licence と collector's licence を
    同一自治体で併有できない。複数自治体で営むなら自治体ごとに申請する。
  - **有効期間 3 年**（Schedule 1 para 1(1)）。古物商許可に更新制度が無いのと対照的。

  ## 法域の但し書き

  `:procedure/jurisdiction` は ISO 3166-1 alpha-3 の \"GBR\" だが、**Scrap Metal
  Dealers Act 2013 の extent は England and Wales のみ**（s.22 が E+W 指定で、
  \"local authority\" を England の district / City of London / London borough と
  Wales の county / county borough に限定している）。Scotland・Northern Ireland は
  別制度で、本 procedure は**それらをカバーしない** —— `:procedure/legal-questions` の
  `:extent-scotland-ni` に open として残す（推測で埋めない）。"
  (:require [kyoninka.schema :as schema]))

(def procedure
  {:procedure/id :gbr-scrap-metal
   :procedure/name "scrap metal licence（英国 England and Wales・発給は地方自治体）"
   :procedure/law "Scrap Metal Dealers Act 2013 (c.10) s.1（免許の要求）・s.2（免許の種別と効力）・s.3（適格者審査）・Schedule 1（申請・手数料・3年）"
   ;; **法域。** ISO alpha-3 は GBR だが、根拠法の extent は England and Wales のみ。
   ;; 国より細かい単位は :procedure/window が持つ（窓口であって法域ではない）。
   :procedure/jurisdiction "GBR"
   ;; **法域コードより狭い。** SMDA 2013 の extent は England and Wales のみ
   ;; （s.22）。Scotland・Northern Ireland は別制度。
   :procedure/extent "England and Wales"
   :procedure/source-urls
   [
                        "https://www.buckinghamshire.gov.uk/business/business-licences-and-permits/scrap-metal-licences/apply-for-a-scrap-metal-dealer-licence/"
                        "https://www.gov.uk/find-licences/scrap-metal-dealer-registration"
                        "https://www.gov.uk/government/publications/scrap-metal-dealers-act-2013-supplementary-guidance/scrap-metal-dealers-act-2013-supplementary-guidance-accessible"
                        "https://www.gov.uk/guidance/complete-a-tax-check-for-a-taxi-private-hire-or-scrap-metal-licence"
                        "https://www.kirklees.gov.uk/beta/licensing/apply-for-a-scrap-metal-dealer-collectors-licence.aspx"
                        "https://www.leeds.gov.uk/licensing/other-licences/scrap-metal-dealer-registration"
                        "https://www.legislation.gov.uk/ukpga/2013/10/schedule/1"
                        "https://www.legislation.gov.uk/ukpga/2013/10/schedule/1/paragraph/2"
                        "https://www.legislation.gov.uk/ukpga/2013/10/section/1"
                        "https://www.legislation.gov.uk/ukpga/2013/10/section/11"
                        "https://www.legislation.gov.uk/ukpga/2013/10/section/12"
                        "https://www.legislation.gov.uk/ukpga/2013/10/section/13"
                        "https://www.legislation.gov.uk/ukpga/2013/10/section/15"
                        "https://www.legislation.gov.uk/ukpga/2013/10/section/2"
                        "https://www.legislation.gov.uk/ukpga/2013/10/section/21"
                        "https://www.legislation.gov.uk/ukpga/2013/10/section/22"
                        "https://www.legislation.gov.uk/ukpga/2013/10/section/3"
                        "https://www.legislation.gov.uk/ukpga/2013/10/section/3/enacted"
                        "https://www.peterborough.gov.uk/business/licences-and-permits/apply-for-a-licence/scrap-metal-dealer-licence"
   ]
   :procedure/authority "地方自治体（local authority / licensing authority）。England は district council・City of London の Common Council・London borough council、Wales は county council・county borough council（s.22）"
   :procedure/window "免許を受けようとする区域の council の licensing team。site licence は site の所在する自治体、collector's licence は mobile collector として活動する自治体（s.2(3)(5)）"
   ;; **:amount を書かない。** Schedule 1 para 6(1) は「An application must be
   ;; accompanied by a fee set by the authority」で、額を決めるのは自治体。
   ;; 代表額を 1 つ書けば、それ以外の全自治体で嘘になる。通貨だけは確定するので残す。
   :procedure/fee {;; **:amount を書かない。** 額は council が決めるので全国値が存在しない。
                   ;; 代表額はどれを選んでも残り全部で嘘になる。:verify が
                   ;; 「最新額を確認せよ」ではなく「そもそも額はここでは決まらない」を表す。
                   ;; 実際に引いた額は :procedure/fee-observations にある。
                   :currency "GBP"
                   :minor-unit 100
                   :kind :licence-application-fee-set-by-authority
                   :set-by {:level :sub-national
                            :body "各 council（licensing authority。二層制の shire area では county ではなく district）"
                            :basis "Scrap Metal Dealers Act 2013 Schedule 1 para 6(1)（licensing authority が費用回収の観点から額を定める）"}
                   :verify (schema/unverified "手数料は council ごとに異なる（Schedule 1 para 6(1)）。申請先 council の licensing fee 表で site / collector・新規 / 更新の別に実額を確認する。14 council を実測した結果は :procedure/fee-observations にあるが、**その min/max は法定の幅ではなく標本の端**であって、外側の額が無い証拠にはならない")}

   ;; 実測 14 council・38 観測（2026-08-07）。**この集合の min/max を制度の幅として
   ;; 引用しないこと** —— site 新規は £235（Cheshire East）〜£1,089（Newham）の
   ;; 4.6 倍、collector は £124〜£717 の 5.8 倍に開くが、それは「私が見た 14 council
   ;; がその範囲だった」でしかない。SMDA は各 licensing authority に費用回収額を
   ;; 自分で決めさせており、実際に計算方法が council ごとに大きく違う。
   ;;
   ;; **段階（:stage）は『ページ上の実際の表記』から決めた。** 6 council は
   ;; Grant/Renewal を 1 額で示しており、これを :new と書くと「区別していない」
   ;; という事実が消える。段階の表記が無い council は :unstated —— 更新額が
   ;; 新規と同じだと推測しない（Sheffield は実際に別行で同額、Leeds は更新の方が高い）。
   ;;
   ;; **年度を書いている council は 14 中 2 つだけ**（Cornwall / Cheshire East）で、
   ;; しかも Cornwall は同じ表で 2026-2027 と『Effective from 1st April 2025』が
   ;; 矛盾している。残り 12 は年度不明であって「今年度」ではない。
   ;;
   ;; 到達できなかった 10 council の内訳は概ね HTTP 403 / bot 検出であって
   ;; 額の非公表ではない（Manchester と Newport の 2 つだけが実際に非公表で、
   ;; 申請者にメールで問い合わせさせる）。検索要約が出した Cardiff（2022-23）・
   ;; Wiltshire（2020-21）・Swansea の 3 件は採らなかった —— **Swansea のものは
   ;; そもそも SMDA ではなく Environment Agency の廃棄物運搬業登録料**で、
   ;; 検索要約はこの 2 制度を取り違える（額は 1 桁違う）。
   :procedure/fee-observations
   [{:fee-observation/id "gbr-scrap-leeds-new"
     :fee-observation/procedure :gbr-scrap-metal
     :fee-observation/authority "Leeds City Council"
     :fee-observation/licence-type :unspecified
     :fee-observation/stage :new
     :fee-observation/rule-form :fixed
     :fee-observation/amount 18100
     :fee-observation/as-of "2026-08-07"
     :fee-observation/source-url "https://www.leeds.gov.uk/licensing/other-licences/scrap-metal-dealer-registration"
     :fee-observation/note "ページは取引種別だけで課金し site / collector を分けていない（表記は New application £181）。**この額を『site 免許の手数料』として引用しないこと** —— 表に無い区別を読み込むことになる"}
    {:fee-observation/id "gbr-scrap-leeds-renewal"
     :fee-observation/procedure :gbr-scrap-metal
     :fee-observation/authority "Leeds City Council"
     :fee-observation/licence-type :unspecified
     :fee-observation/stage :renewal
     :fee-observation/rule-form :fixed
     :fee-observation/amount 18300
     :fee-observation/as-of "2026-08-07"
     :fee-observation/source-url "https://www.leeds.gov.uk/licensing/other-licences/scrap-metal-dealer-registration"
     :fee-observation/note "表記は Renewal。更新 £183 が新規 £181 より高い —— 標本 14 council のうちここだけ"}
    {:fee-observation/id "gbr-scrap-kirklees-site-new"
     :fee-observation/procedure :gbr-scrap-metal
     :fee-observation/authority "Kirklees Council"
     :fee-observation/licence-type :site
     :fee-observation/stage :new
     :fee-observation/rule-form :fixed
     :fee-observation/amount 80478
     :fee-observation/as-of "2026-08-07"
     :fee-observation/source-url "https://www.kirklees.gov.uk/beta/licensing/apply-for-a-scrap-metal-dealer-collectors-licence.aspx"}
    {:fee-observation/id "gbr-scrap-kirklees-site-renewal"
     :fee-observation/procedure :gbr-scrap-metal
     :fee-observation/authority "Kirklees Council"
     :fee-observation/licence-type :site
     :fee-observation/stage :renewal
     :fee-observation/rule-form :fixed
     :fee-observation/amount 72513
     :fee-observation/as-of "2026-08-07"
     :fee-observation/source-url "https://www.kirklees.gov.uk/beta/licensing/apply-for-a-scrap-metal-dealer-collectors-licence.aspx"}
    {:fee-observation/id "gbr-scrap-kirklees-collector-new"
     :fee-observation/procedure :gbr-scrap-metal
     :fee-observation/authority "Kirklees Council"
     :fee-observation/licence-type :collector
     :fee-observation/stage :new
     :fee-observation/rule-form :fixed
     :fee-observation/amount 46761
     :fee-observation/as-of "2026-08-07"
     :fee-observation/source-url "https://www.kirklees.gov.uk/beta/licensing/apply-for-a-scrap-metal-dealer-collectors-licence.aspx"}
    {:fee-observation/id "gbr-scrap-kirklees-collector-renewal"
     :fee-observation/procedure :gbr-scrap-metal
     :fee-observation/authority "Kirklees Council"
     :fee-observation/licence-type :collector
     :fee-observation/stage :renewal
     :fee-observation/rule-form :fixed
     :fee-observation/amount 40902
     :fee-observation/as-of "2026-08-07"
     :fee-observation/source-url "https://www.kirklees.gov.uk/beta/licensing/apply-for-a-scrap-metal-dealer-collectors-licence.aspx"}
    {:fee-observation/id "gbr-scrap-sheffield-site-new"
     :fee-observation/procedure :gbr-scrap-metal
     :fee-observation/authority "Sheffield City Council"
     :fee-observation/licence-type :site
     :fee-observation/stage :new
     :fee-observation/rule-form :fixed
     :fee-observation/amount 37100
     :fee-observation/as-of "2026-08-07"
     :fee-observation/source-url "https://www.sheffield.gov.uk/business/licences-permits-registrations/scrap-metal-dealers-licence"
     :fee-observation/note "新規と更新を別行で示した上で同額（£371 for a new site licence / £371 to renew）。**区別していないのではなく、区別した上で同額**"}
    {:fee-observation/id "gbr-scrap-sheffield-site-renewal"
     :fee-observation/procedure :gbr-scrap-metal
     :fee-observation/authority "Sheffield City Council"
     :fee-observation/licence-type :site
     :fee-observation/stage :renewal
     :fee-observation/rule-form :fixed
     :fee-observation/amount 37100
     :fee-observation/as-of "2026-08-07"
     :fee-observation/source-url "https://www.sheffield.gov.uk/business/licences-permits-registrations/scrap-metal-dealers-licence"}
    {:fee-observation/id "gbr-scrap-sheffield-collector-new"
     :fee-observation/procedure :gbr-scrap-metal
     :fee-observation/authority "Sheffield City Council"
     :fee-observation/licence-type :collector
     :fee-observation/stage :new
     :fee-observation/rule-form :fixed
     :fee-observation/amount 26800
     :fee-observation/as-of "2026-08-07"
     :fee-observation/source-url "https://www.sheffield.gov.uk/business/licences-permits-registrations/scrap-metal-dealers-licence"}
    {:fee-observation/id "gbr-scrap-sheffield-collector-renewal"
     :fee-observation/procedure :gbr-scrap-metal
     :fee-observation/authority "Sheffield City Council"
     :fee-observation/licence-type :collector
     :fee-observation/stage :renewal
     :fee-observation/rule-form :fixed
     :fee-observation/amount 26800
     :fee-observation/as-of "2026-08-07"
     :fee-observation/source-url "https://www.sheffield.gov.uk/business/licences-permits-registrations/scrap-metal-dealers-licence"}
    {:fee-observation/id "gbr-scrap-bradford-site"
     :fee-observation/procedure :gbr-scrap-metal
     :fee-observation/authority "City of Bradford Metropolitan District Council"
     :fee-observation/licence-type :site
     :fee-observation/stage :grant-or-renewal
     :fee-observation/rule-form :fixed
     :fee-observation/amount 42500
     :fee-observation/as-of "2026-08-07"
     :fee-observation/source-url "https://www.bradford.gov.uk/business/licensing/licensing-fees/"
     :fee-observation/note "表記は Site Licence - Grant/Renewal で 1 額。新規と更新を区別していない"}
    {:fee-observation/id "gbr-scrap-bradford-collector"
     :fee-observation/procedure :gbr-scrap-metal
     :fee-observation/authority "City of Bradford Metropolitan District Council"
     :fee-observation/licence-type :collector
     :fee-observation/stage :grant-or-renewal
     :fee-observation/rule-form :fixed
     :fee-observation/amount 23500
     :fee-observation/as-of "2026-08-07"
     :fee-observation/source-url "https://www.bradford.gov.uk/business/licensing/licensing-fees/"
     :fee-observation/note "表記は Collectors Licence - Grant/Renewal で 1 額"}
    {:fee-observation/id "gbr-scrap-bucks-site-new"
     :fee-observation/procedure :gbr-scrap-metal
     :fee-observation/authority "Buckinghamshire Council"
     :fee-observation/licence-type :site
     :fee-observation/stage :new
     :fee-observation/rule-form :fixed
     :fee-observation/amount 58100
     :fee-observation/as-of "2026-08-07"
     :fee-observation/source-url "https://www.buckinghamshire.gov.uk/business/business-licences-and-permits/scrap-metal-licences/apply-for-a-scrap-metal-dealer-licence/"}
    {:fee-observation/id "gbr-scrap-bucks-site-renewal"
     :fee-observation/procedure :gbr-scrap-metal
     :fee-observation/authority "Buckinghamshire Council"
     :fee-observation/licence-type :site
     :fee-observation/stage :renewal
     :fee-observation/rule-form :fixed
     :fee-observation/amount 47100
     :fee-observation/as-of "2026-08-07"
     :fee-observation/source-url "https://www.buckinghamshire.gov.uk/business/business-licences-and-permits/scrap-metal-licences/apply-for-a-scrap-metal-dealer-licence/"}
    {:fee-observation/id "gbr-scrap-bucks-collector-new"
     :fee-observation/procedure :gbr-scrap-metal
     :fee-observation/authority "Buckinghamshire Council"
     :fee-observation/licence-type :collector
     :fee-observation/stage :new
     :fee-observation/rule-form :fixed
     :fee-observation/amount 35400
     :fee-observation/as-of "2026-08-07"
     :fee-observation/source-url "https://www.buckinghamshire.gov.uk/business/business-licences-and-permits/scrap-metal-licences/apply-for-a-scrap-metal-dealer-licence/"}
    {:fee-observation/id "gbr-scrap-bucks-collector-renewal"
     :fee-observation/procedure :gbr-scrap-metal
     :fee-observation/authority "Buckinghamshire Council"
     :fee-observation/licence-type :collector
     :fee-observation/stage :renewal
     :fee-observation/rule-form :fixed
     :fee-observation/amount 26900
     :fee-observation/as-of "2026-08-07"
     :fee-observation/source-url "https://www.buckinghamshire.gov.uk/business/business-licences-and-permits/scrap-metal-licences/apply-for-a-scrap-metal-dealer-licence/"}
    {:fee-observation/id "gbr-scrap-peterborough-site"
     :fee-observation/procedure :gbr-scrap-metal
     :fee-observation/authority "Peterborough City Council"
     :fee-observation/licence-type :site
     :fee-observation/stage :unstated
     :fee-observation/rule-form :fixed
     :fee-observation/amount 59730
     :fee-observation/as-of "2026-08-07"
     :fee-observation/source-url "https://www.peterborough.gov.uk/business/licences-and-permits/apply-for-a-licence/scrap-metal-dealer-licence"
     :fee-observation/note "site の額は 1 つだけで、新規か更新かの表記が無い（更新の額は非公表）。variation £40 / replacement £25 は別"}
    {:fee-observation/id "gbr-scrap-peterborough-collector"
     :fee-observation/procedure :gbr-scrap-metal
     :fee-observation/authority "Peterborough City Council"
     :fee-observation/licence-type :collector
     :fee-observation/stage :unstated
     :fee-observation/rule-form :fixed
     :fee-observation/amount 33110
     :fee-observation/as-of "2026-08-07"
     :fee-observation/source-url "https://www.peterborough.gov.uk/business/licences-and-permits/apply-for-a-licence/scrap-metal-dealer-licence"
     :fee-observation/note "表記は mobile collector's licence。段階の表記が無い"}
    {:fee-observation/id "gbr-scrap-bristol-site"
     :fee-observation/procedure :gbr-scrap-metal
     :fee-observation/authority "Bristol City Council"
     :fee-observation/licence-type :site
     :fee-observation/stage :unstated
     :fee-observation/rule-form :fixed
     :fee-observation/amount 77000
     :fee-observation/as-of "2026-08-07"
     :fee-observation/source-url "https://www.bristol.gov.uk/business/licences-and-permits/other-licences-a-to-z/scrap-metal-dealer-licence"
     :fee-observation/note "表記は Site Licence のみで段階が無い。更新者には新規申請書の提出を案内しており実質同額と読めるが、**ページがそう書いているわけではない**ので :unstated。追加 site は 1 件 £113"}
    {:fee-observation/id "gbr-scrap-bristol-collector"
     :fee-observation/procedure :gbr-scrap-metal
     :fee-observation/authority "Bristol City Council"
     :fee-observation/licence-type :collector
     :fee-observation/stage :unstated
     :fee-observation/rule-form :fixed
     :fee-observation/amount 71700
     :fee-observation/as-of "2026-08-07"
     :fee-observation/source-url "https://www.bristol.gov.uk/business/licences-and-permits/other-licences-a-to-z/scrap-metal-dealer-licence"
     :fee-observation/note "£717 は site の 93%。他の council では collector が site の約半額なので、この比だけ大きく外れる"}
    {:fee-observation/id "gbr-scrap-cornwall-premises"
     :fee-observation/procedure :gbr-scrap-metal
     :fee-observation/authority "Cornwall Council"
     :fee-observation/licence-type :site
     :fee-observation/stage :grant-or-renewal
     :fee-observation/rule-form :fixed
     :fee-observation/amount 49000
     :fee-observation/fee-year "2026-2027"
     :fee-observation/as-of "2026-08-07"
     :fee-observation/source-url "https://www.cornwall.gov.uk/business-trading-and-licences/licences-and-street-trading/scrap-metal-dealers-registration/"
     :fee-observation/note "表記は Grant / Renewal - Premises（Cornwall は site/collector でなく Premises/Person と呼ぶ）。**年度がページ内で矛盾**: 列見出しは Fee (2026-2027) だが表の注記は Effective from 1st April 2025"}
    {:fee-observation/id "gbr-scrap-cornwall-person"
     :fee-observation/procedure :gbr-scrap-metal
     :fee-observation/authority "Cornwall Council"
     :fee-observation/licence-type :collector
     :fee-observation/stage :grant-or-renewal
     :fee-observation/rule-form :fixed
     :fee-observation/amount 34000
     :fee-observation/fee-year "2026-2027"
     :fee-observation/as-of "2026-08-07"
     :fee-observation/source-url "https://www.cornwall.gov.uk/business-trading-and-licences/licences-and-street-trading/scrap-metal-dealers-registration/"
     :fee-observation/note "表記は Grant / Renewal - Person。年度の矛盾は Premises 行と同じ"}
    {:fee-observation/id "gbr-scrap-cheshire-east-site"
     :fee-observation/procedure :gbr-scrap-metal
     :fee-observation/authority "Cheshire East Council"
     :fee-observation/licence-type :site
     :fee-observation/stage :unstated
     :fee-observation/rule-form :fixed
     :fee-observation/amount 23500
     :fee-observation/fee-year "2026/2027"
     :fee-observation/as-of "2026-08-07"
     :fee-observation/source-url "https://www.cheshireeast.gov.uk/business/environmental_health/fees_and_charges.aspx"
     :fee-observation/note "標本中の最安。**データの誤りではない** —— 表の見出しが Scrap Metal dealers で、備考欄が Scrap Metal Dealers Act 2013 を引いていることを再取得して確認した。更新・変更の行は非公表"}
    {:fee-observation/id "gbr-scrap-cheshire-east-collector"
     :fee-observation/procedure :gbr-scrap-metal
     :fee-observation/authority "Cheshire East Council"
     :fee-observation/licence-type :collector
     :fee-observation/stage :unstated
     :fee-observation/rule-form :fixed
     :fee-observation/amount 12400
     :fee-observation/fee-year "2026/2027"
     :fee-observation/as-of "2026-08-07"
     :fee-observation/source-url "https://www.cheshireeast.gov.uk/business/environmental_health/fees_and_charges.aspx"
     :fee-observation/note "£124 は標本中の最安で、Kirklees の collector の約 1/5"}
    {:fee-observation/id "gbr-scrap-nottingham-site"
     :fee-observation/procedure :gbr-scrap-metal
     :fee-observation/authority "Nottingham City Council"
     :fee-observation/licence-type :site
     :fee-observation/stage :unstated
     :fee-observation/rule-form :fixed
     :fee-observation/amount 44800
     :fee-observation/as-of "2026-08-07"
     :fee-observation/source-url "https://www.nottinghamcity.gov.uk/information-for-business/business-information-and-support/business-and-trading-licences-and-permits/regulatory-fees/"
     :fee-observation/note "表記は Site Licence のみ。更新の額は非公表"}
    {:fee-observation/id "gbr-scrap-nottingham-collector"
     :fee-observation/procedure :gbr-scrap-metal
     :fee-observation/authority "Nottingham City Council"
     :fee-observation/licence-type :collector
     :fee-observation/stage :unstated
     :fee-observation/rule-form :fixed
     :fee-observation/amount 22400
     :fee-observation/as-of "2026-08-07"
     :fee-observation/source-url "https://www.nottinghamcity.gov.uk/information-for-business/business-information-and-support/business-and-trading-licences-and-permits/regulatory-fees/"
     :fee-observation/note "表記は Collector Licence のみ。site のちょうど半額"}
    {:fee-observation/id "gbr-scrap-croydon-site-new"
     :fee-observation/procedure :gbr-scrap-metal
     :fee-observation/authority "London Borough of Croydon"
     :fee-observation/licence-type :site
     :fee-observation/stage :new
     :fee-observation/rule-form :fixed
     :fee-observation/amount 64400
     :fee-observation/as-of "2026-08-07"
     :fee-observation/source-url "https://www.croydon.gov.uk/business-licences-and-tenders/licences-permits-and-registrations/licence-and-permit-fees/licence-and-permit-fees/all-other-licence-fees"}
    {:fee-observation/id "gbr-scrap-croydon-site-renewal"
     :fee-observation/procedure :gbr-scrap-metal
     :fee-observation/authority "London Borough of Croydon"
     :fee-observation/licence-type :site
     :fee-observation/stage :renewal
     :fee-observation/rule-form :fixed
     :fee-observation/amount 52000
     :fee-observation/as-of "2026-08-07"
     :fee-observation/source-url "https://www.croydon.gov.uk/business-licences-and-tenders/licences-permits-and-registrations/licence-and-permit-fees/licence-and-permit-fees/all-other-licence-fees"}
    {:fee-observation/id "gbr-scrap-croydon-collector-new"
     :fee-observation/procedure :gbr-scrap-metal
     :fee-observation/authority "London Borough of Croydon"
     :fee-observation/licence-type :collector
     :fee-observation/stage :new
     :fee-observation/rule-form :fixed
     :fee-observation/amount 44600
     :fee-observation/as-of "2026-08-07"
     :fee-observation/source-url "https://www.croydon.gov.uk/business-licences-and-tenders/licences-permits-and-registrations/licence-and-permit-fees/licence-and-permit-fees/all-other-licence-fees"}
    {:fee-observation/id "gbr-scrap-croydon-collector-renewal"
     :fee-observation/procedure :gbr-scrap-metal
     :fee-observation/authority "London Borough of Croydon"
     :fee-observation/licence-type :collector
     :fee-observation/stage :renewal
     :fee-observation/rule-form :fixed
     :fee-observation/amount 40400
     :fee-observation/as-of "2026-08-07"
     :fee-observation/source-url "https://www.croydon.gov.uk/business-licences-and-tenders/licences-permits-and-registrations/licence-and-permit-fees/licence-and-permit-fees/all-other-licence-fees"}
    {:fee-observation/id "gbr-scrap-newham-site"
     :fee-observation/procedure :gbr-scrap-metal
     :fee-observation/authority "London Borough of Newham"
     :fee-observation/licence-type :site
     :fee-observation/stage :unstated
     :fee-observation/rule-form :fixed
     :fee-observation/amount 108900
     :fee-observation/as-of "2026-08-07"
     :fee-observation/source-url "https://www.newham.gov.uk/business-licensing-regulation/licences-%E2%80%93-scrap-metal-dealers"
     :fee-observation/note "標本中の最高額（£1,089）。表記は Site licence のみで段階が無い"}
    {:fee-observation/id "gbr-scrap-newham-collector"
     :fee-observation/procedure :gbr-scrap-metal
     :fee-observation/authority "London Borough of Newham"
     :fee-observation/licence-type :collector
     :fee-observation/stage :unstated
     :fee-observation/rule-form :fixed
     :fee-observation/amount 61050
     :fee-observation/as-of "2026-08-07"
     :fee-observation/source-url "https://www.newham.gov.uk/business-licensing-regulation/licences-%E2%80%93-scrap-metal-dealers"
     :fee-observation/note "£610.50。collector から site への variation に £825 という別建ての額がある"}
    {:fee-observation/id "gbr-scrap-chelmsford-site-new"
     :fee-observation/procedure :gbr-scrap-metal
     :fee-observation/authority "Chelmsford City Council"
     :fee-observation/licence-type :site
     :fee-observation/stage :new
     :fee-observation/rule-form :fixed
     :fee-observation/amount 43000
     :fee-observation/as-of "2026-08-07"
     :fee-observation/source-url "https://www.chelmsford.gov.uk/business/licensing/find-a-licence/scrap-metal/"
     :fee-observation/note "二層制の Essex では **county ではなく district が SMDA の licensing authority**"}
    {:fee-observation/id "gbr-scrap-chelmsford-site-renewal"
     :fee-observation/procedure :gbr-scrap-metal
     :fee-observation/authority "Chelmsford City Council"
     :fee-observation/licence-type :site
     :fee-observation/stage :renewal
     :fee-observation/rule-form :fixed
     :fee-observation/amount 27000
     :fee-observation/as-of "2026-08-07"
     :fee-observation/source-url "https://www.chelmsford.gov.uk/business/licensing/find-a-licence/scrap-metal/"
     :fee-observation/note "標本中で最も大きい更新割引（新規の 37% 引き）"}
    {:fee-observation/id "gbr-scrap-chelmsford-collector-new"
     :fee-observation/procedure :gbr-scrap-metal
     :fee-observation/authority "Chelmsford City Council"
     :fee-observation/licence-type :collector
     :fee-observation/stage :new
     :fee-observation/rule-form :fixed
     :fee-observation/amount 20000
     :fee-observation/as-of "2026-08-07"
     :fee-observation/source-url "https://www.chelmsford.gov.uk/business/licensing/find-a-licence/scrap-metal/"}
    {:fee-observation/id "gbr-scrap-chelmsford-collector-renewal"
     :fee-observation/procedure :gbr-scrap-metal
     :fee-observation/authority "Chelmsford City Council"
     :fee-observation/licence-type :collector
     :fee-observation/stage :renewal
     :fee-observation/rule-form :fixed
     :fee-observation/amount 17000
     :fee-observation/as-of "2026-08-07"
     :fee-observation/source-url "https://www.chelmsford.gov.uk/business/licensing/find-a-licence/scrap-metal/"}
    {:fee-observation/id "gbr-scrap-wrexham-site"
     :fee-observation/procedure :gbr-scrap-metal
     :fee-observation/authority "Wrexham County Borough Council"
     :fee-observation/licence-type :site
     :fee-observation/stage :grant-or-renewal
     :fee-observation/rule-form :fixed
     :fee-observation/amount 49500
     :fee-observation/as-of "2026-08-07"
     :fee-observation/source-url "https://www.wrexham.gov.uk/service/licensing/scrap-metal-dealers-licences"
     :fee-observation/note "表記は new/renewal を 1 額にまとめている"}
    {:fee-observation/id "gbr-scrap-wrexham-collector"
     :fee-observation/procedure :gbr-scrap-metal
     :fee-observation/authority "Wrexham County Borough Council"
     :fee-observation/licence-type :collector
     :fee-observation/stage :grant-or-renewal
     :fee-observation/rule-form :fixed
     :fee-observation/amount 23100
     :fee-observation/as-of "2026-08-07"
     :fee-observation/source-url "https://www.wrexham.gov.uk/service/licensing/scrap-metal-dealers-licences"
     :fee-observation/note "同じく new/renewal で 1 額。variation £88"}]
   ;; **:value を書かない。** 法にも Home Office guidance にも決定期限が無く、
   ;; 公表するかどうかも council 次第。全国値を書く根拠が存在しない。
   :procedure/standard-period-days {:verify (schema/unverified "全国共通の標準処理期間は存在しない（法・Home Office guidance とも決定期限を定めていない）。申請先 council が service standard を公表しているか確認する。実測例: Leeds は『28 days of receipt』と公表、Peterborough / Buckinghamshire / Kirklees は未公表")}
   :procedure/valid-years 3

   ;; 免許種別。**申請前にどちらかを選ぶ必要があり、同一自治体で併有できない**（s.2(9)）。
   :procedure/categories
   [{:id :site-licence :name "site licence"
     :itad-note "自治体内の**特定の site** で営むことを認める（s.2(3)）。免許に全 site を列挙し、site ごとに site manager を記名する（s.2(4)(c)(d)）。固定の解体・保管拠点を持つ ITAD 事業はこちら"}
    {:id :collectors-licence :name "collector's licence"
     :itad-note "自治体の区域内で **mobile collector** として営むことを認める（s.2(5)）。site を持たない巡回回収。免許は車両に掲示する"}]

   :procedure/requirements
   [{:requirement/id :suitable-person
     :requirement/name "適格者（suitable person）であること"
     :requirement/detail "s.3(1)『A local authority must not issue or renew a scrap metal licence unless it is satisfied that the applicant is a suitable person to carry on business as a scrap metal dealer.』法人の場合は director・secretary・shadow director、パートナーシップの場合は各 partner が個別に適格でなければならない。自治体は s.3(2) により、relevant offence の有罪歴・relevant enforcement action・過去の免許申請却下や取消・環境許可申請の却下・本法遵守体制の有無を考慮できる。s.3(7) により他自治体・Environment Agency・Natural Resources Body for Wales・警察に照会できる。"
     :requirement/blocking? true}
    {:requirement/id :licence-type-choice
     :requirement/name "免許種別の選択（同一自治体で併有不可）"
     :requirement/detail "s.2(9)『A person may hold more than one licence issued by different local authorities, but may not hold more than one licence issued by any one authority.』site licence と collector's licence のどちらかを自治体ごとに選ぶ。複数自治体で営むなら自治体ごとに別途申請する。"
     :requirement/blocking? true}
    {:requirement/id :site-manager
     :requirement/name "site manager の記名（site licence のみ）"
     :requirement/detail "s.2(4)(d) により site licence は各 site の site manager を記名しなければならない。記名される individual は s.3(2) の適格性審査の対象になる（申請書に氏名・生年月日・常居所を記載、Schedule 1 para 2(2)(b)）。collector's licence には site manager の概念が無い。"
     :requirement/blocking? true}
    {:requirement/id :tax-check
     :requirement/name "HMRC tax check（更新・他自治体での追加取得）"
     :requirement/detail "2022-04-04 以降、site licence / collector's licence を**更新**する前、または既に保有する免許と同種の免許を**他の licensing authority で**取得する前に、HMRC の tax check を完了し 9 桁の tax check code を council に提出しなければならない（gov.uk）。初回の新規申請では tax check ではなく納税義務の確認（confirm your tax responsibilities）が求められる。code を出さないと免許が失効する。"
     :requirement/blocking? true}
    {:requirement/id :basic-disclosure
     :requirement/name "Basic Disclosure Certificate（犯罪歴証明）"
     :requirement/detail "Home Office supplementary guidance:『To verify the information provided in the application form, licensing authorities request that applicants submit a Basic Disclosure Certificate for themselves and any person listed on the application form.』**法が直接課す条件ではなく、s.3 の適格性審査を裏付けるために自治体が求める運用**。実測した council（Leeds / Buckinghamshire / Kirklees）はいずれも要求しており、Buckinghamshire は『issued within the last month』と発行時期も指定する。有効期限の扱いが council ごとに違うので取得タイミングを窓口に確認する。"
     :requirement/blocking? true}
    {:requirement/id :cashless-payment
     :requirement/name "現金以外の支払体制（申請時に口座情報を届け出る）"
     :requirement/detail "s.12 により scrap metal の対価は (a) Bills of Exchange Act 1882 s.81A の譲渡不能小切手、または (b) 電子資金移動（クレジット/デビットカード等）でしか支払えない。申請書には s.12 の遵守に用いる銀行口座の情報を記載する（Schedule 1 para 2(1)）。**免許取得前に決済フローを現金前提で組まない。**"
     :requirement/blocking? true}]

   :procedure/documents
   [{:document/id :application-form :document/name "council の scrap metal licence 申請書（様式は自治体ごと。site / collector で別様式のことがある）" :document/who :company}
    {:document/id :applicant-identity :document/name "申請者の特定情報（法人: 名称・登記番号・登記上の事務所所在地／個人: 氏名・生年月日・常居所／パートナーシップ: 各 partner の氏名・生年月日・常居所）Schedule 1 para 2(1)" :document/who :company}
    {:document/id :trading-name :document/name "使用予定の trading name・電話番号・電子メールアドレス（Schedule 1 para 2(1)）" :document/who :company}
    {:document/id :other-area-sites :document/name "他の自治体の区域内で営む site の所在地一覧（Schedule 1 para 2(1)）" :document/who :company}
    {:document/id :site-addresses :document/name "免許に載せる各 site の所在地（site licence のみ。Schedule 1 para 2(2)(a)）" :document/who :company}
    {:document/id :site-manager-details :document/name "各 site manager の氏名・生年月日・常居所（site licence のみ。Schedule 1 para 2(2)(b)）" :document/who :officers}
    {:document/id :environmental-permit :document/name "関連する environmental permit / registration の内容（s.22(7) に列挙されたもの。**保有していれば開示する**という届出事項であり、保有自体が免許の条件ではない）" :document/who :company}
    {:document/id :prior-licences :document/name "直近 3 年以内に申請者へ発給された他の scrap metal licence の内容（Schedule 1 para 2(1)）" :document/who :company}
    {:document/id :bank-account :document/name "s.12（現金支払の禁止）の遵守に用いる銀行口座の情報（Schedule 1 para 2(1)）" :document/who :company}
    {:document/id :convictions :document/name "relevant offence の有罪歴・relevant enforcement action の内容（Schedule 1 para 2(1)）" :document/who :officers}
    {:document/id :basic-disclosure :document/name "Basic Disclosure Certificate（申請書に載る各人分。Home Office guidance に基づく自治体の運用要求。Kirklees の実測で発行手数料 £25.00）" :document/who :officers}
    {:document/id :tax-check-code :document/name "HMRC tax check code（9 桁。更新・他自治体での同種免許取得時。gov.uk の Government Gateway で取得）" :document/who :company}
    {:document/id :photo-id :document/name "写真付き身分証明書・住所証明（公共料金請求書や銀行取引明細等）。**council の運用要求**で、法定の申請記載事項ではない（Leeds の実測）" :document/who :officers}
    {:document/id :passport-photo :document/name "パスポート用写真（collector's licence のみ。Buckinghamshire の実測。要否は council ごとに確認）" :document/who :officers}]

   :procedure/steps
   [{:step/id :verify-current-rules :step/order 1 :step/requires-human true
     :step/title "発給する council を特定し、手数料・様式・所要期間・必要書類を確認"
     :step/detail "**この手続きでは step 1 の比重が日本の 2 手続きより重い** —— 手数料も所要期間も必要書類も自治体が決めるので、収録値だけでは申請できない。site の所在地（または mobile collector として活動する区域）から council を特定し、site / collector・新規 / 更新の別に実額を確認する。"
     :step/errand {:kind :verify-authority-info :draft-via :tayori
                   :evidence-schema {:authority :string :verified :map
                                     :source :string :date :iso-date}}}
    {:step/id :choose-licence-type :step/order 2 :step/requires-human false
     :step/title "site licence か collector's licence かを決める（自治体ごとに 1 枚）"
     :step/detail "固定拠点で受け入れるなら site licence、巡回回収なら collector's licence。s.2(9) により同一自治体で併有できないので、両方の実態がある場合は事業形態そのものの整理が先（:legal-questions の :both-modes 参照）。複数自治体にまたがるなら自治体の数だけ申請が要る。"}
    {:step/id :resolve-legal-questions :step/order 3 :step/requires-human true
     :step/title "業態の該当性と法域の整理（英国の solicitor / licensing consultant に相談）"
     :step/detail ":legal-questions を諮る。特に s.21 の『carry on business as a scrap metal dealer』に自社の金属回収が当たるか、England and Wales 以外での営業をどう扱うか。"
     :step/errand {:kind :consult-professional :draft-via :tayori
                   :evidence-schema {:office :string :date :iso-date
                                     :resolutions :map}}}
    {:step/id :obtain-tax-check :step/order 4 :step/requires-human true
     :step/title "HMRC tax check の完了と tax check code の取得（更新・他自治体での同種免許）"
     :step/detail "gov.uk の Government Gateway で完了し 9 桁の code を得る。code を council に渡さないと免許が失効するので、申請書提出より前に済ませる。新規初回は納税義務の確認で足りるかを council に確認する。"}
    {:step/id :obtain-basic-disclosure :step/order 5 :step/requires-human true
     :step/title "Basic Disclosure Certificate の取得（申請書に載る各人分）"
     :step/detail "発行に日数がかかり、council によっては『直近 1 か月以内に発行されたもの』と鮮度を指定する（Buckinghamshire の実測）。**早く取りすぎると失効する**ので、step 1 で鮮度要件を確認してから発注する。"}
    {:step/id :collect-documents :step/order 6 :step/requires-human false
     :step/title "申請書類一式の収集（:procedure/documents のチェックリスト消化）"
     :step/errand {:kind :collect-documents :draft-via nil
                   :evidence-schema {:doc :keyword :obtained-date :iso-date}}}
    {:step/id :appoint-site-manager :step/order 7 :step/requires-human true
     :step/title "各 site の site manager の選任（site licence のみ）"
     :step/detail "記名される individual は s.3(2) の適格性審査の対象になる。選任は人間の決定。"}
    {:step/id :submit :step/order 8 :step/requires-human true
     :step/title "council へ申請書提出と手数料納付"
     :step/detail "提出は human gate。控えと受付番号を台帳に記録する。更新申請は**有効期限前に**出せば、決定（不服申立の結論を含む）が出るまで既存免許が効力を維持する（Schedule 1 para 1(2)）。"}
    {:step/id :respond-to-review :step/order 9 :step/requires-human true
     :step/title "審査対応（追加資料・照会への応答）"
     :step/detail "自治体は s.3(7) により他自治体・Environment Agency・Natural Resources Body for Wales・警察へ照会できる。却下の意向がある場合は Schedule 1 para 7–9 の notice・representations・appeal の手続を経る。"}
    {:step/id :post-grant :step/order 10 :step/requires-human true
     :step/title "取得後の継続義務の実装（掲示・本人確認・非現金決済・記録 3 年）"
     :step/detail "s.10 免許の掲示（site は公衆が見える場所、collector は業務中の車両）／s.11 引渡人の氏名・住所を信頼できる独立した資料で確認してからでないと金属を受け取れない／s.12 譲渡不能小切手か電子資金移動でしか支払えない／s.13 受入時に金属の種類・形状・状態・重量・所有者標記、受入日時、車両登録番号、引渡人の氏名住所、支払者名を記録／s.15(3) これらの記録を受入（または処分）の日から **3 年間**保存。免許は 3 年で失効するので更新申請の起票時期も併せて登録する。"}]

   ;; 結論を出さずに保持する法的論点
   :procedure/legal-questions
   [{:question/id :carry-on-business
     :question/title "自社の金属回収が『carry on business as a scrap metal dealer』に当たるか"
     :question/detail "s.21 は『a business which consists wholly or partly in buying or selling scrap metal』（加工の有無を問わない）と motor salvage operator を捕捉し、**製造業者が副産物としてのみ金属くずを売る場合を除外**する。scrap metal は『any old, waste or discarded metal or metallic material, and any product, article or assembly which is made from or contains metal』で、金・銀および金銀を重量比 2% 以上含む合金は除外。ITAD の PC 回収が『partly in buying or selling scrap metal』に落ちるか、それとも製造業者除外に類する形に整理できるかは業務フロー次第で、結論は現地専門家に諮る。"
     :question/status :open}
    {:question/id :extent-scotland-ni
     :question/title "England and Wales 以外（Scotland・Northern Ireland）での営業"
     :question/detail "Scrap Metal Dealers Act 2013 の extent は England and Wales のみ（s.22 が E+W 指定で local authority を England の district / City of London / London borough と Wales の county / county borough に限定）。Scotland・Northern Ireland に別制度があるかは**未調査**であり、本 procedure はそれらをカバーしない。英国全域で営むなら別途調べる。"
     :question/status :open}
    {:question/id :which-councils
     :question/title "どの council で何枚取るか"
     :question/detail "免許の効力は発給した自治体の区域に限られ（site licence は s.2(3)、collector's licence は s.2(5)）、1 自治体につき 1 枚しか持てない（s.2(9)）。複数自治体にまたがる事業は自治体の数だけ申請・手数料・更新が発生する。手数料が 4 倍以上開く（実測 £181〜£804.78）ため、拠点配置がそのままコストに効く。"
     :question/status :open}
    {:question/id :both-modes
     :question/title "同一自治体で固定拠点と巡回回収の両方を行いたい場合"
     :question/detail "s.2(9) により同一自治体で site licence と collector's licence を併有できない。片方に寄せるか、法人を分けるか、区域をまたぐ形にするか — いずれも事業形態そのものの設計になるので結論を出さずに保持する。"
     :question/status :open}
    {:question/id :environmental-permit
     :question/title "environmental permit / waste carrier registration が別途要るか"
     :question/detail "申請書には s.22(7) の relevant environmental permit / registration の内容を記載するが、Home Office guidance の読みでは**保有していれば開示するという届出事項**であって、保有自体が scrap metal licence の条件ではない。他方 Leeds は『relevant authorisation such as a waste carrier licence or planning permission』の取得を案内しており、廃棄物運搬を行うなら別法の登録が並行して要る可能性がある。scrap metal licence と waste carrier registration の関係は未確認。"
     :question/status :open}
    {:question/id :fee-basis
     :question/title "手数料の実額と算定根拠"
     :question/detail "Schedule 1 para 6(1) で額は自治体が定め、para 6(2) で Secretary of State が Treasury の承認を得て出す guidance を参酌する。Home Office は『recovering certain costs of administering and ensuring compliance with the licensing scheme』と説明する。新規・更新・変更・再交付で別建てになるのが通例（Leeds: 新規 £181 / 更新 £183 / 変更 £44 / 再交付 £44、Buckinghamshire: site 新規 £581 / site 更新 £471 / collector 新規 £354 / collector 更新 £269）。申請先が決まるまで実額は決まらない。"
     :question/status :open}]})
