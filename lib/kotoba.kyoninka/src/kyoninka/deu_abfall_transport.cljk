(ns kyoninka.deu-abfall-transport
  "ドイツの廃棄物の収集・運搬・取引・仲介（Sammeln / Befördern / Handeln / Makeln）の
  開業手続き data。連邦法テンプレート。ADR-2607141620。

  ## 日本の2本と構造が違う点（ここを取り違えると全部ずれる）

  1. **二段構造の分岐軸が『危険廃棄物かどうか』。** 日本は収集運搬と処分で分けるが、
     ドイツは扱う廃棄物が gefährlich か否かで **§53 の Anzeige（届出）** と
     **§54 の Erlaubnis（許可）** に分かれる。だから step 1 は書類集めでも窓口確認でも
     なく、**AVV による廃棄物分類の確定**である。
  2. **名宛人が広い。** Sammler・Beförderer だけでなく **Händler（取引）と Makler（仲介）**
     も対象。自ら 1 メートルも運ばず取り次ぐだけの ops 層がそのまま規制対象に入りうる。
  3. **法域は連邦、窓口は州。** KrWG / AbfAEV は連邦法だが、所管は
     『申請者が Hauptsitz を置く州の当局』（KrWG §53 Abs.1 S.3 / §54 Abs.1 S.3）。
     手数料は州の Gebührenordnung で決まり、州ごとに違う。
  4. **許可は全国有効・無期限が既定。** §54 Abs.1 S.4 で連邦全域に効く。日本の
     収集運搬業許可が積み下ろしの都道府県ごとに要るのと正反対。
  5. **沈黙が許可になる。** 完全な申請の到達から 3 か月で Genehmigungsfiktion が働き、
     当局が動かなくても許可されたものとみなされる（§54 Abs.6 S.2 KrWG i.V.m.
     §42a VwVfG、AbfAEV §10 Abs.1 Nr.3）。日本の『標準処理期間』は目安にすぎず
     沈黙は不許可でも許可でもない —— **別種の法的対象**なので同じ枠に入れない。

  ## `kyoninka.schema` を require していない理由

  既存 2 本（sanpai / kobutsu）は `:procedure/fee` と
  `:procedure/standard-period-days` に `schema/unverified` を付けている。
  この手続きは**その 2 つをどちらも収録していない**ので、`schema/unverified` を
  呼ぶ箇所が無い。

  - **手数料**: 連邦法は金額を定めない。全国値が存在しないので `:amount` は
    書けない（`:set-by :level` が `:sub-national`）。**16 州すべてを実測した
    結果は `:procedure/fee-observations` にある**（2026-08-07、37 観測）。

    以前ここには「州の Gebührenordnung が定め、しかも定額でなく**幅**で示される」
    と書いていた。**16 州を数えたらこれは 11 州にしか当たらなかった。**
    実際には 5 つの形がある —— 幅（11 州）／下限のみ上限なし（NI ≥160 €、
    HH ≥371 €）／上限のみ下限なし（MV ≤5.500 €）／**額の定めが一切なし**
    （NRW は純粋な時間手数料）／定額（HE 電子 800 € 紙 1.000 €、16 州で唯一）。
    幅を既定の形として型に焼かなかったのはこのため。

    以前記録していた 3 州の値のうち **2 件に誤りがあった**: Niedersachsen の
    「AllGO 2.1.35 で平均 ca. 360 €」は数値としては実在するが**法的性格が違う**
    —— 条文は「時間費用、ただし最低 160 €」で、360 € は所管庁 Merkblatt の
    運用平均。Hamburg の「50–1,000 €」は §54 の値として裏付けが取れなかった
    （確認できたのは UmwGebO の最低 371 €）。前者は `:source-kind` が
    `:instrument` と `:practice` を分けることで両方保持している。

    **州ごとの値の散らばりは幅ではない。** 11 州の法定幅を通覧すると下限 57–375 €、
    上限 1.000–10.000 € に散らばるが、`57–10.000 €` のような合成値はどの州の
    規則にも存在しないので作らない。同じ誤りは州内でも起きており、Sachsen では
    一部の Landkreis ページが別々の Tarifstelle の下限と上限を跨いで
    「100–6.000 €」と表示する（条文上そのような項目は無い）。

    **§53 届出が「多くの州で無料」というのは誤りだった。** 無条件に無料なのは
    Bremen 1 州のみで、13 州は有料。条件付き無料の 2 州（HE / NI）も、無料は
    §53 という手続にではなく**電子経路に**付いている（HE の条文は
    「elektronischen Anzeige …wird keine Gebühr erhoben」で紙は 50 €）。
    それが `:fee-observation/channel` を持つ理由。
  - **標準処理期間**: ドイツにこの概念は無い。あるのは上記 3 か月の
    Genehmigungsfiktion で、これは『たいていこれくらいで返ってくる』ではなく
    『これを過ぎたら許可されたことになる』という別の法的効果。しかも法文の単位は
    暦月（『drei Monate』）であって日ではなく、日数への換算値はどの出典にも無い。
    → **省いた。** 3 か月という事実は `:submit` / `:respond-to-review` step の
    `:step/detail` に、起算点と非 EU/EEA 申請者への不適用（AbfAEV §10 Abs.8）
    ごと保持する。

  収録した値はすべて 2026-08-07 に一次資料（gesetze-im-internet.de の
  KrWG / AbfAEV / AVV / VwVfG、および州所管庁の公式ページ・Merkblatt）で確認した。
  裏の取れなかった値は書いていない。"
  (:require [kyoninka.schema :as schema]))

