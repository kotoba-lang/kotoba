(ns okugai.facts
  "屋外広告物の掲出に関する**法域別・媒体別の法令カタログ**。

  ## 各国の法令名を共通語彙にしない

  最初 JP だけで作ったとき、規制 id は `:outdoor-ad-permit` `:road-occupancy`
  `:building-code-88` `:building-code-64` という**日本の法令名**だった。多法域に
  広げるとこれは嘘になる —— 米国に建築基準法88条は無いし、日本に Highway
  Beautification Act は無い。

  そこで層を分けた:

  - **カテゴリ**（`okugai.medium` の `:regulatory-triggers`）は普遍:
    `:display-permit` / `:road-space` / `:structural` / `:highway-corridor`
  - **instrument**（この ns の `regulations`）は法域ごと。同じカテゴリを
    どの法令が担い、閾値がいくつで、誰が許可するかは国ごとに違う

  実測される差の例:
  - JP: 高さ **4m 超**で工作物確認申請（建築基準法88条）
  - DE: **面積 1m² 超**で Baugenehmigung（Werbeanlage は bauliche Anlage）
  - US: Interstate/primary の right-of-way から **660 フィート**以内が連邦の
    実効管理対象（Highway Beautification Act, 23 U.S.C. §131）
  - FR: 2024-01-01 から publicité の police が**市長へ分権**（Climat et Résilience 法）

  ## カバレッジは正直に

  ここに無い法域は spec-basis が **無い**（advisor が創作してよい、ではない）。
  `coverage` は収録法域と、**人口の大きい未収録法域**を名指しで返す —— 「8 法域
  収録」だけ見せると世界を覆っているように読めるため。

  ## 不明を『不要』に倒さない

  高さ・面積・区域が分からなければ `:undetermined`。`okugai.order` は
  `:undetermined` が残る限り許可申請に進めない。"
  (:require [kotoba.lang.text :as str]
            [okugai.medium :as medium]))