(def procedure
  {:procedure/id :deu-abfall-transport
   :procedure/name "廃棄物の収集・運搬・取引・仲介の開業手続（ドイツ連邦・KrWG §53 届出／§54 許可の二段）"
   :procedure/law "Kreislaufwirtschaftsgesetz (KrWG) 第53条第1項（Anzeige）／第54条第1項（gefährliche Abfälle の Erlaubnis）。手続の細則は Anzeige- und Erlaubnisverordnung (AbfAEV)、危険性の判定は Abfallverzeichnis-Verordnung (AVV)（KrWG 第3条第5項 → 第48条）"
   ;; **法域は連邦。** KrWG / AbfAEV / AVV はいずれも連邦法で、州法ではない。
   ;; 州が持つのは所管（どの官庁が処理するか）と手数料。混ぜない。
   :procedure/jurisdiction "DEU"
   ;; **範囲は連邦全域。GBR の 2 本とは理由が逆。** England / England and Wales は
   ;; 法自体が devolve していて範囲が国より狭いのに対し、ドイツは範囲が国と一致する
   ;; —— KrWG §54 Abs.1 S.4「Die Erlaubnis nach Satz 1 gilt für die Bundesrepublik
   ;; Deutschland.」で明文化されている。
   ;;
   ;; 省略しても schema 上は「法域全域」を意味するが、**省略は『確認した』と
   ;; 『考えていない』を区別できない**ので明示する。州が決めるのは所管官庁と
   ;; 手数料だけで、適用範囲ではない —— そこに州名を書くと『ドイツの一部にしか
   ;; 効かない法律』という別の主張になる。州差は下の :land-* が持つ。
   :procedure/extent "Deutschland (Bund)"
   ;; **額を決めるのは連邦ではなく州。** 全国値が存在しないので :amount は無い。
   ;; 通貨と最小単位は観測が共有する（州が変わっても EUR）。
   :procedure/fee {:currency "EUR"
                   :minor-unit 100
                   :kind :landesrechtliche-verwaltungsgebuehr
                   :set-by {:level :sub-national
                            :body "各州（Land）の Gebühren-/Kostenordnung。NRW と Sachsen では Kreis / kreisfreie Stadt が執行するため州の規範の下にさらに散らばりが生じる"
                            :basis "KrWG は手数料額を定めない。VwKostG 系の州法と各州の Gebührenordnung が定める（AbfAEV §7〜§11 の手続に対応）"}
                   :verify (schema/unverified "額は州ごとに異なり、しかも 5 つの異なる形（幅 / 下限のみ / 上限のみ / 定めなし / 定額）をとる。申請先の州の Gebührenordnung で実額を確認する。16 州の実測は :procedure/fee-observations にあるが、**その min/max は法定の幅ではない** —— 州ごとの散らばりは 16 個の別々の法規範であって 1 つの幅ではない")}

   ;; 16 州・37 観測（2026-08-07）。**subagent 2 本を独立に走らせ、食い違いを潰した。**
   ;; 最も重い対立は Hessen で、1 本目が条文 PDF から定額 800/1.000 € を引用し、
   ;; 2 本目が「同じ PDF に KrWG §§53/54 の項目は無い」と報告した。
   ;; **推測で採らず条文 PDF を自分で取得して確かめた** —— Nr. 181301/181302/18128 は
   ;; 実在し、1 本目が正しかった。2 本目が外したのは、項目本文が KrWG ではなく
   ;; AbfAEV §9/§11 を引いているため。自分で読んだおかげで、どちらの調査にも
   ;; 無かった Nr. 181303（変更 250 €）も見つかった。
   ;;
   ;; **出所の質は州で違う。** 条例本文の行項目まで辿れたのは 11 州、
   ;; 所管庁の公式表明どまりが 5 州（BE / HH / HB / ST / TH）。とくに Thüringen は
   ;; ThürVwKostOMUEN に §§53/54 の項目自体が無く、条例が 2012 年の KrWG 施行に
   ;; 追随していない（旧法の Transportgenehmigung のまま）。この差を
   ;; `:fee-observation/source-kind` が持つ —— **どちらも「公式」だが同格ではない。**
   :procedure/fee-observations
   [{:fee-observation/id "deu-abfall-ni-erlaubnis-floor"
     :fee-observation/procedure :deu-abfall-transport
     :fee-observation/authority "Niedersachsen"
     :fee-observation/licence-type :erlaubnis
     :fee-observation/stage :new
     :fee-observation/channel :any
     :fee-observation/rule-form :floor
     :fee-observation/range-min 16000
     :fee-observation/source-kind :instrument
     :fee-observation/basis "AllGO Kostentarif Nr. 2.1.35（時間費用、ただし最低 160 €）"
     :fee-observation/as-of "2026-08-07"
     :fee-observation/source-url "https://www.mf.niedersachsen.de/download/1822/Allgemeine_Gebuehrenordnung_AllGO_.pdf"
     :fee-observation/note "**上限は条文に無い**（höchstens の定めが 2.1.35 に存在しない）。定額でも幅でもなく、上限なしの時間手数料。AllGO は 2025-12-16 改正版"}
    {:fee-observation/id "deu-abfall-ni-erlaubnis-practice"
     :fee-observation/procedure :deu-abfall-transport
     :fee-observation/authority "Niedersachsen"
     :fee-observation/licence-type :erlaubnis
     :fee-observation/stage :new
     :fee-observation/channel :any
     :fee-observation/rule-form :fixed
     :fee-observation/amount 36000
     :fee-observation/approximate? true
     :fee-observation/source-kind :practice
     :fee-observation/basis "所管庁 Merkblatt（Staatliches Gewerbeaufsichtsamt Hildesheim、Stand 05/2026）の運用平均"
     :fee-observation/as-of "2026-08-07"
     :fee-observation/source-url "https://www.gewerbeaufsicht.niedersachsen.de/download/89281/Merkblatt_Erlaubnis_Stand_05_2026.pdf"
     :fee-observation/note "**この library が以前『AllGO 2.1.35 で平均 ca. 360 €』と記録していた値。数値は正しいが法的性格の記述が誤っていた** —— 原文は durchschnittlich ca.（平均・約）で、条文には一切現れない。上の法定最低額 160 € と混同しないこと"}
    {:fee-observation/id "deu-abfall-ni-anzeige-floor"
     :fee-observation/procedure :deu-abfall-transport
     :fee-observation/authority "Niedersachsen"
     :fee-observation/licence-type :anzeige
     :fee-observation/stage :new
     :fee-observation/channel :paper
     :fee-observation/rule-form :floor
     :fee-observation/range-min 6700
     :fee-observation/source-kind :instrument
     :fee-observation/basis "AllGO Kostentarif Nr. 2.1.32.1 / 2.1.32.2（時間費用、ただし最低 67 €）"
     :fee-observation/as-of "2026-08-07"
     :fee-observation/source-url "https://www.mf.niedersachsen.de/download/1822/Allgemeine_Gebuehrenordnung_AllGO_.pdf"
     :fee-observation/note "2.1.32 の Anmerkung により、届出が完全かつ AbfAEV §8 の電子手続で提出された場合は徴収しない。紙・不完全なら最低 67 €"}
    {:fee-observation/id "deu-abfall-be-erlaubnis"
     :fee-observation/procedure :deu-abfall-transport
     :fee-observation/authority "Berlin"
     :fee-observation/licence-type :erlaubnis
     :fee-observation/stage :new
     :fee-observation/channel :any
     :fee-observation/rule-form :range
     :fee-observation/range-min 25000
     :fee-observation/range-max 500000
     :fee-observation/source-kind :authority-guidance
     :fee-observation/basis "UGebO Tarifstelle 3013a (1)（Beförderungserlaubnis の交付決定）"
     :fee-observation/as-of "2026-08-07"
     :fee-observation/source-url "https://service.berlin.de/dienstleistung/326690/"
     :fee-observation/note "新規交付のみ。重要事項変更後の決定と、申請により内容/期間を限定した許可は別枠でともに 50–5.000 €。**所管 SBB mbH は Berlin と Brandenburg をまとめて 100–5.000 € と表示するが、その 100 は Brandenburg 側の下限**。条文原文（gesetze.berlin.de）は JS 依存で取得できず、Tarifstelle 表記は SBB の引用に依拠。幅の中の額は廃棄物種類数で決まる（SBB 段階表: 20 種まで 500 €、50 種まで 1.000 €、全種 2.500 €、消費税別）—— **同じ幅を持つ 2 州が体系的に別の額を出しうる**"}
    {:fee-observation/id "deu-abfall-be-anzeige"
     :fee-observation/procedure :deu-abfall-transport
     :fee-observation/authority "Berlin"
     :fee-observation/licence-type :anzeige
     :fee-observation/stage :new
     :fee-observation/channel :any
     :fee-observation/rule-form :range
     :fee-observation/range-min 5000
     :fee-observation/range-max 50000
     :fee-observation/source-kind :authority-guidance
     :fee-observation/basis "UGebO Tarifstelle 3013b (1)（KrWG §53 の届出処理）"
     :fee-observation/as-of "2026-08-07"
     :fee-observation/source-url "https://www.sbb-mbh.de/de/aufgaben-der-sbb/anzeigen-53-krwg/gebuehren-der-anzeige/"
     :fee-observation/note "**無料ではない。** SBB の運用内訳は標準 75 € / 増 150 € / 高 225 € / 最大 500 €（いずれも消費税別）"}
    {:fee-observation/id "deu-abfall-bb-erlaubnis"
     :fee-observation/procedure :deu-abfall-transport
     :fee-observation/authority "Brandenburg"
     :fee-observation/licence-type :erlaubnis
     :fee-observation/stage :grant-or-change
     :fee-observation/channel :any
     :fee-observation/rule-form :range
     :fee-observation/range-min 10000
     :fee-observation/range-max 500000
     :fee-observation/source-kind :instrument
     :fee-observation/basis "GebOUmwelt (GebOMUGV) Tarifstelle 3.1.21.1"
     :fee-observation/as-of "2026-08-07"
     :fee-observation/source-url "https://bravors.brandenburg.de/verordnungen/gebomugv"
     :fee-observation/note "交付と変更が同一 Tarifstelle に同居しているので、額を新規のものとして単独で引用できない。最終改正 2025-04-15"}
    {:fee-observation/id "deu-abfall-bb-anzeige"
     :fee-observation/procedure :deu-abfall-transport
     :fee-observation/authority "Brandenburg"
     :fee-observation/licence-type :anzeige
     :fee-observation/stage :new
     :fee-observation/channel :any
     :fee-observation/rule-form :range
     :fee-observation/range-min 5000
     :fee-observation/range-max 50000
     :fee-observation/source-kind :instrument
     :fee-observation/basis "GebOUmwelt (GebOMUGV) Tarifstelle 3.1.20.1"
     :fee-observation/as-of "2026-08-07"
     :fee-observation/source-url "https://bravors.brandenburg.de/verordnungen/gebomugv"
     :fee-observation/note "無料ではない"}
    {:fee-observation/id "deu-abfall-hh-erlaubnis-floor"
     :fee-observation/procedure :deu-abfall-transport
     :fee-observation/authority "Hamburg"
     :fee-observation/licence-type :erlaubnis
     :fee-observation/stage :new
     :fee-observation/channel :any
     :fee-observation/rule-form :floor
     :fee-observation/range-min 37100
     :fee-observation/source-kind :authority-guidance
     :fee-observation/basis "UmwGebO, Anlage 1 Verwaltungsgebühren（最低 371 €。特別な処理負担があれば増額）"
     :fee-observation/as-of "2026-08-07"
     :fee-observation/source-url "https://www.hamburg.de/politik-und-verwaltung/behoerden/bukea/themen/abfall-entsorgung/sammler-befoerderer-haendler-makler/abfallbefoerderung-erlaubnis-krwg-159504"
     :fee-observation/note "**上限なしの下限であって幅ではない。** 以前この library が併記していた『50–1.000 €』は §54 の値として裏付けが取れなかった"}
    {:fee-observation/id "deu-abfall-hh-anzeige-floor"
     :fee-observation/procedure :deu-abfall-transport
     :fee-observation/authority "Hamburg"
     :fee-observation/licence-type :anzeige
     :fee-observation/stage :new
     :fee-observation/channel :any
     :fee-observation/rule-form :floor
     :fee-observation/range-min 10600
     :fee-observation/source-kind :authority-guidance
     :fee-observation/basis "UmwGebO, Anlage 1（in der Regel ab 106 €）"
     :fee-observation/as-of "2026-08-07"
     :fee-observation/source-url "https://www.hamburg.de/politik-und-verwaltung/behoerden/bukea/themen/abfall-entsorgung/sammler-befoerderer-haendler-makler/anzeigeverfahren-53-krwg-159494"
     :fee-observation/note "無料ではない"}
    {:fee-observation/id "deu-abfall-nw-erlaubnis-none"
     :fee-observation/procedure :deu-abfall-transport
     :fee-observation/authority "Nordrhein-Westfalen"
     :fee-observation/licence-type :erlaubnis
     :fee-observation/stage :new
     :fee-observation/channel :any
     :fee-observation/rule-form :no-amount-set
     :fee-observation/source-kind :instrument
     :fee-observation/basis "AVwGebO NRW Tarifstelle 4.4.1.26.1（je nach Zeitaufwand nach Tarifstelle 4.1.1.1）"
     :fee-observation/as-of "2026-08-07"
     :fee-observation/source-url "https://recht.nrw.de/system/files/2026-04/agt_tarifstelle-04_stand-25.04.2026.pdf"
     :fee-observation/note "**州法は額を一切定めていない**（定額も幅も無い）。純粋な時間手数料で、Dienstleistungsrichtlinie 2006/123/EG により実費上限に縛られる旨を条文が明記。時間単価は Richtwerte-Erlass（2026-02-14, MB.NRW Nr. 45）の推奨値 LG2.2 87,95 €/h 〜 LG1.1 54,00 €/h。個々の Kreis のページに出る『500–1.000 €』等は自治体の実務値であって州法の幅ではない"}
    {:fee-observation/id "deu-abfall-nw-anzeige-none"
     :fee-observation/procedure :deu-abfall-transport
     :fee-observation/authority "Nordrhein-Westfalen"
     :fee-observation/licence-type :anzeige
     :fee-observation/stage :new
     :fee-observation/channel :any
     :fee-observation/rule-form :no-amount-set
     :fee-observation/source-kind :instrument
     :fee-observation/basis "AVwGebO NRW Tarifstelle 4.4.1.25（je nach Zeitaufwand）"
     :fee-observation/as-of "2026-08-07"
     :fee-observation/source-url "https://recht.nrw.de/system/files/2026-04/agt_tarifstelle-04_stand-25.04.2026.pdf"
     :fee-observation/note "無料ではない。§54 と同じく額の定めが無い"}
    {:fee-observation/id "deu-abfall-by-erlaubnis"
     :fee-observation/procedure :deu-abfall-transport
     :fee-observation/authority "Bayern"
     :fee-observation/licence-type :erlaubnis
     :fee-observation/stage :new
     :fee-observation/channel :any
     :fee-observation/rule-form :range
     :fee-observation/range-min 25000
     :fee-observation/range-max 600000
     :fee-observation/source-kind :instrument
     :fee-observation/basis "Kostenverzeichnis (KVz) Tarif-Nr. 8.I.0/35"
     :fee-observation/as-of "2026-08-07"
     :fee-observation/source-url "https://www.gesetze-bayern.de/Content/Pdf/BayKVzKG?all=True"
     :fee-observation/note "KVz は 2026-06-15 改正版。16 州で最も高い上限のひとつ"}
    {:fee-observation/id "deu-abfall-by-anzeige"
     :fee-observation/procedure :deu-abfall-transport
     :fee-observation/authority "Bayern"
     :fee-observation/licence-type :anzeige
     :fee-observation/stage :new
     :fee-observation/channel :any
     :fee-observation/rule-form :range
     :fee-observation/range-min 2500
     :fee-observation/range-max 10000
     :fee-observation/source-kind :instrument
     :fee-observation/basis "KVz Tarif-Nr. 8.I.0/34.2"
     :fee-observation/as-of "2026-08-07"
     :fee-observation/source-url "https://www.gesetze-bayern.de/Content/Pdf/BayKVzKG?all=True"
     :fee-observation/note "**無料ではない。** §53 Abs.3 の措置を要する場合は別枠（34.1）で 150–3.000 €。同じ KVz が隣接項目 8.I.0/32 を明示的に kostenfrei と書いており、無料にする意図があれば明記する体裁 —— §53 にその印は無い"}
    {:fee-observation/id "deu-abfall-bw-erlaubnis"
     :fee-observation/procedure :deu-abfall-transport
     :fee-observation/authority "Baden-Württemberg"
     :fee-observation/licence-type :erlaubnis
     :fee-observation/stage :new
     :fee-observation/channel :any
     :fee-observation/rule-form :range
     :fee-observation/range-min 25000
     :fee-observation/range-max 500000
     :fee-observation/source-kind :instrument
     :fee-observation/basis "GebVerz UM Nummer 1.1.23"
     :fee-observation/as-of "2026-08-07"
     :fee-observation/source-url "https://gewerbeaufsicht.baden-wuerttemberg.de/documents/20121/67096/2_2_3.pdf"
     :fee-observation/note "**州全域に一律ではない。** GebVO UM §1 Abs.1 がこの手数料表から Landratsämter を明示的に除外しており、BW で §54 許可を出すのは多くが Landratsamt（untere Abfallrechtsbehörde）で郡独自の条例が適用される。GebVO UM §2 により消費税別"}
    {:fee-observation/id "deu-abfall-bw-anzeige"
     :fee-observation/procedure :deu-abfall-transport
     :fee-observation/authority "Baden-Württemberg"
     :fee-observation/licence-type :anzeige
     :fee-observation/stage :new
     :fee-observation/channel :any
     :fee-observation/rule-form :range
     :fee-observation/range-min 15000
     :fee-observation/range-max 500000
     :fee-observation/source-kind :instrument
     :fee-observation/basis "GebVerz UM Nummer 1.1.22"
     :fee-observation/as-of "2026-08-07"
     :fee-observation/source-url "https://gewerbeaufsicht.baden-wuerttemberg.de/documents/20121/67096/2_2_3.pdf"
     :fee-observation/note "無料ではない。届出の上限が許可と同じ 5.000 € で、16 州で最も高い §53 の上限"}
    {:fee-observation/id "deu-abfall-he-erlaubnis-elektronisch"
     :fee-observation/procedure :deu-abfall-transport
     :fee-observation/authority "Hessen"
     :fee-observation/licence-type :erlaubnis
     :fee-observation/stage :new
     :fee-observation/channel :electronic
     :fee-observation/rule-form :fixed
     :fee-observation/amount 80000
     :fee-observation/source-kind :instrument
     :fee-observation/basis "VwKostO（Geschäftsbereich Umwelt）Verwaltungskostenverzeichnis Nr. 181301"
     :fee-observation/as-of "2026-08-07"
     :fee-observation/source-url "https://verkuendung.hessen.de/sites/verkuendung.hessen.de/files/veroeffentlichungsplattform_plugin/published/782/GVBl_2025_Nr_11_Regelungstext.pdf"
     :fee-observation/note "**16 州で唯一の Festgebühr（定額）。** GVBl 2025 Nr. 11（2025-02-18 公布）。⚠ 2 回目の独立調査が『この PDF に KrWG §§53/54 の項目は無い』と報告したため、**条文 PDF を自分で取得して確かめた**（2026-08-07）—— Nr. 181301 は実在し、親項目は §54 Abs.1 S.1 / Abs.2 を引いている。2 回目が外したのは、項目本文が KrWG ではなく AbfAEV §9/§11 を引いているため"}
    {:fee-observation/id "deu-abfall-he-erlaubnis-papier"
     :fee-observation/procedure :deu-abfall-transport
     :fee-observation/authority "Hessen"
     :fee-observation/licence-type :erlaubnis
     :fee-observation/stage :new
     :fee-observation/channel :paper
     :fee-observation/rule-form :fixed
     :fee-observation/amount 100000
     :fee-observation/source-kind :instrument
     :fee-observation/basis "VwKostO Nr. 181302（nicht elektronisch beantragt）"
     :fee-observation/as-of "2026-08-07"
     :fee-observation/source-url "https://verkuendung.hessen.de/sites/verkuendung.hessen.de/files/veroeffentlichungsplattform_plugin/published/782/GVBl_2025_Nr_11_Regelungstext.pdf"
     :fee-observation/note "電子申請との差 200 € が電子化のインセンティブ。条文 PDF を自分で読んで確認"}
    {:fee-observation/id "deu-abfall-he-anzeige-elektronisch"
     :fee-observation/procedure :deu-abfall-transport
     :fee-observation/authority "Hessen"
     :fee-observation/licence-type :anzeige
     :fee-observation/stage :new
     :fee-observation/channel :electronic
     :fee-observation/rule-form :fixed
     :fee-observation/amount 0
     :fee-observation/source-kind :instrument
     :fee-observation/basis "VwKostO Nr. 18128（AbfAEV §8 の電子届出は徴収しない）"
     :fee-observation/as-of "2026-08-07"
     :fee-observation/source-url "https://rp-kassel.hessen.de/umwelt/abfall/sammlung-transport/erlaubnis-sammeln-befoerdern"
     :fee-observation/note "条文の文言は『Für die Prüfung einer elektronischen Anzeige nach §8 Abs.1 AbfAEV wird keine Gebühr erhoben』—— 無料は §53 という手続に付いているのではなく**電子経路に付いている**。紙は別 observation（50 €）"}
    {:fee-observation/id "deu-abfall-sn-erlaubnis-befristet"
     :fee-observation/procedure :deu-abfall-transport
     :fee-observation/authority "Sachsen"
     :fee-observation/licence-type :erlaubnis
     :fee-observation/stage :new
     :fee-observation/channel :any
     :fee-observation/rule-form :range
     :fee-observation/range-min 37500
     :fee-observation/range-max 500000
     :fee-observation/source-kind :instrument
     :fee-observation/basis "10. SächsKVZ Anlage 1 lfd. Nr. 3 Tarifstelle 13.4.1（10 年以内の期限付き許可）"
     :fee-observation/as-of "2026-08-07"
     :fee-observation/source-url "https://www.revosax.sachsen.de/vorschrift/19330-Zehntes-Saechsisches-Kostenverzeichnis"
     :fee-observation/note "通常ケース。**額は裁量ではなく計算規則で決まる** —— 許可の経済的価値を年 500 € とし期限年数を乗じ、廃棄物コード数に応じて減額（1–10 コード 25% / 11–50 15% / 51–100 7,5% / 100 超 減額なし）。⚠ 一部の Landkreis ページが 100–6.000 € と表示するが、これは 13.4.3（変更 100–5.000）の下限と 13.4.2 の上限を跨いだ合成で、条文上そのような項目は無い"}
    {:fee-observation/id "deu-abfall-sn-erlaubnis-unbefristet"
     :fee-observation/procedure :deu-abfall-transport
     :fee-observation/authority "Sachsen"
     :fee-observation/licence-type :erlaubnis
     :fee-observation/stage :new
     :fee-observation/channel :any
     :fee-observation/rule-form :range
     :fee-observation/range-min 450000
     :fee-observation/range-max 600000
     :fee-observation/source-kind :instrument
     :fee-observation/basis "10. SächsKVZ Tarifstelle 13.4.2（10 年超の期限付き、または無期限の許可）"
     :fee-observation/as-of "2026-08-07"
     :fee-observation/source-url "https://www.revosax.sachsen.de/vorschrift/19330-Zehntes-Saechsisches-Kostenverzeichnis"
     :fee-observation/note "13.4.1 と連続しない二段構え（5.000 と 4.500 が重なる）。同じ :licence-type / :stage / :channel を持つ 13.4.1 とは許可期間で分かれる —— この軸は observation の 3 軸では表せず、note が担っている"}
    {:fee-observation/id "deu-abfall-sn-anzeige"
     :fee-observation/procedure :deu-abfall-transport
     :fee-observation/authority "Sachsen"
     :fee-observation/licence-type :anzeige
     :fee-observation/stage :new
     :fee-observation/channel :any
     :fee-observation/rule-form :range
     :fee-observation/range-min 3500
     :fee-observation/range-max 27500
     :fee-observation/source-kind :instrument
     :fee-observation/basis "10. SächsKVZ Tarifstelle 13.1"
     :fee-observation/as-of "2026-08-07"
     :fee-observation/source-url "https://www.revosax.sachsen.de/vorschrift/19330-Zehntes-Saechsisches-Kostenverzeichnis"
     :fee-observation/note "無料ではない"}
    {:fee-observation/id "deu-abfall-rp-erlaubnis"
     :fee-observation/procedure :deu-abfall-transport
     :fee-observation/authority "Rheinland-Pfalz"
     :fee-observation/licence-type :erlaubnis
     :fee-observation/stage :new
     :fee-observation/channel :any
     :fee-observation/rule-form :range
     :fee-observation/range-min 30000
     :fee-observation/range-max 100000
     :fee-observation/source-kind :instrument
     :fee-observation/basis "Gebührenverzeichnis zur Sonderabfall-Kostenverordnung Lfd. Nr. 2.7"
     :fee-observation/as-of "2026-08-07"
     :fee-observation/source-url "https://sam-rlp.de/aufgaben/gebuehren/"
     :fee-observation/note "**根拠条例に注意。** RLP の Besonderes Gebührenverzeichnis（Umweltrecht, 2019-08-28）には §§53/54 のエントリが存在せず、所管が SAM（Zentrale Stelle für Sonderabfälle）のため別条例にある。上限 1.000 € は 16 州で最低水準"}
    {:fee-observation/id "deu-abfall-rp-anzeige"
     :fee-observation/procedure :deu-abfall-transport
     :fee-observation/authority "Rheinland-Pfalz"
     :fee-observation/licence-type :anzeige
     :fee-observation/stage :new
     :fee-observation/channel :any
     :fee-observation/rule-form :range
     :fee-observation/range-min 5000
     :fee-observation/range-max 15000
     :fee-observation/source-kind :instrument
     :fee-observation/basis "Gebührenverzeichnis zur Sonderabfall-Kostenverordnung Lfd. Nr. 2.5"
     :fee-observation/as-of "2026-08-07"
     :fee-observation/source-url "https://sam-rlp.de/aufgaben/gebuehren/"
     :fee-observation/note "無料ではない"}
    {:fee-observation/id "deu-abfall-sh-erlaubnis"
     :fee-observation/procedure :deu-abfall-transport
     :fee-observation/authority "Schleswig-Holstein"
     :fee-observation/licence-type :erlaubnis
     :fee-observation/stage :new
     :fee-observation/channel :any
     :fee-observation/rule-form :range
     :fee-observation/range-min 25000
     :fee-observation/range-max 500000
     :fee-observation/source-kind :instrument
     :fee-observation/basis "VerwGebVO Allgemeiner Gebührentarif Tarifstelle 1.1.14"
     :fee-observation/as-of "2026-08-07"
     :fee-observation/source-url "https://www.segeberg.de/loadDocument.phtml?ObjSvrID=3466&ObjID=854&ObjLa=1&Ext=PDF"
     :fee-observation/note "VerwGebVO は 2018-09-26 のもの。2024-11-26 改正令が Tarifstelle 19 のみを変更し 1.1.13/1.1.14 に影響しないことは確認したが、2024-11-19 改正令の本文自体は未閲覧（州 juris ポータルが JS 依存）—— 2026 時点までの改正監査は未完"}
    {:fee-observation/id "deu-abfall-sh-anzeige"
     :fee-observation/procedure :deu-abfall-transport
     :fee-observation/authority "Schleswig-Holstein"
     :fee-observation/licence-type :anzeige
     :fee-observation/stage :new
     :fee-observation/channel :any
     :fee-observation/rule-form :range
     :fee-observation/range-min 3000
     :fee-observation/range-max 12000
     :fee-observation/source-kind :instrument
     :fee-observation/basis "VerwGebVO Tarifstelle 1.1.13"
     :fee-observation/as-of "2026-08-07"
     :fee-observation/source-url "https://www.segeberg.de/loadDocument.phtml?ObjSvrID=3466&ObjID=854&ObjLa=1&Ext=PDF"
     :fee-observation/note "無料ではない。16 州で最も低い §53 の上限"}
    {:fee-observation/id "deu-abfall-mv-erlaubnis-ceiling"
     :fee-observation/procedure :deu-abfall-transport
     :fee-observation/authority "Mecklenburg-Vorpommern"
     :fee-observation/licence-type :erlaubnis
     :fee-observation/stage :new
     :fee-observation/channel :any
     :fee-observation/rule-form :ceiling
     :fee-observation/range-max 550000
     :fee-observation/source-kind :instrument
     :fee-observation/basis "AbfKostVO M-V Anlage Tarifstelle 222.4（nach Zeitaufwand, höchstens 5.500 €）"
     :fee-observation/as-of "2026-08-07"
     :fee-observation/source-url "https://www.mv-serviceportal.de/leistung?leistungId=118519592&ortId=7230"
     :fee-observation/note "**下限の定めが無く上限のみ**（Niedersachsen の逆）。時間単価は Tarifstelle 101.1 で 30 分単位、LG2 第2入職以上 40,50 €/半時間。⚠ 閲覧できた条文は 2014-10-17 改正版で現行は 2024-01-31 改正（landesrecht-mv.de が JS 依存）。州官庁 2 ページが同じ 5.500 を示しており額は変わっていないと見られる。2 回目の独立調査は Landkreis のページで『Mindestens 0,00 EUR, höchstens 5500,00 EUR』という表示を読んでいる —— 下限 0 と『下限の定めが無い』は実質同じだが、**表示のしかたが出所によって違う**"}
    {:fee-observation/id "deu-abfall-mv-anzeige-ceiling"
     :fee-observation/procedure :deu-abfall-transport
     :fee-observation/authority "Mecklenburg-Vorpommern"
     :fee-observation/licence-type :anzeige
     :fee-observation/stage :new
     :fee-observation/channel :any
     :fee-observation/rule-form :ceiling
     :fee-observation/range-max 20000
     :fee-observation/source-kind :instrument
     :fee-observation/basis "AbfKostVO M-V Tarifstelle 222.1（nach Zeitaufwand, höchstens 200 €）"
     :fee-observation/as-of "2026-08-07"
     :fee-observation/source-url "https://www.mv-serviceportal.de/leistung?leistungId=118519592&ortId=7230"
     :fee-observation/note "無料ではない。州ポータルの『0,00 - 200,00 EUR』は時間費用がゼロになりうるという運用表示であって免除規定ではない"}
    {:fee-observation/id "deu-abfall-sl-erlaubnis"
     :fee-observation/procedure :deu-abfall-transport
     :fee-observation/authority "Saarland"
     :fee-observation/licence-type :erlaubnis
     :fee-observation/stage :new
     :fee-observation/channel :any
     :fee-observation/rule-form :range
     :fee-observation/range-min 10000
     :fee-observation/range-max 1000000
     :fee-observation/source-kind :instrument
     :fee-observation/basis "Allgemeines Gebührenverzeichnis（52. Änderung）Abschnitt 2 Nr. 1.23"
     :fee-observation/as-of "2026-08-07"
     :fee-observation/source-url "https://www.saarland.de/SharedDocs/Downloads/DE/LAV/Service/Gebuehren/dl_Allgemeines-Gebuehrenverzeichnis_lav.pdf?__blob=publicationFile&v=2"
     :fee-observation/note "16 州で最も広い法定の幅（上限 10.000 € は最高）"}
    {:fee-observation/id "deu-abfall-sl-anzeige"
     :fee-observation/procedure :deu-abfall-transport
     :fee-observation/authority "Saarland"
     :fee-observation/licence-type :anzeige
     :fee-observation/stage :new
     :fee-observation/channel :any
     :fee-observation/rule-form :range
     :fee-observation/range-min 5000
     :fee-observation/range-max 150000
     :fee-observation/source-kind :instrument
     :fee-observation/basis "Allgemeines Gebührenverzeichnis Nr. 1.22"
     :fee-observation/as-of "2026-08-07"
     :fee-observation/source-url "https://www.saarland.de/SharedDocs/Downloads/DE/LAV/Service/Gebuehren/dl_Allgemeines-Gebuehrenverzeichnis_lav.pdf?__blob=publicationFile&v=2"
     :fee-observation/note "無料ではない。⚠ 所管の LUA サービスポータルは同じ届出を 50–100 € と表示しており条例の幅（50–1.500）と一致しない。条例側を法定の幅として採り、ポータル値は実務レンジと解した（両者を調停する文書は見つからず）"}
    {:fee-observation/id "deu-abfall-hb-erlaubnis"
     :fee-observation/procedure :deu-abfall-transport
     :fee-observation/authority "Bremen"
     :fee-observation/licence-type :erlaubnis
     :fee-observation/stage :new
     :fee-observation/channel :any
     :fee-observation/rule-form :range
     :fee-observation/range-min 5700
     :fee-observation/range-max 287500
     :fee-observation/source-kind :authority-guidance
     :fee-observation/basis "Die Senatorin für Umwelt, Klima und Wissenschaft, Referat 23（根拠として KrWG §54 Abs.1-7 / AbfAEV §10 を挙げる）"
     :fee-observation/as-of "2026-08-07"
     :fee-observation/source-url "https://www.service.bremen.de/dienstleistungen/antrag-auf-erteilung-einer-erlaubnis-fuer-sammler-befoerderer-haendler-und-makler-von-gefaehrlichen-abfaellen-16792?reg=kosten"
     :fee-observation/note "州公式サービスポータルの記載（2026-04-27 更新）で、Tarifstelle / Kostenverzeichnis の番号は明示されておらず条例の行項目まで辿れていない。57 € という下限は他州に類例が無い"}
    {:fee-observation/id "deu-abfall-hb-anzeige-free"
     :fee-observation/procedure :deu-abfall-transport
     :fee-observation/authority "Bremen"
     :fee-observation/licence-type :anzeige
     :fee-observation/stage :new
     :fee-observation/channel :any
     :fee-observation/rule-form :fixed
     :fee-observation/amount 0
     :fee-observation/source-kind :authority-guidance
     :fee-observation/basis "Die Senatorin für Umwelt, Klima und Wissenschaft（gebührenfrei）"
     :fee-observation/as-of "2026-08-07"
     :fee-observation/source-url "https://www.service.bremen.de/dienstleistungen/anzeige-einer-taetigkeit-als-sammler-befoerderer-haendler-und-makler-von-abfaellen-16796"
     :fee-observation/note "**16 州で、提出方法を問わず §53 が無条件に無料なのは Bremen だけ。** 条件付き無料が Hessen（電子のみ）と Niedersachsen（完全かつ電子のみ）の 2 州、残り 13 州は有料 —— 『多くの州で無料』という前提は成り立たない"}
    {:fee-observation/id "deu-abfall-st-erlaubnis"
     :fee-observation/procedure :deu-abfall-transport
     :fee-observation/authority "Sachsen-Anhalt"
     :fee-observation/licence-type :erlaubnis
     :fee-observation/stage :new
     :fee-observation/channel :any
     :fee-observation/rule-form :range
     :fee-observation/range-min 30000
     :fee-observation/range-max 100000
     :fee-observation/source-kind :authority-guidance
     :fee-observation/basis "AllGO LSA（州公式ポータルが根拠として挙げるが Tarifstelle 番号は不記載）"
     :fee-observation/as-of "2026-08-07"
     :fee-observation/source-url "https://buerger.sachsen-anhalt.de/detail?areaId=300381&pstId=29827919"
     :fee-observation/note "条例本文まで辿れていない。所管は Landkreis / kreisfreie Stadt の untere Abfallbehörde"}
    {:fee-observation/id "deu-abfall-st-anzeige-papier"
     :fee-observation/procedure :deu-abfall-transport
     :fee-observation/authority "Sachsen-Anhalt"
     :fee-observation/licence-type :anzeige
     :fee-observation/stage :new
     :fee-observation/channel :paper
     :fee-observation/rule-form :fixed
     :fee-observation/amount 10000
     :fee-observation/source-kind :authority-guidance
     :fee-observation/basis "AllGO LSA（州公式ポータル記載）"
     :fee-observation/as-of "2026-08-07"
     :fee-observation/source-url "https://buerger.sachsen-anhalt.de/detail?areaId=300381&pstId=29827919"
     :fee-observation/note "無料ではない。EFB・EMAS 事業者は紙 150 €"}
    {:fee-observation/id "deu-abfall-st-anzeige-elektronisch"
     :fee-observation/procedure :deu-abfall-transport
     :fee-observation/authority "Sachsen-Anhalt"
     :fee-observation/licence-type :anzeige
     :fee-observation/stage :new
     :fee-observation/channel :electronic
     :fee-observation/rule-form :fixed
     :fee-observation/amount 7500
     :fee-observation/source-kind :authority-guidance
     :fee-observation/basis "AllGO LSA（eAEV-formulare.de 経由）"
     :fee-observation/as-of "2026-08-07"
     :fee-observation/source-url "https://buerger.sachsen-anhalt.de/detail?areaId=300381&pstId=29827919"
     :fee-observation/note "EFB・EMAS 事業者は電子 120 €"}
    {:fee-observation/id "deu-abfall-th-erlaubnis"
     :fee-observation/procedure :deu-abfall-transport
     :fee-observation/authority "Thüringen"
     :fee-observation/licence-type :erlaubnis
     :fee-observation/stage :new
     :fee-observation/channel :any
     :fee-observation/rule-form :range
     :fee-observation/range-min 25000
     :fee-observation/range-max 500000
     :fee-observation/source-kind :authority-guidance
     :fee-observation/basis "Serviceportal Thüringen（Thüringer Ministerium für Umwelt, Energie, Naturschutz und Forsten が 2025-05-21 に fachlich freigegeben）"
     :fee-observation/as-of "2026-08-07"
     :fee-observation/source-url "https://buerger.thueringen.de/detail?pstId=741791"
     :fee-observation/note "⚠ **条例に対応する項目が存在しない。** ThürVwKostOMUEN の Anlage Teil A Abschnitt 1『Abfall』は 2012 年以前の KrW-/AbfG のままで、§§53/54 の Tarifstelle が無い。Nr. 15.1『Erteilung einer Transportgenehmigung 250,00』は廃止された Transportgenehmigung であって §54 の許可ではない —— **この 250 を §54 の額として使わないこと**"}
    {:fee-observation/id "deu-abfall-he-anzeige-papier"
     :fee-observation/procedure :deu-abfall-transport
     :fee-observation/authority "Hessen"
     :fee-observation/licence-type :anzeige
     :fee-observation/stage :new
     :fee-observation/channel :paper
     :fee-observation/rule-form :fixed
     :fee-observation/amount 5000
     :fee-observation/source-kind :instrument
     :fee-observation/basis "VwKostO（Geschäftsbereich Umwelt）Nr. 18128（AbfAEV §7 Abs.1 の届出審査）"
     :fee-observation/as-of "2026-08-07"
     :fee-observation/source-url "https://verkuendung.hessen.de/sites/verkuendung.hessen.de/files/veroeffentlichungsplattform_plugin/published/782/GVBl_2025_Nr_11_Regelungstext.pdf"
     :fee-observation/note "同じ Nr. 18128 が紙 50 € と電子無料の両方を定める。条文 PDF を自分で読んで確認"}
    {:fee-observation/id "deu-abfall-he-erlaubnis-aenderung"
     :fee-observation/procedure :deu-abfall-transport
     :fee-observation/authority "Hessen"
     :fee-observation/licence-type :erlaubnis
     :fee-observation/stage :change
     :fee-observation/channel :any
     :fee-observation/rule-form :fixed
     :fee-observation/amount 25000
     :fee-observation/source-kind :instrument
     :fee-observation/basis "VwKostO Nr. 181303（AbfAEV §10 Abs.6 S.1 による重要事項変更に伴う許可の変更）"
     :fee-observation/as-of "2026-08-07"
     :fee-observation/source-url "https://verkuendung.hessen.de/sites/verkuendung.hessen.de/files/veroeffentlichungsplattform_plugin/published/782/GVBl_2025_Nr_11_Regelungstext.pdf"
     :fee-observation/note "条文 PDF を自分で読んで見つけた項目。1 回目の調査は交付（181301/181302）だけを返しており、変更は入っていなかった"}]

   :procedure/source-urls
   [
                        "https://service.berlin.de/dienstleistung/326690/"
                        "https://www.gesetze-im-internet.de/abfaev/__10.html"
                        "https://www.gesetze-im-internet.de/abfaev/__12.html"
                        "https://www.gesetze-im-internet.de/abfaev/__13.html"
                        "https://www.gesetze-im-internet.de/abfaev/__3.html"
                        "https://www.gesetze-im-internet.de/abfaev/__4.html"
                        "https://www.gesetze-im-internet.de/abfaev/__5.html"
                        "https://www.gesetze-im-internet.de/abfaev/__6.html"
                        "https://www.gesetze-im-internet.de/abfaev/__7.html"
                        "https://www.gesetze-im-internet.de/abfaev/__9.html"
                        "https://www.gesetze-im-internet.de/avv/"
                        "https://www.gesetze-im-internet.de/avv/ （xml.zip 内 BJNR337910001.xml の Anlage）"
                        "https://www.gesetze-im-internet.de/krwg/__3.html"
                        "https://www.gesetze-im-internet.de/krwg/__53.html"
                        "https://www.gesetze-im-internet.de/krwg/__54.html"
                        "https://www.gesetze-im-internet.de/krwg/__55.html"
                        "https://www.gesetze-im-internet.de/vwvfg/__42a.html"
                        "https://www.gewerbeaufsicht.niedersachsen.de/download/89281/Merkblatt_Erlaubnis_Stand_12_2022.pdf"
                        "https://www.gewerbeaufsicht.niedersachsen.de/startseite/umweltschutz/kreislauf_und_abfallwirtschaft/anzeige_nach_53_krwg/anzeige-nach-53-krwg-106132.html"
                        "https://www.hamburg.de/politik-und-verwaltung/behoerden/bukea/themen/abfall-entsorgung/sammler-befoerderer-haendler-makler/abfallbefoerderung-erlaubnis-krwg-159504"
                        "https://www.hamburg.de/service/info/11277423/"
   ]
   :procedure/authority "申請者が Hauptsitz を置く州（Land）の所管当局（KrWG §53 Abs.1 S.3 / §54 Abs.1 S.3）。連邦官庁ではない。国内に本店が無い場合は、最初に収集・運搬・取引・仲介を行う州の当局（AbfAEV §7 Abs.2 / §9 Abs.2）"
   ;; **ここが連邦と州の境目。** 法は連邦、窓口と手数料は州。
   ;; 州の官庁名は実在確認できた 3 州だけ挙げ、「州ごとに違う」を明示して残り 13 州を
   ;; 推測で埋めない。
   :procedure/window "州ごとの所管庁（実在確認済みの例: Niedersachsen = Staatliches Gewerbeaufsichtsamt Hildesheim / Hamburg = Behörde für Umwelt, Klima, Energie und Agrarwirtschaft / Berlin = Senatsverwaltung für Mobilität, Verkehr, Klimaschutz und Umwelt。他 13 州は未確認 — 自社の Hauptsitz の州を個別に確認すること）。電子申請は州共通の eAEV ポータル https://eaev.gadsys.de（AbfAEV §8 / §11 が命じる『bundesweit einheitliches informationstechnisches System』）。書面は AbfAEV Anlage 2（届出）／Anlage 3（許可申請）の様式"
   ;; **法定の有効期間は無い。** §54 Abs.1 S.4 の許可は連邦全域に効き、州所管庁の
   ;; 公式 Merkblatt（Nds. Gewerbeaufsichtsamt Hildesheim, Stand 05/2026）も
   ;; 「generell bundesweit …, für alle Abfallarten und zeitlich unbefristet」と明記。
   ;; ただし当局は §54 Abs.2 の Nebenbestimmung で、届出側は §53 Abs.3 で
   ;; 明文上「zeitlich befristen」できる。nil は「更新制度が無い」であって
   ;; 「絶対に期限が付かない」ではない。
   :procedure/valid-years nil

   ;; ITAD（PC 廃棄）で扱う廃棄物と、それが §53 と §54 のどちらに落ちるか。
   ;; **AVV の Abfallschlüssel に * が付いていれば gefährlich**（AVV §3 Abs.1）。
   ;; 以下の 6 コードは AVV 本文（gesetze-im-internet.de の XML）で実際に読んで確認した。
   :procedure/waste-categories
   [{:id :geraete-mit-gefaehrlichen-bauteilen :name "16 02 13* gefährliche Bauteile enthaltende gebrauchte Geräte"
     :itad-note "事業所由来の PC・サーバでバッテリー等の危険部品を含むもの。* 付き = gefährlich → §54 の Erlaubnis 側"}
    {:id :geraete-sonstige :name "16 02 14 gebrauchte Geräte（16 02 09〜13 に当たらないもの）"
     :itad-note "危険部品を外した／含まない機器。* 無し = nicht gefährlich → §53 の Anzeige 側"}
    {:id :entfernte-bauteile :name "16 02 16 aus gebrauchten Geräten entfernte Bauteile（16 02 15* 以外）"
     :itad-note "抜去した HDD・メモリ・基板。抜いた部品が 16 02 15*（gefährliche Bauteile）に当たるかで分岐する"}
    {:id :weee-haushalt-gefaehrlich :name "20 01 35* gebrauchte elektrische und elektronische Geräte, die gefährliche Bauteile enthalten"
     :itad-note "家庭由来（宅配回収）の機器で危険部品を含むもの。宅配回収 ITAD はここに落ちやすい"}
    {:id :weee-haushalt-sonstige :name "20 01 36 gebrauchte elektrische und elektronische Geräte（20 01 21/23/35 以外）"
     :itad-note "家庭由来で危険部品を含まないもの"}
    {:id :batterien-sonstige :name "16 06 05 andere Batterien und Akkumulatoren"
     :itad-note "PC から抜いたバッテリー。鉛蓄電池（16 06 01*）等に当たらないもの。当たれば gefährlich"}]

   :procedure/requirements
   [{:requirement/id :abfallklassifizierung
     :requirement/name "廃棄物の危険性分類（gefährlich かどうか）の確定"
     :requirement/detail "KrWG 第3条第5項は『第48条の法規命令で定められた廃棄物が gefährlich、それ以外は nicht gefährlich』とし、その命令が AVV。AVV 第3条第1項により Abfallschlüssel に * が付いた種類が gefährlich（同条第2項で EU 廃棄物枠組指令 2008/98/EC 附属書III の危険特性 HP1-HP15 に接続する）。**この分類が §53 の届出で足りるか §54 の許可が要るかを決める**ので、手続きの最初に確定させる。"
     :requirement/blocking? true}
    {:requirement/id :zuverlaessigkeit
     :requirement/name "Zuverlässigkeit（信頼性）"
     :requirement/detail "KrWG §53 Abs.2 S.1 / §54 Abs.1 S.2 Nr.1。事業主および事業の指揮・監督に責任を持つ者が対象。AbfAEV §3 Abs.2 は『通常は信頼性が無い』場合を具体化する — 環境刑法・廃棄物法・水法・化学品法・遺伝子技術法・原子力法、食品/医薬品/植物保護/感染症法、営業/労働保護/運送/危険物法、麻薬/武器/爆発物法の違反により、届出または許可申請前の5年以内に **2,500 ユーロ超の過料**を科されたか刑を受けた場合、および反復的・重大な義務違反があった場合。"
     :requirement/blocking? true}
    {:requirement/id :fachkunde
     :requirement/name "Fachkunde（専門知識、経営責任者）"
     :requirement/detail "許可側（AbfAEV §5 Abs.1）は ①申請する活動についての**2年の実務**（当該分野の大学/専門大学卒、商業・技術系の専門学校/職業訓練修了、または Meister 資格があれば1年に短縮）に加え、②**所管庁が承認した Lehrgang**（AbfAEV Anlage 1 の内容）の受講が必須。届出側（AbfAEV §4）は原則②が不要で実務経験のみだが、当局が §4 Abs.5 で受講と定期的継続教育を命じうる。Lehrgang は**どの州で受けてもよい**（提供者が承認を持っていればよい。Nds. Merkblatt 明記）。"
     :requirement/blocking? true}
    {:requirement/id :fortbildung
     :requirement/name "Fortbildung（継続教育、少なくとも3年ごと）"
     :requirement/detail "AbfAEV §5 Abs.3。許可対象の事業主・指揮監督責任者は『regelmäßig, mindestens alle drei Jahre』承認 Lehrgang に参加し、**求められずとも当局に証明する**義務を負う。許可取得後に発生する継続義務であって、初回申請の要件ではない。"
     :requirement/blocking? false}
    {:requirement/id :sachkunde-personal
     :requirement/name "Sachkunde（その他の職員）"
     :requirement/detail "AbfAEV §6。その他の職員は Einarbeitungsplan（習熟計画）に基づき社内で習熟させ、必要な最新知識を保持させる。継続教育の必要性は事業主または指揮監督責任者が判定する。当局は公益上必要なら計画の書面化と提出を命じうる。KrWG §53 Abs.3 S.3 は、この Sachkunde が証明されない場合に**届出済みの活動を禁止しなければならない**と定めるので、書類要件ではないが活動の存続を左右する。"
     :requirement/blocking? true}
    {:requirement/id :kfz-haftpflicht
     :requirement/name "Kfz-Haftpflichtversicherung（危険廃棄物を公道で運ぶ場合）"
     :requirement/detail "AbfAEV §9 Abs.3 S.1 Nr.8。危険廃棄物を公道で運ぶ Sammler / Beförderer は自動車損害賠償責任保険の証明を申請に添付する。同 Nr.7 の Betriebshaftpflicht / Umwelthaftpflicht は『sofern solche Versicherungen vorhanden sind』（存在する場合）にとどまり、連邦法は最低補償額を定めない — 最低額を求めるのは州の運用（:land-gebuehren-und-praxis を参照）。"
     :requirement/blocking? true}]

   ;; AbfAEV §9 Abs.3 S.1 の 8 項目（許可申請）を条文の順で写したもの。
   ;; 届出（§53）側は AbfAEV §7 Abs.1 により Anlage 2 の様式が本体で、
   ;; EfB / EMAS の免除に依る場合だけ証明書を添える。
   :procedure/documents
   [{:document/id :antrag-vordruck :document/name "申請様式（許可は AbfAEV Anlage 3、届出は Anlage 2。電子申請では Anlage 2 の『Unterschrift』欄は無くなる — AbfAEV §8 Abs.1 Nr.1）" :document/who :company}
    {:document/id :gewerbeanmeldung :document/name "Gewerbeanmeldung（営業開始届の写し。AbfAEV §9 Abs.3 Nr.1）" :document/who :company}
    {:document/id :registerauszug :document/name "Handels-, Vereins- oder Genossenschaftsregister の抄本（登記がある場合。同 Nr.2）" :document/who :company}
    {:document/id :gzr-firma :document/name "Gewerbezentralregister の firmenbezogene Auskunft, Belegart 9（法人・人的団体の場合。同 Nr.3）" :document/who :company}
    {:document/id :gzr-person :document/name "Gewerbezentralregister の personenbezogene Auskunft, Belegart 9（事業主および指揮監督責任者。同 Nr.4、GewO §150 Abs.5）" :document/who :officers}
    {:document/id :fuehrungszeugnis :document/name "Führungszeugnis, Belegart OG（事業主および指揮監督責任者。同 Nr.5、BZRG §§30 Abs.5・32 Abs.4。住所地自治体で申請）" :document/who :officers}
    {:document/id :fachkunde-nachweis :document/name "Fachkunde の証明（実務経験＋承認 Lehrgang の修了証。同 Nr.6）" :document/who :officers}
    {:document/id :haftpflicht :document/name "Betriebshaftpflichtversicherung および活動に対応した Umwelthaftpflichtversicherung の証明（**存在する場合**。同 Nr.7）" :document/who :company}
    {:document/id :kfz-haftpflicht :document/name "Kfz-Haftpflichtversicherung の証明（危険廃棄物を公道で運ぶ Sammler / Beförderer。同 Nr.8）" :document/who :company}
    {:document/id :efb-zertifikat :document/name "Entsorgungsfachbetrieb の有効な証明書（KrWG §56 Abs.3。§54 Abs.3 Nr.2 の許可免除に依り届出で済ませる場合に添付。AbfAEV §7 Abs.1 S.2）" :document/who :company}
    {:document/id :emas-urkunde :document/name "EMAS 登録証（AbfAEV §12 Abs.1 Nr.4 の許可免除に依る場合。後続の登録証は求められずとも提出する。AbfAEV §7 Abs.1 S.3-4）" :document/who :company}]

   :procedure/steps
   [{:step/id :classify-waste :step/order 1 :step/requires-human false
     :step/title "扱う廃棄物を AVV で分類し、§53（届出）か §54（許可）かを確定する"
     :step/detail "AVV の Abfallschlüssel に * が付けば gefährlich（AVV §3 Abs.1）。ITAD なら 16 02 13* / 16 02 14 / 16 02 16 / 20 01 35* / 20 01 36 / 16 06 05 の分岐を先に決める。**この 1 手で以降の様式・書類・費用・所要期間がすべて変わる**ので、他の step より前に置く。"}
    {:step/id :verify-current-rules :step/order 2 :step/requires-human true
     :step/title "自社 Hauptsitz の州の所管庁で、最新の様式・手数料・提出方法を確認"
     :step/detail "**手数料はこの手続き data に収録していない** — 連邦法は金額を定めず、州の Gebührenordnung が幅で定めるため。所管庁と、その州の Gebührenordnung 上の項目・金額をここで確定させる。電子申請（eAEV）に電子署名カードが要るかも州の運用で異なる。"
     :step/errand {:kind :verify-authority-info :draft-via :tayori
                   :evidence-schema {:authority :string :verified :map
                                     :source :string :date :iso-date}}}
    {:step/id :check-exemptions :step/order 3 :step/requires-human false
     :step/title "免除規定に当たらないかを確認する（当たれば手続き自体が消えるか軽くなる）"
     :step/detail "届出の免除: AbfAEV §7 Abs.8（法規命令に基づく製造者・販売者の非危険廃棄物の引取り）、同 Abs.9（『gewöhnlich und regelmäßig』でない収集・運搬。暦年で**非危険 20 トン／危険 2 トン**を超えれば常態と推定される）。許可の免除: KrWG §54 Abs.3（公法上の処理主体、および当該活動について認証された Entsorgungsfachbetrieb）、AbfAEV §12 Abs.1 の 6 類型（①本業が廃棄物でない事業者、②製造者・販売者の引取り、③使用済自動車の引渡し、④EMAS 登録事業所の該当業種、⑤海上輸送、⑥**Paket-, Express- und Kurierdienste**）。**許可を免れても §53 の届出義務は残る。** 当局は §12 Abs.2 で免除にかかわらず許可手続を命じうる。"}
    {:step/id :resolve-legal-questions :step/order 4 :step/requires-human true
     :step/title "事業スキームの法的整理（ドイツの Umweltrecht 専門の弁護士に諮る）"
     :step/detail ":procedure/legal-questions を諮る。特に『自社が Händler / Makler に当たるか』と『宅配回収が AbfAEV §12 Abs.1 Nr.6 の KEP 免除に乗るか』は、当たり外れで手続きの有無そのものが変わる。"
     :step/errand {:kind :consult-professional :draft-via :tayori
                   :evidence-schema {:office :string :date :iso-date
                                     :resolutions :map}}}
    {:step/id :acquire-fachkunde :step/order 5 :step/requires-human true
     :step/title "承認 Lehrgang（AbfAEV Anlage 1 の内容）の受講予約と受講"
     :step/detail "許可側は実務経験に加えて必須（AbfAEV §5 Abs.1 Nr.2）。提供者が所管庁の承認を持っていれば**どの州で受けてもよい**ので、自州で日程が無ければ他州を探す。承認の有無は提供者に都度確認する。"
     :step/errand {:kind :book-course :draft-via :koyomi
                   :evidence-schema {:provider :keyword :course :string :date :iso-date
                                     :attendee :string :confirmation-no :string}}}
    {:step/id :collect-documents :step/order 6 :step/requires-human false
     :step/title "申請書類一式の収集（:procedure/documents のチェックリスト消化）"
     :step/detail "Führungszeugnis と Gewerbezentralregister の抄本は**取得から3か月以内・原本**で提出するのが州の運用（Nds. Merkblatt）。取り寄せに時間がかかる一方で古くなると使えないので、他の書類より後ろに置く。AbfAEV §9 Abs.4 により Nr.1・2・6・7・8 は写しでよいが、真正性に疑いがあれば当局は原本を求めうる。"
     :step/errand {:kind :collect-documents :draft-via nil
                   :evidence-schema {:doc :keyword :obtained-date :iso-date}}}
    {:step/id :submit :step/order 7 :step/requires-human true
     :step/title "届出（Anlage 2）または許可申請（Anlage 3）の提出と手数料納付"
     :step/detail "提出は human gate。**許可側はここから 3 か月の Genehmigungsfiktion が動く** — 当局が完全な申請の受領確認（AbfAEV §10 Abs.1、開始日と満了日が明示される）を出したのち、当局が動かないまま 3 か月経つと許可されたものとみなされる（KrWG §54 Abs.6 S.2 i.V.m. VwVfG §42a。§42a Abs.2 の既定期間が 3 か月で、AbfAEV は別段の期間を定めていない）。ただし **この擬制は申請者が EU/EEA の国籍・法人であることが条件**で、それ以外には受領確認・期間告知の規定が適用されない（AbfAEV §10 Abs.8）。届出側にはそもそも擬制が無く、当局は受領を『unverzüglich』書面で確認するだけ（KrWG §53 Abs.1 S.2、AbfAEV §7 Abs.5 は記入済み様式の返送をもって確認とする）。控えと Vorgangsnummer / Kennnummer を台帳に記録する。"}
    {:step/id :respond-to-review :step/order 8 :step/requires-human true
     :step/title "審査対応（不備の補正）"
     :step/detail "申請が不完全なら当局は遅滞なく追完すべき書類を通知し、**3 か月の期間は完全な書類の到達をもって初めて起算される**（AbfAEV §10 Abs.2）。届出側も不完全なら追完を求められる（AbfAEV §7 Abs.4）。"}
    {:step/id :post-grant :step/order 9 :step/requires-human true
     :step/title "取得後の継続義務"
     :step/detail "①**携行義務**（AbfAEV §13）: 届出なら当局が確認した届出書の写し／印刷物、許可なら許可の写し（**非危険廃棄物を運ぶときも携行する** — §13 Abs.2 S.2）、擬制で許可を得た場合は申請書と受領確認の写し。鉄道車両による収集・運搬では免除。②**車両標識**（KrWG §55 Abs.1）: 公道で運ぶ車両には出発前に反射白色の警告板（A-Schild）2 枚。ただし『im Rahmen wirtschaftlicher Unternehmen』の Sammler / Beförderer には適用されない（同 S.2）。要件は AbfVerbrG §10 に従う。③**継続教育**（AbfAEV §5 Abs.3）: 少なくとも 3 年ごとに承認 Lehrgang を受け、求められずとも当局に証明。④**変更時**: 届出は重要事項が変われば再度の届出（AbfAEV §7 Abs.7）、許可は基礎事情が変われば新しい許可が必要で、指揮監督責任者の交替は届出で足りる（AbfAEV §10 Abs.6）。"}]

   ;; 結論を出さずに保持する法的論点。
   :procedure/legal-questions
   [{:question/id :gefaehrlichkeit
     :question/title "ITAD の PC・電子機器が gefährliche Abfälle に当たるか"
     :question/detail "AVV は同じ『使用済み機器』を、危険部品を含むか否かで 16 02 13*／16 02 14（事業所由来）、20 01 35*／20 01 36（家庭由来）に割る。バッテリー・特定の基板・ディスプレイの扱い次第で * 側に落ち、その瞬間に §53 の届出が §54 の許可に変わる。回収時点で分類が確定しない混合ロットをどう扱うかも含めて詰める。"
     :question/status :open}
    {:question/id :haendler-makler-gaitousei
     :question/title "自ら運ばない ops 層が Händler / Makler に当たるか"
     :question/detail "KrWG §53 Abs.1 / §54 Abs.1 の名宛人は Sammler・Beförderer に加えて **Händler（取引）と Makler（仲介）**。許可業者に取り次ぐだけのプラットフォームがこれに当たれば、自社も届出（危険廃棄物なら許可）の対象になる。日本の『運送委託で収集運搬許可を回避する』設計がここでは通らない可能性が高い。Makler の外延を示す判例はワークスペースに未収載（cloud-itonami-licensed-operator の :known-gaps でも同じ穴が挙がっている）。"
     :question/status :open}
    {:question/id :kep-ausnahme
     :question/title "宅配回収が AbfAEV §12 Abs.1 Nr.6 の KEP 免除に乗るか"
     :question/detail "AbfAEV §12 Abs.1 Nr.6 は『Paket-, Express- und Kurierdienste の枠内で収集・運搬する Sammler / Beförderer』を、その運送約款が危険物輸送の安全法令を考慮している限り、危険廃棄物の**許可義務から**除外する。宅配回収 ITAD がここに乗れば §54 が外れるが、**§53 の届出義務は残る**。また当局は §12 Abs.2 で公益上必要なら許可手続を命じうる。誰が『KEP の枠内』の主体なのか（運送会社か、荷主である自社か）を確定させる必要がある。"
     :question/status :open}
    {:question/id :wirtschaftliche-unternehmen
     :question/title "自社が『im Rahmen wirtschaftlicher Unternehmen』に当たるか"
     :question/detail "廃棄物の取扱いが本業でない事業者は AbfAEV §12 Abs.1 Nr.1 で危険廃棄物の**許可義務から**外れ、Fachkunde も §4 Abs.4（本業に必要な職業資格で足りる）という軽い規律になり、KrWG §55 Abs.1 S.2 で A-Schild も不要になる。他方 AbfAEV §7 Abs.9 の 20 トン／2 トン閾値もこの類型に効く。**ITAD を事業として掲げている以上ここには当たらない可能性が高い**が、当たる/当たらないで規律の重さが大きく変わるので明示的に判定する。"
     :question/status :open}
    {:question/id :schwellenwert
     :question/title "年間取扱量が届出免除の閾値に収まるか"
     :question/detail "AbfAEV §7 Abs.9: 『gewöhnlich und regelmäßig』でない収集・運搬は届出義務を免れるが、暦年の合計が**非危険 20 トンまたは危険 2 トン**を超えれば常態と推定される。PC は 1 台 10kg 前後なので、非危険側 20 トンは概ね年 2,000 台規模。事業計画上の想定台数がこの線のどちら側かを最初に見積もる。"
     :question/status :open}
    {:question/id :land-gebuehren-und-praxis
     :question/title "手数料と保険の最低額は州ごとに違う — 自社はどの州の運用に服するか"
     :question/detail "連邦法は金額を定めない。2026-08-07 に確認した公式値: **Niedersachsen** は AllGO の Kostentarif 2.1.35 により初回交付が『durchschnittlich ca. 360 €』（平均額であって定額ではない）、**Berlin** は運搬許可の交付が 250–5,000 €、重要変更の決定が 50–5,000 €、期限付き許可が 50–5,000 €、**Hamburg** は『je nach Aufwand 50,00 EUR - 1.000,00 EUR』（サービス案内）と『最低 371 €、事務量に応じて増額、UmwGebO による』（所管庁の案内）で公式ページ間に食い違いがある。保険も同様で、AbfAEV §9 Abs.3 Nr.7 は連邦法上『存在する場合』の添付にとどまるのに、Niedersachsen は Sammler / Beförderer に **Umwelt-Haftpflichtversicherung 一律最低 100 万ユーロ**の証明を求めている。**残り 13 州は未確認。** 手数料も処理実務も、この data ではなく自社 Hauptsitz の州の Gebührenordnung が正本。"
     :question/status :open}
    {:question/id :andere-genehmigungen
     :question/title "KrWG の許可だけでは足りない — 併存する他法の許可"
     :question/detail "所管庁の Merkblatt が明記する: 『Die Erlaubnis ist eine ausschließlich nach dem KrWG ergehende Entscheidung. Andere Genehmigungen, Erlaubnisse, Konzessionen usw. (insbesondere nach dem Güterkraftverkehrsgesetz und den Gefahrgutverordnungen) müssen unabhängig von der abfallrechtlichen Erlaubnis vorliegen.』。貨物自動車運送事業（GüKG）と危険物輸送（ADR / GGVSEB 系）の規律は別建てで、KrWG §55 Abs.3 も危険物輸送法令は影響を受けないと定める。この data はそれらを収録していない。"
     :question/status :open}
    {:question/id :efb-zertifizierung
     :question/title "Entsorgungsfachbetrieb 認証を取って許可を免れる経路の是非"
     :question/detail "KrWG §54 Abs.3 Nr.2 により、当該許可対象活動について認証された Entsorgungsfachbetrieb（KrWG §56）は許可義務から外れる（届出には §56 Abs.3 の有効な証明書を添付し、車載も要る — AbfAEV §7 Abs.1 S.2 / §13 Abs.1 S.4）。許可申請と EfB 認証取得のどちらが速く安いか、また EfB 認証が他の商流（排出事業者からの受注要件）でも効くかを併せて判断する。KrWG §56 の認証要件そのものはこの data に未収載。"
     :question/status :open}]})