(def categories
  "普遍カテゴリ。媒体はこれを trigger として持ち、法域がこれに instrument を割り当てる。"
  #{:display-permit :road-space :structural :highway-corridor})

;; ── 法域ごとの instrument ───────────────────────────────────────────
;;
;; `:reg/category`   どの普遍カテゴリを担うか
;; `:reg/decision`   要否の決まり方
;;                     :always        そのカテゴリに触れる媒体なら常に要る
;;                     :overhang      道路上空・路上に出るなら要る
;;                     :height        `:reg/threshold` の height-m 超で要る
;;                     :area          `:reg/threshold` の area-m2 超で要る
;;                     :zone          `:reg/zone` の区域内なら要る（+ height 併用可）
;;                     :corridor      幹線道路の沿線・区域なら要る
;; `:reg/evidence-key` 提出証跡のキー
(def regulations
  {"JPN"
   {:jp-outdoor-ad-ordinance
    {:reg/category :display-permit :reg/decision :always
     :reg/name "屋外広告物条例に基づく許可"
     :reg/authority "各都道府県・政令指定都市等"
     :reg/legal-basis "屋外広告物法、および同法に基づく各自治体の屋外広告物条例"
     :reg/evidence-key "outdoor-ad-permit-record"
     :reg/note "許可主体は自治体であって国ではない。多くの条例が電柱・街路灯柱への貼り紙・貼り札・広告旗を禁止物件として列挙するが、これは無断の貼付物への規制で、所有者許諾と条例許可を経た掲出物とは別扱い。"
     :reg/source-urls ["https://www.rilg.or.jp/htdocs/img/reiki/057_outdoor_advertising.htm"
                       "https://www.toshiseibi.metro.tokyo.lg.jp/documents/d/toshiseibi/pdf_kenchiku_koukoku_pdf_kou_siori"]}
    :jp-road-occupancy
    {:reg/category :road-space :reg/decision :overhang
     :reg/name "道路占用許可" :reg/authority "道路管理者"
     :reg/legal-basis "道路法第32条"
     :reg/evidence-key "road-occupancy-permit-record"
     :reg/source-urls ["https://www.city.osaka.lg.jp/kensetsu/page/0000372127.html"]}
    :jp-road-use
    {:reg/category :road-space :reg/decision :overhang
     :reg/name "道路使用許可" :reg/authority "所轄警察署"
     :reg/legal-basis "道路交通法"
     :reg/evidence-key "road-use-permit-record"
     :reg/source-urls ["https://www.etic.co.jp/feature/outdoor-advertising-rule/"]}
    :jp-building-code-88
    {:reg/category :structural :reg/decision :height :reg/threshold {:height-m 4.0}
     :reg/name "工作物確認申請（広告塔・広告板）"
     :reg/authority "建築主事／指定確認検査機関"
     :reg/legal-basis "建築基準法第88条第1項（施行令第138条第1項第3号）"
     :reg/evidence-key "building-code-88-record"
     :reg/penalty "確認済証の交付前の着工は違反（1年以下の懲役または100万円以下の罰金）"
     :reg/source-urls ["https://www.city.ota.tokyo.jp/seikatsu/sumaimachinami/kenchiku/tatemono_tyuuikisei/kousakubutsu.html"
                       "https://www.pref.nagano.lg.jp/toshikei/kurashi/sumai/kokoku/documents/takasanosantei.pdf"]}
    :jp-building-code-64
    {:reg/category :structural :reg/decision :zone :reg/zone :fire-prevention-district
     :reg/threshold {:height-m 3.0}
     :reg/name "看板等の防火措置" :reg/authority "建築主事／特定行政庁"
     :reg/legal-basis "建築基準法第64条"
     :reg/evidence-key "building-code-64-record"
     :reg/note "防火地域内で、建築物の屋上に設けるもの、または高さ3m超は主要部分を不燃材料で造るか覆う。"
     :reg/source-urls ["https://www.mori-sign.jp/column/sign-building-code-structure"]}
    :jp-expressway
    {:reg/category :highway-corridor :reg/decision :corridor
     :reg/name "高速道路の区域内／沿道の規制"
     :reg/authority "道路管理者（NEXCO 東日本・中日本・西日本 等）／都道府県"
     :reg/legal-basis "道路法、および都道府県の屋外広告物条例・高速道路等沿道ガイドライン"
     :reg/evidence-key "highway-authority-record"
     :reg/source-urls ["https://www.pref.wakayama.lg.jp/prefg/080900/okugaikoukokubutsujyourei/about_okugaikoukokubutsu_d/fil/kousoku_guideline_1.pdf"
                       "https://www.w-nexco-coms.co.jp/img/common/file/w-nexco-media.pdf"]}}

   "USA"
   {:us-local-zoning
    {:reg/category :display-permit :reg/decision :always
     :reg/name "Local sign permit / zoning approval"
     :reg/authority "City or county zoning / building department"
     :reg/legal-basis "Municipal zoning codes and sign ordinances (state law delegates)"
     :reg/evidence-key "local-sign-permit-record"
     :reg/note "連邦にも州にも全国一律の掲出許可は無い。実務の許可は自治体の zoning/sign ordinance。"
     :reg/source-urls ["https://oaaa.org/policy-advocacy/general-information/laws-regulations/"]}
    :us-state-outdoor-advertising-permit
    {:reg/category :display-permit :reg/decision :corridor
     :reg/name "State DOT outdoor advertising permit"
     :reg/authority "State department of transportation"
     :reg/legal-basis "State outdoor advertising control statutes required by 23 U.S.C. §131"
     :reg/evidence-key "state-dot-outdoor-advertising-permit-record"
     :reg/source-urls ["https://www.fhwa.dot.gov/real_estate/oac/oacprog.cfm"]}
    :us-highway-beautification-act
    {:reg/category :highway-corridor :reg/decision :corridor
     :reg/name "Highway Beautification Act — federal outdoor advertising control"
     :reg/authority "FHWA (via State control agreements)"
     :reg/legal-basis "23 U.S.C. §131; 23 CFR Part 750"
     :reg/threshold {:corridor-distance-ft 660}
     :reg/evidence-key "highway-authority-record"
     :reg/note "Interstate / Federal-aid primary / NHS の right-of-way から 660 フィート以内（都市部外では 660 フィート超でも本線から視認できるもの）が対象。州が effective control を維持しないと連邦道路資金の 10% を失う。commercial/industrial 地域に限って設置を認め、size/lighting/spacing は州と FHWA の協定で決まる。"
     :reg/source-urls ["https://www.law.cornell.edu/uscode/text/23/131"
                       "https://www.ecfr.gov/current/title-23/chapter-I/subchapter-H/part-750"
                       "https://www.fhwa.dot.gov/real_estate/oac/oacprog.cfm"]}
    :us-building-permit
    {:reg/category :structural :reg/decision :height :reg/threshold {:height-m 0.0}
     :reg/name "Building permit / structural review for signs"
     :reg/authority "Local building department"
     :reg/legal-basis "Adopted building codes (IBC Chapter 31 / local amendments)"
     :reg/evidence-key "structural-permit-record"
     :reg/note "閾値は自治体ごとに違うので 0.0（＝高さが分かれば要ると扱う）にしてある。実際の免除規定は自治体条例で確認する。"
     :reg/source-urls ["https://oaaa.org/policy-advocacy/general-information/laws-regulations/"]}}

   "DEU"
   {:de-baugenehmigung
    {:reg/category :display-permit :reg/decision :always
     :reg/name "Baugenehmigung für Werbeanlagen"
     :reg/authority "Untere Bauaufsichtsbehörde（自治体の建築監督官庁）"
     :reg/legal-basis "Landesbauordnung des jeweiligen Bundeslandes（州の建築法）"
     :reg/evidence-key "baugenehmigung-record"
     :reg/note "Werbeanlage は『公共交通空間または公共緑地から視認できる、告知・宣伝・営業表示のための定着した施設』。連邦法ではなく州法なので州ごとに違う。"
     :reg/source-urls ["https://www.service-bw.de/zufi/leistungen/2043"
                       "https://recht.nrw.de/lmi/owa/br_bes_detail?bes_id=4883&anw_nr=2&aufgehoben=J&det_id=417172"]}
    :de-genehmigungsfreiheit
    {:reg/category :structural :reg/decision :area :reg/threshold {:area-m2 1.0}
     :reg/name "Genehmigungspflicht ab 1 m² (Regelfall)"
     :reg/authority "Untere Bauaufsichtsbehörde"
     :reg/legal-basis "Landesbauordnung（多くの州で総面積 1 m² まで genehmigungsfrei）"
     :reg/evidence-key "structural-permit-record"
     :reg/note "**閾値は高さではなく面積**。日本の 4m 超とは別の軸で決まる —— 普遍カテゴリを法令名にしなかった理由そのもの。州ごとに例外あり。"
     :reg/source-urls ["https://www.service-bw.de/zufi/leistungen/2043"]}}

   "FRA"
   {:fr-declaration-prealable
    {:reg/category :display-permit :reg/decision :always
     :reg/name "Déclaration préalable / autorisation préalable de publicité"
     :reg/authority "Maire（2024-01-01 から。それ以前は préfet が原則）"
     :reg/legal-basis "Code de l'environnement L581-1 以下・R581-1 以下"
     :reg/evidence-key "declaration-prealable-record"
     :reg/note "loi Climat et Résilience 第17条により publicité の police が 2024-01-01 に市長へ分権。RLP（règlement local de publicité）があればその地域規則が上乗せ。CERFA 16310*01。"
     :reg/source-urls ["https://www.legifrance.gouv.fr/codes/section_lc/LEGITEXT000006074220/LEGISCTA000006159329/"
                       "https://www.ecologie.gouv.fr/politiques-publiques/reglementation-publicite-exterieure-enseignes-preenseignes"]}}

   "CHN"
   {:cn-outdoor-ad-plan
    {:reg/category :display-permit :reg/decision :always
     :reg/name "户外广告设置规划・管理办法に基づく設置"
     :reg/authority "县级以上地方人民政府（广告监督管理・城市建设・环境保护・公安の各部門が共同で策定）"
     :reg/legal-basis "中华人民共和国广告法"
     :reg/evidence-key "outdoor-ad-permit-record"
     :reg/note "設置禁止が法律で列挙されている: 交通安全設施・交通標識を利用するもの／市政公共設施・交通安全設施・交通標識の使用を妨げるもの／生産や生活を妨げ市容市貌を損なうもの／国家機関・文物保護単位・名勝風景点の建築控制地帯／県級以上の地方政府が禁止した区域。"
     :reg/source-urls ["http://gongbao.court.gov.cn/Details/5e4b747dcdf15e728ae60c3904cdc0.html"
                       "https://faolex.fao.org/docs/pdf/chn204726.pdf"]}
    :cn-content-review
    {:reg/category :display-permit :reg/decision :always
     :reg/name "広告内容の事前審査（特定分野）"
     :reg/authority "有关行政主管部门"
     :reg/legal-basis "中华人民共和国广告法（药品・医疗器械・农药・兽药 等）"
     :reg/evidence-key "content-review-record"
     :reg/note "医薬品・医療機器・農薬・獣医薬等の広告は発布前に内容審査が要る。媒体の形ではなく**広告内容**で決まる規制なので、他法域の構造規制とは別軸。"
     :reg/source-urls ["http://gongbao.court.gov.cn/Details/5e4b747dcdf15e728ae60c3904cdc0.html"]}}

   "IND"
   {:in-municipal-noc
    {:reg/category :display-permit :reg/decision :always
     :reg/name "Municipal advertising licence / NOC"
     :reg/authority "各市自治体（BMC / MCD / BBMP 等）"
     :reg/legal-basis "各 Municipal Corporation Act と市の outdoor advertising policy（例: Mumbai Municipal Corporation Act 1888 + BMC 屋外広告政策）"
     :reg/evidence-key "municipal-advertising-licence-record"
     :reg/note "全国一律の法は無く市ごと。BMC の政策（2024 改訂）は高さ 100 ft 上限、歩道上の設置禁止、国道 right-of-way 上の全面禁止、DOOH の 23 時消灯、国家的重要性のある像から 50m 以内の新設禁止 等。"
     :reg/source-urls ["https://portal.mcgm.gov.in/irj/go/km/docs/documents/HomePage%20Data/Whats%20New/BMC%20Draft%20Policy%20Guidelines%20for%20Display%20of%20Outdoor%20Advertisements%202024.pdf"]}
    :in-structural-stability
    {:reg/category :structural :reg/decision :height :reg/threshold {:height-m 4.6}
     :reg/name "Structural stability certificate"
     :reg/authority "市自治体（登録構造技術者の証明）"
     :reg/legal-basis "市の outdoor advertising policy / building bye-laws"
     :reg/evidence-key "structural-permit-range-record"
     :reg/note "閾値は市ごとに違い、典型は 15 ft 超（≒4.6m）。2024 年の Ghatkopar 事故（17 名死亡）後に規制が強化された。"
     :reg/source-urls ["https://www.shubindiaadworks.com/blog/hoarding-permission-india-rules-regulations-guide"]}
    :in-national-highway
    {:reg/category :highway-corridor :reg/decision :corridor
     :reg/name "National highway right-of-way の掲出制限"
     :reg/authority "NHAI / 道路管理者・市自治体"
     :reg/legal-basis "市の outdoor advertising policy（BMC は国道 right-of-way 上を全面禁止）"
     :reg/evidence-key "highway-authority-record"
     :reg/source-urls ["https://portal.mcgm.gov.in/irj/go/km/docs/documents/HomePage%20Data/Whats%20New/BMC%20Draft%20Policy%20Guidelines%20for%20Display%20of%20Outdoor%20Advertisements%202024.pdf"]}}

   "SAU"
   {:sa-municipal-licence
    {:reg/category :display-permit :reg/decision :always
     :reg/name "Operational licence for an advertising or promotional sign"
     :reg/authority "Ministry of Municipalities and Housing（Balady プラットフォーム経由）"
     :reg/legal-basis "Rules of Regulating Advertisements and Publicity Boards (1991) と、これを更新した MoMaH の広告板規則"
     :reg/evidence-key "municipal-advertising-licence-record"
     :reg/note "Balady の電子サービスで自治体窓口に出向かずに申請できる。ライセンス期間満了時・営業終了時には撤去し原状回復する義務がある。"
     :reg/source-urls ["https://balady.gov.sa/en/services/issuing-operational-license-advertising-or-promotional-sign"
                       "https://momah.gov.sa/en/node/15049"]}
    :sa-media-authority
    {:reg/category :display-permit :reg/decision :always
     :reg/name "広告会社・代理店のライセンス"
     :reg/authority "General Authority for Media Regulation"
     :reg/legal-basis "GAMR の広告事務所・マーケティング事務所・広告代理店ライセンス制度"
     :reg/evidence-key "agency-licence-record"
     :reg/note "掲出物の許可とは別に、**広告を扱う事業者側**のライセンスが要る。媒体社照会の前提条件になる。"
     :reg/source-urls ["https://gmedia.gov.sa/en/services/licensing-of-advertising-offices-marketing-offices-and-advertising-agencies"]}}

   "RUS"
   {:ru-outdoor-ad-permit
    {:reg/category :display-permit :reg/decision :always
     :reg/name "Разрешение на установку и эксплуатацию рекламной конструкции"
     :reg/authority "Орган местного самоуправления（муниципальный район / округ / городской округ）"
     :reg/legal-basis "Федеральный закон от 13.03.2006 N 38-ФЗ «О рекламе», статья 19"
     :reg/evidence-key "outdoor-ad-permit-record"
     :reg/note "設置は自治体の схема размещения рекламных конструкций に沿う必要がある。自治体は掲出位置・外観・技術諸元に関係しない書類を要求できず、許可発行に追加料金も取れない（法19条）。申請は書面または Госуслуги 経由。"
     :reg/source-urls ["https://www.consultant.ru/document/cons_doc_LAW_58968/557f501dd14e1da00da85dd8d8429a8a456bb0f9/"
                       "https://base.garant.ru/12145525/95ef042b11da42ac166eeedeb998f688/"]}
    :ru-state-land-auction
    {:reg/category :display-permit :reg/decision :always
     :reg/name "Договор на установку через торги（аукцион / конкурс）"
     :reg/authority "Собственник государственного или муниципального имущества"
     :reg/legal-basis "38-ФЗ «О рекламе», статья 19"
     :reg/evidence-key "site-owner-consent-record"
     :reg/note "国有・自治体所有の土地/建物に設置する契約は**入札（オークションまたはコンペ）による**。地権者の任意合意では取れない —— 他法域の『地権者 NOC』とは手続きの性質が違う。"
     :reg/source-urls ["https://www.consultant.ru/document/cons_doc_LAW_58968/557f501dd14e1da00da85dd8d8429a8a456bb0f9/"]}}

   "BRA"
   {:br-municipal-licence
    {:reg/category :display-permit :reg/decision :always
     :reg/name "Licença municipal para anúncio / publicidade"
     :reg/authority "Prefeitura（市。連邦法ではない）"
     :reg/legal-basis "市の景観法。São Paulo は Lei nº 14.223/2006「Cidade Limpa」（2007-01-01 施行）"
     :reg/evidence-key "municipal-advertising-licence-record"
     :reg/note "**São Paulo は outdoor（ビルボード）と外壁面の広告塗装を原則禁止した。**公道での brand 広告が許されるのは市の concession を受けた urban furniture 上のみ。指示広告（営業所の自己表示）・行政との提携広告・文化/教育/不動産目的は別カテゴリ。違反は警告→罰金→再犯で倍額→許可取消→撤去。"
     :reg/source-urls ["https://www.prefeitura.sp.gov.br/cidade/secretarias/licenciamento/noticias/?p=309238"
                       "https://drive.prefeitura.sp.gov.br/cidade/secretarias/subprefeituras/upload/pinheiros/arquivos/Cartilha_lei_cidade_limpa.pdf"]}}

   "IDN"
   {:id-reklame-permit
    {:reg/category :display-permit :reg/decision :always
     :reg/name "Izin penyelenggaraan reklame"
     :reg/authority "Pemerintah daerah（DPMPTSP 等）"
     :reg/legal-basis "各地方の Perda。DKI Jakarta は Perda No. 9 Tahun 2014 tentang Penyelenggaraan Reklame"
     :reg/evidence-key "reklame-permit-record"
     :reg/note "許可は地方ごとの Perda で決まるので掲出地の規則を確認する。"
     :reg/source-urls ["https://dpp.jakarta.go.id/berita/mengenal-lebih-dalam-pajak-reklame-menurut-perda-nomor-1-tahun-2024"
                       "https://www.hukumcorner.com/bagaimana-mengurus-izin-pemasangan-iklan-reklame-di-jalan/"]}
    :id-pajak-reklame
    {:reg/category :display-permit :reg/decision :always
     :reg/name "Pajak reklame（広告税）"
     :reg/authority "Pemerintah daerah（地方税）"
     :reg/legal-basis "UU No. 28 Tahun 2009 tentang Pajak Daerah dan Retribusi Daerah + 各地方 Perda"
     :reg/evidence-key "advertising-tax-record"
     :reg/note "**掲出許可とは別に地方税の納付証明が要る。**合法な掲出事業者は許可と納税証明の両方を持つ。中央/地方政府自身の広告、インターネット・TV・ラジオ・新聞等は課税対象外。"
     :reg/source-urls ["https://www.online-pajak.com/tentang-pajak/pajak-reklame/"
                       "https://klikpajak.id/blog/fungsi-dan-penghitungan-pajak-reklame/"]}}

   "MEX"
   {:mx-cdmx-licence
    {:reg/category :display-permit :reg/decision :always
     :reg/name "Licencia / Permiso Administrativo Temporal Revocable de publicidad exterior"
     :reg/authority "SEDUVI（Secretaría de Desarrollo Urbano y Vivienda, CDMX）"
     :reg/legal-basis "Ley de Publicidad Exterior de la Ciudad de México y su Reglamento"
     :reg/evidence-key "advertising-permit-record"
     :reg/note "SEDUVI が licencia・autorización temporal・PATR を発行/取消。**Registro de Publicistas（広告事業者登録）と Catálogo Oficial** があり、掲出は nodos publicitarios / corredores という指定ゾーンに集約される設計。これは CDMX の制度で、他州は別。"
     :reg/source-urls ["https://www.seduvi.cdmx.gob.mx/comunicacion/nota/presenta-seduvi-la-plataforma-digital-de-publicidad-exterior-de-la-ciudad-de-mexico-para-anunciantes-marcas-y-publicistas"
                       "https://www.seduvi.cdmx.gob.mx/storage/app/uploads/public/5c8/1c4/d17/5c81c4d17fe99070894653.pdf"]}}

   "NGA"
   {:ng-lagos-signage-permit
    {:reg/category :display-permit :reg/decision :always
     :reg/name "LASAA signage / advertisement permit"
     :reg/authority "Lagos State Signage and Advertisement Agency (LASAA)"
     :reg/legal-basis "Lagos State Structures for Signage and Advertisement Agency Law, 2006（および改正）"
     :reg/evidence-key "signage-permit-record"
     :reg/note "所定手数料の納付で発行され**毎年更新**。承認後に structure permit number が付与され、掲出物にその番号を表示する義務がある。これは Lagos 州の制度で、他州は別機関。"
     :reg/source-urls ["https://lasaa.lg.gov.ng/"
                       "http://www.lasaa.com/need-permission/apply-for-signage-permit/"
                       "http://www.lasaa.com/regulations/"]}}

   "PAK"
   {:pk-municipal-permit
    {:reg/category :display-permit :reg/decision :always
     :reg/name "自治体／カントンメント委員会の掲出許可"
     :reg/authority "Karachi Metropolitan Corporation・Defence Housing Authority・cantonment boards 等"
     :reg/legal-basis "各自治体・カントンメントの規則、および全国の outdoor advertising policy"
     :reg/evidence-key "municipal-advertising-licence-record"
     :reg/note "⚠ **最高裁が『公有地上の屋外広告ビルボードを許す法は無い』と判示し、Karachi の全ビルボード撤去を命じた**（2016）。公有地上の掲出可否は法的に争いがあるので、この法域では『許可が取れる』を前提に設計しない。政策側は歴史的・環境的に重要な地域と公的機関区域での広告を禁じ、幹線道路・農業・工業地域については構造・安全・間隔の要件を定める。"
     :reg/source-urls ["https://tribune.com.pk/story/1098030/supreme-court-ruling-take-down-all-billboards-by-june-30"
                       "https://www.dawn.com/news/790878"]}}

   "ARE"
   {:ae-dubai-advertising-permit
    {:reg/category :display-permit :reg/decision :always
     :reg/name "Advertising permit (Emirate of Dubai)"
     :reg/authority "Dubai Municipality（RTA・DET が経路により関与）"
     :reg/legal-basis "Decree No. (6) of 2020 Regulating Advertisements in the Emirate of Dubai"
     :reg/evidence-key "advertising-permit-record"
     :reg/note "『何人も、Manual に従って発行された Permit を先に取得することなく、広告媒体を用いて広告スペースに広告を掲出してはならない』。屋外広告は site survey・design specification・地権者 NOC を要する。首長国ごとに別制度（Abu Dhabi は DMT）。"
     :reg/source-urls ["https://dlp.dubai.gov.ae/Legislation%20Reference/2020/Decree%20No.%20(6)%20of%202020%20Regulating%20Advertisements%20in%20the%20Emirate%20of%20Dubai.html"]}}})

(def base-evidence
  "法域に依らず常に要る証跡。規制由来の証跡は `applicable` の結果から導出する。"
  ["site-owner-consent-record" "agency-order-record" "creative-spec-record"])

(def jurisdictions
  {"JPN" {:name "Japan" :permit-level :municipal
          :note "屋外広告物法が枠を与え、実際の許可は自治体条例。"}
   "USA" {:name "United States" :permit-level :municipal-and-state
          :note "連邦に掲出許可は無い。連邦（HBA）は幹線道路沿線の州による実効管理を義務づけるだけで、許可は州 DOT と自治体。"}
   "DEU" {:name "Germany" :permit-level :state-and-municipal
          :note "Werbeanlage は建築物（bauliche Anlage）扱いで州の Landesbauordnung が根拠。EU レベルの掲出許可制度は存在しない。"}
   "FRA" {:name "France" :permit-level :municipal
          :note "Code de l'environnement が全国の枠、RLP が地域規則。2024-01-01 に police が市長へ分権。EU レベルの掲出許可制度は存在しない。"}
   "CHN" {:name "China" :permit-level :municipal
          :note "广告法が禁止事項を法律で列挙し、設置規划と管理办法は県級以上の地方政府が策定。"}
   "IND" {:name "India" :permit-level :municipal
          :note "全国一律の法は無く、市の Municipal Corporation Act と市の広告政策。"}
   "SAU" {:name "Saudi Arabia" :permit-level :national-and-municipal
          :note "MoMaH（Balady）が掲出許可、GAMR が事業者ライセンス。"}
   "ARE" {:name "United Arab Emirates" :permit-level :emirate
          :note "首長国ごとに別制度。ここに収録したのは Dubai のみ。"}
   "RUS" {:name "Russia" :permit-level :municipal
          :note "38-ФЗ が全国の枠、許可は自治体。国有/自治体所有地は入札で契約する。"}
   "BRA" {:name "Brazil" :permit-level :municipal
          :note "連邦法ではなく市の景観法。São Paulo の Cidade Limpa はビルボードを原則禁止。"}
   "IDN" {:name "Indonesia" :permit-level :municipal
          :note "地方の Perda が許可、UU 28/2009 に基づく地方広告税の納付も要る。"}
   "MEX" {:name "Mexico" :permit-level :municipal
          :note "収録は CDMX（SEDUVI）のみ。他州は別制度。"}
   "NGA" {:name "Nigeria" :permit-level :state
          :note "収録は Lagos 州（LASAA）のみ。他州は別機関。"}
   "PAK" {:name "Pakistan" :permit-level :municipal
          :note "公有地上のビルボードは最高裁判断により法的地位が不安定。"}})

;; 未収録のうち人口の大きい法域。「N 法域収録」だけ見せると世界を覆っているように
;; 読めるので、名指しで残す。人口は World Bank 2024（SP.POP.TOTL）。
(def uncovered-large-jurisdictions
  {:source-url "https://data.worldbank.org/indicator/SP.POP.TOTL"
   :as-of "2024"
   ;; 2026-08-04: IDN PAK NGA BRA RUS MEX を収録したのでここから外した。
   ;; 残る 3 件は**一次情報の出典が取れなかった** —— 「調べたが見つからなかった」
   ;; であって「規制が無い」ではない。推測で書くくらいなら未収録のまま残す。
   :entries [{:iso3 "BGD" :name "Bangladesh" :population 173000000
              :why "Dhaka City Corporation の屋外広告規則について一次情報に到達できず"}
             {:iso3 "ETH" :name "Ethiopia" :population 130000000
              :why "Addis Ababa の屋外広告規則について一次情報に到達できず"}
             {:iso3 "EGY" :name "Egypt" :population 116000000
              :why "Cairo Governorate の掲出許可手続について一次情報に到達できず"}]})

(def alpha2->iso3
  "収録法域の alpha-2 → alpha-3。survey の area は ISO 3166-2（\"JP-13\" \"US-NY\"）で
  宣言されるが法令カタログは alpha-3 キーなので、この 1 枚だけ明示的に持つ。
  **収録法域だけ**を載せる —— 未収録国の alpha-2 をここに足すと、法令が無いのに
  法域が解決できてしまう。"
  {"JP" "JPN" "US" "USA" "DE" "DEU" "FR" "FRA" "CN" "CHN" "IN" "IND"
   "SA" "SAU" "AE" "ARE" "RU" "RUS" "BR" "BRA" "ID" "IDN" "MX" "MEX"
   "NG" "NGA" "PK" "PAK"})

(defn iso3-of
  "\"JPN\" / \"JP-13\" / \"JP\" → \"JPN\"。解決できなければ nil（推測しない）。"
  [code]
  (when (string? code)
    (cond
      (contains? regulations code) code
      (contains? alpha2->iso3 code) (get alpha2->iso3 code)
      (and (> (count code) 2) (= \- (nth code 2)))
      (get alpha2->iso3 (subs code 0 2))
      :else nil)))

(defn requirements [iso3] (get jurisdictions (iso3-of iso3)))
(defn covered? [iso3] (contains? regulations (iso3-of iso3)))
(defn regulations-for [iso3] (get regulations (iso3-of iso3) {}))
(defn describe-regulation
  ([id] (some (fn [[_ regs]] (get regs id)) regulations))
  ([iso3 id] (get-in regulations [(iso3-of iso3) id])))

(defn coverage []
  (let [covered (vec (sort (keys regulations)))]
    {:jurisdictions covered
     :count (count covered)
     :regulations (reduce + (map count (vals regulations)))
     :uncovered-large (mapv (fn [e] (str (:iso3 e) " (" (:name e) ", "
                                         (quot (:population e) 1000000) "M)"))
                            (:entries uncovered-large-jurisdictions))
     :note (str "収録 " (count covered) " 法域 / "
                (reduce + (map count (vals regulations))) " instrument。"
                "未収録の法域は spec-basis 無し —— advisor は要件を創作してはならず、"
                "governor は掲出提案を保留する。人口 1 億超で未収録の法域が "
                (count (:entries uncovered-large-jurisdictions))
                " ある（IDN/PAK/NGA/BRA/BGD/RUS/MEX/ETH/EGY）。"
                "**EU レベルの掲出許可制度は存在しない** —— DEU/FRA は加盟国法として収録した。")}))

;; ── 実際に効くかの判定 ──────────────────────────────────────────────

(defn- decide-one
  "1 instrument の要否。`:yes` / `:no` / `:unknown`。"
  [{:keys [reg/decision reg/threshold reg/zone]}
   {:keys [height-m area-m2 overhangs-road? highway-adjacent? highway-facility?
           special-zones]}]
  (case decision
    :always :yes

    :overhang (cond (nil? overhangs-road?) :unknown
                    overhangs-road? :yes
                    :else :no)

    :height (cond (nil? height-m) :unknown
                  (> height-m (:height-m threshold 0.0)) :yes
                  :else :no)

    :area (cond (nil? area-m2) :unknown
                (> area-m2 (:area-m2 threshold 0.0)) :yes
                :else :no)

    ;; 区域 + 高さの複合（JP 64 条: 防火地域内で屋上、または高さ3m超）
    :zone (cond (nil? special-zones) :unknown
                (not (contains? special-zones zone)) :no
                (nil? height-m) :unknown
                (> height-m (:height-m threshold 0.0)) :yes
                :else :no)

    :corridor (cond highway-facility? :yes
                    (nil? highway-adjacent?) :unknown
                    highway-adjacent? :yes
                    :else :no)

    :unknown))

(defn applicable
  "この掲出が法域 `iso3` で実際に受ける規制。

  `{:medium :billboard :height-m 5.2 :area-m2 12.0 :overhangs-road? false
    :highway-adjacent? false :special-zones #{:fire-prevention-district}}`

  戻り値は `{:required #{...} :undetermined #{...} :not-applicable #{...}}`
  （要素は instrument id）。法域が未収録なら `:no-spec-basis`。

  **寸法・面積・区域が不明なら `:undetermined`** —— 不明を『不要』に倒すと、
  確認申請なしで着工する提案が governor を通ってしまう。"
  [iso3 {:keys [medium] :as placement}]
  (if-not (covered? iso3)
    :no-spec-basis
    (let [trig (medium/triggers medium)
          regs (regulations-for iso3)
          relevant (filter (fn [[_ r]] (contains? trig (:reg/category r))) regs)]
      (reduce (fn [acc [id r]]
                (case (decide-one r placement)
                  :yes (update acc :required conj id)
                  :unknown (update acc :undetermined conj id)
                  :no (update acc :not-applicable conj id)))
              {:required #{} :undetermined #{} :not-applicable #{}}
              (sort-by key relevant)))))

(defn undetermined?
  "判定できない instrument が残っているか。法域が未収録なら true（＝進めない）。"
  [iso3 placement]
  (let [a (applicable iso3 placement)]
    (or (= a :no-spec-basis) (boolean (seq (:undetermined a))))))

(defn required-evidence
  "この掲出に実際に要る証跡キー。基本証跡 + **実際に効く／要否未確定の**
  instrument の証跡。法域が未収録なら `:no-spec-basis`。

  `:undetermined` な instrument の証跡も要求する —— 要否が決まっていないものを
  『不要だから証跡も不要』にすると、許可なしで進む提案が通ってしまう。"
  [iso3 placement]
  (let [a (applicable iso3 placement)]
    (if (= a :no-spec-basis)
      :no-spec-basis
      (let [regs (regulations-for iso3)
            ids (into (:required a) (:undetermined a))]
        (vec (distinct (concat base-evidence
                               (keep #(:reg/evidence-key (get regs %)) (sort ids)))))))))

(defn missing-evidence
  "持つべき証跡のうち、まだ無いもの。法域が未収録なら `:no-spec-basis`。"
  [iso3 placement provided-evidence-keys]
  (let [need (required-evidence iso3 placement)]
    (if (= :no-spec-basis need)
      :no-spec-basis
      (vec (remove (set (map str provided-evidence-keys)) need)))))

(defn summary
  "監査ログ用の一行。"
  [iso3 placement]
  (let [a (applicable iso3 placement)]
    (if (= a :no-spec-basis)
      (str iso3 " → spec-basis 無し（未収録法域）")
      (str iso3 " → 要 " (str/join "," (map name (sort (:required a))))
           (when (seq (:undetermined a))
             (str " / 未確定 " (str/join "," (map name (sort (:undetermined a))))))))))
