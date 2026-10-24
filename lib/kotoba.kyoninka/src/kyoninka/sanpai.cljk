(ns kyoninka.sanpai
  "産業廃棄物収集運搬業許可(積替え保管を除く)の手続き data。
  東京都テンプレート。ADR-2607141620。

  収録値は一般に公表されている標準値であり、:verify フラグ付き —
  申請直前に許可権者の公式情報で実値を確認すること(それ自体が step 1)。"
  (:require [kyoninka.schema :as schema]))

(def procedure
  {:procedure/id :sanpai-shuun-tokyo
   :procedure/name "産業廃棄物収集運搬業許可（東京都・積替え保管なし）"
   :procedure/law "廃棄物の処理及び清掃に関する法律（廃棄物処理法）第14条第1項"
   ;; **法域。** 以前は暗黙に日本だった。産業廃棄物収集運搬業許可は都道府県知事の許可（法域は日本、窓口が東京都）。
   :procedure/jurisdiction "JPN"
   :procedure/authority "東京都知事（環境局 資源循環推進部）"
   :procedure/window "東京都環境局（申請は郵送/窓口。最新の受付方法は要確認）"
   :procedure/fee {:amount 81000
                   ;; **通貨を型に焼かない。** 以前の schema は :procedure/fee-jpy で
                   ;; JPY を属性名に持っており、日本以外を収録した瞬間に嘘になった。
                   :currency "JPY"
                   ;; JPY は最小単位の端数を持たないので minor-unit は 1。
                   :minor-unit 1
                   :kind :新規許可申請手数料
                   ;; **19,000 円 / 81,000 円は「国が定めた額」ではない。**
                   ;; 地方自治法第228条第1項は「政令で定める金額の手数料を徴収することを
                   ;; **標準として**条例を定めなければならない」であって拘束ではなく、
                   ;; 徴収の法的根拠は各自治体の手数料条例。全国一律でも純粋な自治でもない
                   ;; ので `:statute-standard`。
                   :set-by {:level :statute-standard
                            :body "各都道府県・政令市（手数料条例）。**許可権者ごとに別の許可が要る**ので、営業する都道府県・政令市の数だけ手数料が積み上がる"
                            :basis "地方自治法第228条第1項 + 地方公共団体の手数料の標準に関する政令（平成12年政令第16号）別表 九十四の項1"}
                   :verify (schema/unverified "東京都環境局の公式ページ/手数料条例で最新額を確認")}
   ;; 22 自治体 + 政令標準 + 条例本文を実測（2026-08-07、28 観測）。
   ;;
   ;; **新規 81,000 円は 22 自治体すべてで一致した。** 通説の「積替え保管ありの
   ;; 新規は 82,000 円」は**どの公式資料にも存在しない** —— 積替えの有無が変える
   ;; のは事前協議・現地審査・添付書類であって手数料ではない（大阪府は積替え
   ;; あり/なしを別ページで運用して両方 81,000 円、広島市は条例別表第4 の
   ;; 一次法令レベルで区分自体が無い）。だから観測の `:licence-type` は
   ;; **新規について積替えの区別を持たない** —— 表に無い区別を読み込まないため。
   ;;
   ;; **一律なのは新規だけで、東京都は更新で標準から外れている**（積替え保管
   ;; なしの更新 42,000 円、政令標準 73,000 円の 4 割超の減額）。しかも条例本文の
   ;; 明文であって運用の裁量ではない。「標準として条例を定める」という制度は、
   ;; 実際に自治体が標準から外れる余地として使われている。
   ;;
   ;; 政令市は都道府県と別の許可権者だが、実測 14 市すべてが県と同額だった ——
   ;; 「政令市だから違いうる」は制度上正しいが実測では 1 件も差が出ておらず、
   ;; 差が出たのは政令市ではなく**東京都という都道府県**だった。
   ;;
   ;; ⚠ **この 81,000 円を 1 事業者あたりの総額と読むと大きく過小評価する。**
   ;; 許可権者ごとに別の許可が要るので、東京・埼玉・神奈川で営業するなら
   ;; 新規だけで 243,000 円になる。
   :procedure/fee-observations
   [{:fee-observation/id "sanpai-shuun-tokyo-seirei-hyojun"
     :fee-observation/procedure :sanpai-shuun-tokyo
     :fee-observation/authority "国（政令の標準額）"
     :fee-observation/licence-type :sanpai
     :fee-observation/stage :new
     :fee-observation/channel :any
     :fee-observation/rule-form :fixed
     :fee-observation/amount 81000
     :fee-observation/source-kind :instrument
     :fee-observation/basis "地方公共団体の手数料の標準に関する政令（平成12年政令第16号）別表 九十四の項1（廃棄物処理法第十四条第一項の産業廃棄物収集運搬業の許可申請に対する審査 八万千円）"
     :fee-observation/as-of "2026-08-07"
     :fee-observation/source-url "https://laws.e-gov.go.jp/law/412CO0000000016"
     :fee-observation/note "**『国が定めた額』ではなく『標準』**（地方自治法第228条第1項）。同別表は更新 73,000 / 変更 71,000 / 特管 81,000・74,000・72,000 も標準として定める。**東京都はこの標準から外れている**（下記）"}
    {:fee-observation/id "sanpai-shuun-tokyo-hiroshima-jorei"
     :fee-observation/procedure :sanpai-shuun-tokyo
     :fee-observation/authority "広島市（広島市廃棄物の処理及び清掃に関する条例 別表第4）"
     :fee-observation/licence-type :sanpai
     :fee-observation/stage :new
     :fee-observation/channel :any
     :fee-observation/rule-form :fixed
     :fee-observation/amount 81000
     :fee-observation/source-kind :instrument
     :fee-observation/basis "広島市廃棄物の処理及び清掃に関する条例 別表第4"
     :fee-observation/as-of "2026-08-07"
     :fee-observation/source-url "https://www.city.hiroshima.lg.jp/kikaku/houki/reiki_int/reiki_honbun/r500RG00000545.html"
     :fee-observation/note "条例本文＝徴収の一次根拠。**各業種 3 行のみで積替え保管の区分が存在しない** —— 積替えの有無で額が変わらないことが条文レベルで確認できる"}
    {:fee-observation/id "sanpai-shuun-tokyo-new-00-東京都"
     :fee-observation/procedure :sanpai-shuun-tokyo
     :fee-observation/authority "東京都"
     :fee-observation/licence-type :sanpai
     :fee-observation/stage :new
     :fee-observation/channel :any
     :fee-observation/rule-form :fixed
     :fee-observation/amount 81000
     :fee-observation/source-kind :authority-guidance
     :fee-observation/basis "各自治体の手数料条例（政令標準額 81,000 円に一致）"
     :fee-observation/as-of "2026-08-07"
     :fee-observation/source-url "https://www.kankyo.metro.tokyo.lg.jp/resource/industrial_waste/on_processor/license_application"}
    {:fee-observation/id "sanpai-shuun-tokyo-new-01-埼玉県"
     :fee-observation/procedure :sanpai-shuun-tokyo
     :fee-observation/authority "埼玉県"
     :fee-observation/licence-type :sanpai
     :fee-observation/stage :new
     :fee-observation/channel :any
     :fee-observation/rule-form :fixed
     :fee-observation/amount 81000
     :fee-observation/source-kind :authority-guidance
     :fee-observation/basis "各自治体の手数料条例（政令標準額 81,000 円に一致）"
     :fee-observation/as-of "2026-08-07"
     :fee-observation/source-url "https://www.pref.saitama.lg.jp/a0506/kurashi/gomi/sangyo/shushuunpan/index.html"
     :fee-observation/note "更新 73,000 / 変更 71,000（特管 81,000 / 74,000 / 72,000）"}
    {:fee-observation/id "sanpai-shuun-tokyo-new-02-静岡県"
     :fee-observation/procedure :sanpai-shuun-tokyo
     :fee-observation/authority "静岡県"
     :fee-observation/licence-type :sanpai
     :fee-observation/stage :new
     :fee-observation/channel :any
     :fee-observation/rule-form :fixed
     :fee-observation/amount 81000
     :fee-observation/source-kind :authority-guidance
     :fee-observation/basis "各自治体の手数料条例（政令標準額 81,000 円に一致）"
     :fee-observation/as-of "2026-08-07"
     :fee-observation/source-url "https://www.pref.shizuoka.jp/kurashikankyo/recycle/sangyohaikibutsu/1049463/1017727.html"
     :fee-observation/note "更新 73,000 / 変更 71,000"}
    {:fee-observation/id "sanpai-shuun-tokyo-new-03-大阪府"
     :fee-observation/procedure :sanpai-shuun-tokyo
     :fee-observation/authority "大阪府"
     :fee-observation/licence-type :sanpai
     :fee-observation/stage :new
     :fee-observation/channel :any
     :fee-observation/rule-form :fixed
     :fee-observation/amount 81000
     :fee-observation/source-kind :authority-guidance
     :fee-observation/basis "各自治体の手数料条例（政令標準額 81,000 円に一致）"
     :fee-observation/as-of "2026-08-07"
     :fee-observation/source-url "https://www.pref.osaka.lg.jp/o120060/sangyohaiki/tetuduki/shorigyoukyokasinsei.html"
     :fee-observation/note "大阪府環境農林水産行政事務手数料条例第18条に基づく旨を明記。**積替え保管ありは別ページで運用されているが額は完全に同一**"}
    {:fee-observation/id "sanpai-shuun-tokyo-new-04-愛知県"
     :fee-observation/procedure :sanpai-shuun-tokyo
     :fee-observation/authority "愛知県"
     :fee-observation/licence-type :sanpai
     :fee-observation/stage :new
     :fee-observation/channel :any
     :fee-observation/rule-form :fixed
     :fee-observation/amount 81000
     :fee-observation/source-kind :authority-guidance
     :fee-observation/basis "各自治体の手数料条例（政令標準額 81,000 円に一致）"
     :fee-observation/as-of "2026-08-07"
     :fee-observation/source-url "https://www.pref.aichi.jp/site/gyoute/12050.html"
     :fee-observation/note "積替えの有無で区分なし"}
    {:fee-observation/id "sanpai-shuun-tokyo-new-05-北海道"
     :fee-observation/procedure :sanpai-shuun-tokyo
     :fee-observation/authority "北海道"
     :fee-observation/licence-type :sanpai
     :fee-observation/stage :new
     :fee-observation/channel :any
     :fee-observation/rule-form :fixed
     :fee-observation/amount 81000
     :fee-observation/source-kind :authority-guidance
     :fee-observation/basis "各自治体の手数料条例（政令標準額 81,000 円に一致）"
     :fee-observation/as-of "2026-08-07"
     :fee-observation/source-url "https://www.pref.hokkaido.lg.jp/ks/jss/top_page/yousiki_H291001.html"
     :fee-observation/note "額は手引き PDF の別紙参考例にのみ記載"}
    {:fee-observation/id "sanpai-shuun-tokyo-new-06-神奈川県"
     :fee-observation/procedure :sanpai-shuun-tokyo
     :fee-observation/authority "神奈川県"
     :fee-observation/licence-type :sanpai
     :fee-observation/stage :new
     :fee-observation/channel :any
     :fee-observation/rule-form :fixed
     :fee-observation/amount 81000
     :fee-observation/source-kind :authority-guidance
     :fee-observation/basis "各自治体の手数料条例（政令標準額 81,000 円に一致）"
     :fee-observation/as-of "2026-08-07"
     :fee-observation/source-url "https://www.pref.kanagawa.jp/documents/13976/2_sinnki_tebiki.pdf"
     :fee-observation/note "更新 73,000 / 変更 71,000 は別 PDF"}
    {:fee-observation/id "sanpai-shuun-tokyo-new-07-福岡県"
     :fee-observation/procedure :sanpai-shuun-tokyo
     :fee-observation/authority "福岡県"
     :fee-observation/licence-type :sanpai
     :fee-observation/stage :new
     :fee-observation/channel :any
     :fee-observation/rule-form :fixed
     :fee-observation/amount 81000
     :fee-observation/source-kind :authority-guidance
     :fee-observation/basis "各自治体の手数料条例（政令標準額 81,000 円に一致）"
     :fee-observation/as-of "2026-08-07"
     :fee-observation/source-url "https://www.pref.fukuoka.lg.jp/contents/sanpaishinsei.html"
     :fee-observation/note "額は電子申請サービスの様式 zip 内 PDF にのみ記載"}
    {:fee-observation/id "sanpai-shuun-tokyo-new-08-横浜市"
     :fee-observation/procedure :sanpai-shuun-tokyo
     :fee-observation/authority "横浜市"
     :fee-observation/licence-type :sanpai
     :fee-observation/stage :new
     :fee-observation/channel :any
     :fee-observation/rule-form :fixed
     :fee-observation/amount 81000
     :fee-observation/source-kind :authority-guidance
     :fee-observation/basis "各自治体の手数料条例（政令標準額 81,000 円に一致）"
     :fee-observation/as-of "2026-08-07"
     :fee-observation/source-url "https://www.city.yokohama.lg.jp/business/bunyabetsu/gomi-recycle/sangyo/shori/01kyoka.files/0096_20260330.pdf"
     :fee-observation/note "積替えあり/なしで手続フローは分けるが**手数料表は 1 本**"}
    {:fee-observation/id "sanpai-shuun-tokyo-new-09-名古屋市"
     :fee-observation/procedure :sanpai-shuun-tokyo
     :fee-observation/authority "名古屋市"
     :fee-observation/licence-type :sanpai
     :fee-observation/stage :new
     :fee-observation/channel :any
     :fee-observation/rule-form :fixed
     :fee-observation/amount 81000
     :fee-observation/source-kind :authority-guidance
     :fee-observation/basis "各自治体の手数料条例（政令標準額 81,000 円に一致）"
     :fee-observation/as-of "2026-08-07"
     :fee-observation/source-url "https://www.city.nagoya.jp/jigyou/gomi/1026239/1026273/1026286.html"}
    {:fee-observation/id "sanpai-shuun-tokyo-new-10-豊田市中核市"
     :fee-observation/procedure :sanpai-shuun-tokyo
     :fee-observation/authority "豊田市（中核市）"
     :fee-observation/licence-type :sanpai
     :fee-observation/stage :new
     :fee-observation/channel :any
     :fee-observation/rule-form :fixed
     :fee-observation/amount 81000
     :fee-observation/source-kind :authority-guidance
     :fee-observation/basis "各自治体の手数料条例（政令標準額 81,000 円に一致）"
     :fee-observation/as-of "2026-08-07"
     :fee-observation/source-url "https://www.city.toyota.aichi.jp/jigyousha/tetsuzuki/haikibutsu/1021747/1004217.html"
     :fee-observation/note "同一県内の別許可権者だが愛知県・名古屋市と同額"}
    {:fee-observation/id "sanpai-shuun-tokyo-new-11-大阪市"
     :fee-observation/procedure :sanpai-shuun-tokyo
     :fee-observation/authority "大阪市"
     :fee-observation/licence-type :sanpai
     :fee-observation/stage :new
     :fee-observation/channel :any
     :fee-observation/rule-form :fixed
     :fee-observation/amount 81000
     :fee-observation/source-kind :authority-guidance
     :fee-observation/basis "各自治体の手数料条例（政令標準額 81,000 円に一致）"
     :fee-observation/as-of "2026-08-07"
     :fee-observation/source-url "https://www.city.osaka.lg.jp/kankyo/cmsfiles/contents/0000009/9764/r1_0_3.pdf"}
    {:fee-observation/id "sanpai-shuun-tokyo-new-12-札幌市"
     :fee-observation/procedure :sanpai-shuun-tokyo
     :fee-observation/authority "札幌市"
     :fee-observation/licence-type :sanpai
     :fee-observation/stage :new
     :fee-observation/channel :any
     :fee-observation/rule-form :fixed
     :fee-observation/amount 81000
     :fee-observation/source-kind :authority-guidance
     :fee-observation/basis "各自治体の手数料条例（政令標準額 81,000 円に一致）"
     :fee-observation/as-of "2026-08-07"
     :fee-observation/source-url "https://www3.city.sapporo.jp/download/shinsei/search/procedure_view.asp?ProcID=1227"}
    {:fee-observation/id "sanpai-shuun-tokyo-new-13-福岡市"
     :fee-observation/procedure :sanpai-shuun-tokyo
     :fee-observation/authority "福岡市"
     :fee-observation/licence-type :sanpai
     :fee-observation/stage :new
     :fee-observation/channel :any
     :fee-observation/rule-form :fixed
     :fee-observation/amount 81000
     :fee-observation/source-kind :authority-guidance
     :fee-observation/basis "各自治体の手数料条例（政令標準額 81,000 円に一致）"
     :fee-observation/as-of "2026-08-07"
     :fee-observation/source-url "https://www.city.fukuoka.lg.jp/kankyo/sanhai/hp/sangyouhaikibutu/syorisidougakari/documents/syuuun_kyokashinsei_R0509_4.pdf"}
    {:fee-observation/id "sanpai-shuun-tokyo-new-14-北九州市"
     :fee-observation/procedure :sanpai-shuun-tokyo
     :fee-observation/authority "北九州市"
     :fee-observation/licence-type :sanpai
     :fee-observation/stage :new
     :fee-observation/channel :any
     :fee-observation/rule-form :fixed
     :fee-observation/amount 81000
     :fee-observation/source-kind :authority-guidance
     :fee-observation/basis "各自治体の手数料条例（政令標準額 81,000 円に一致）"
     :fee-observation/as-of "2026-08-07"
     :fee-observation/source-url "https://www.city.kitakyushu.lg.jp/contents/924_11153.html"}
    {:fee-observation/id "sanpai-shuun-tokyo-new-15-川崎市"
     :fee-observation/procedure :sanpai-shuun-tokyo
     :fee-observation/authority "川崎市"
     :fee-observation/licence-type :sanpai
     :fee-observation/stage :new
     :fee-observation/channel :any
     :fee-observation/rule-form :fixed
     :fee-observation/amount 81000
     :fee-observation/source-kind :authority-guidance
     :fee-observation/basis "各自治体の手数料条例（政令標準額 81,000 円に一致）"
     :fee-observation/as-of "2026-08-07"
     :fee-observation/source-url "https://www.city.kawasaki.jp/300/cmsfiles/contents/0000060/60482/202604(2)shinseinotebiki.pdf"}
    {:fee-observation/id "sanpai-shuun-tokyo-new-16-京都市"
     :fee-observation/procedure :sanpai-shuun-tokyo
     :fee-observation/authority "京都市"
     :fee-observation/licence-type :sanpai
     :fee-observation/stage :new
     :fee-observation/channel :any
     :fee-observation/rule-form :fixed
     :fee-observation/amount 81000
     :fee-observation/source-kind :authority-guidance
     :fee-observation/basis "各自治体の手数料条例（政令標準額 81,000 円に一致）"
     :fee-observation/as-of "2026-08-07"
     :fee-observation/source-url "https://sanpai.city.kyoto.lg.jp/trader_information/license/shinseitesuuryou/"}
    {:fee-observation/id "sanpai-shuun-tokyo-new-17-神戸市"
     :fee-observation/procedure :sanpai-shuun-tokyo
     :fee-observation/authority "神戸市"
     :fee-observation/licence-type :sanpai
     :fee-observation/stage :new
     :fee-observation/channel :any
     :fee-observation/rule-form :fixed
     :fee-observation/amount 81000
     :fee-observation/source-kind :authority-guidance
     :fee-observation/basis "各自治体の手数料条例（政令標準額 81,000 円に一致）"
     :fee-observation/as-of "2026-08-07"
     :fee-observation/source-url "https://www.city.kobe.lg.jp/a84526/business/kankyotaisaku/industry/shuuun-sinki.html"
     :fee-observation/note "e-KOBE のカード決済は決済手段であって減額ではない"}
    {:fee-observation/id "sanpai-shuun-tokyo-new-18-仙台市"
     :fee-observation/procedure :sanpai-shuun-tokyo
     :fee-observation/authority "仙台市"
     :fee-observation/licence-type :sanpai
     :fee-observation/stage :new
     :fee-observation/channel :any
     :fee-observation/rule-form :fixed
     :fee-observation/amount 81000
     :fee-observation/source-kind :authority-guidance
     :fee-observation/basis "各自治体の手数料条例（政令標準額 81,000 円に一致）"
     :fee-observation/as-of "2026-08-07"
     :fee-observation/source-url "https://www.city.sendai.jp/shido-jigyo/jigyosha/kankyo/haikibutsu/haikibutsu/todokede/documents/syuungyou_sinsei_tebiki_202506.pdf"}
    {:fee-observation/id "sanpai-shuun-tokyo-new-19-さいたま市"
     :fee-observation/procedure :sanpai-shuun-tokyo
     :fee-observation/authority "さいたま市"
     :fee-observation/licence-type :sanpai
     :fee-observation/stage :new
     :fee-observation/channel :any
     :fee-observation/rule-form :fixed
     :fee-observation/amount 81000
     :fee-observation/source-kind :authority-guidance
     :fee-observation/basis "各自治体の手数料条例（政令標準額 81,000 円に一致）"
     :fee-observation/as-of "2026-08-07"
     :fee-observation/source-url "https://www.city.saitama.lg.jp/001/006/008/002/005/p055978.html"
     :fee-observation/note "様式は積替えあり/なしで分けるが**手数料表は分けていない**"}
    {:fee-observation/id "sanpai-shuun-tokyo-new-20-千葉市"
     :fee-observation/procedure :sanpai-shuun-tokyo
     :fee-observation/authority "千葉市"
     :fee-observation/licence-type :sanpai
     :fee-observation/stage :new
     :fee-observation/channel :any
     :fee-observation/rule-form :fixed
     :fee-observation/amount 81000
     :fee-observation/source-kind :authority-guidance
     :fee-observation/basis "各自治体の手数料条例（政令標準額 81,000 円に一致）"
     :fee-observation/as-of "2026-08-07"
     :fee-observation/source-url "https://www.city.chiba.jp/kankyo/junkan/sangyohaikibutsu/documents/shuuntebiki202604.pdf"
     :fee-observation/note "収入証紙は令和8年3月31日廃止"}
    {:fee-observation/id "sanpai-shuun-tokyo-tokyo-renewal-no-storage"
     :fee-observation/procedure :sanpai-shuun-tokyo
     :fee-observation/authority "東京都"
     :fee-observation/licence-type :sanpai-no-storage
     :fee-observation/stage :renewal
     :fee-observation/channel :any
     :fee-observation/rule-form :fixed
     :fee-observation/amount 42000
     :fee-observation/source-kind :instrument
     :fee-observation/basis "東京都廃棄物条例（平成4年東京都条例第140号）別表 十一の項"
     :fee-observation/as-of "2026-08-07"
     :fee-observation/source-url "https://www.reiki.metro.tokyo.lg.jp/reiki/reiki_honbun/g101RG00001019.html"
     :fee-observation/note "★**全国で唯一の標準からの逸脱。** 政令標準 73,000 円に対し 42,000 円（42% 引き）。条例本文に『事業の範囲に積替え又は保管を含むものにあつては七万三千円、含まないものにあつては四万二千円』と明記されており、運用の裁量ではない。**新規では積替えの有無で額が変わらないのに、更新では変わる**"}
    {:fee-observation/id "sanpai-shuun-tokyo-tokyo-renewal-with-storage"
     :fee-observation/procedure :sanpai-shuun-tokyo
     :fee-observation/authority "東京都"
     :fee-observation/licence-type :sanpai-with-storage
     :fee-observation/stage :renewal
     :fee-observation/channel :any
     :fee-observation/rule-form :fixed
     :fee-observation/amount 73000
     :fee-observation/source-kind :instrument
     :fee-observation/basis "東京都廃棄物条例 別表 十一の項"
     :fee-observation/as-of "2026-08-07"
     :fee-observation/source-url "https://www.reiki.metro.tokyo.lg.jp/reiki/reiki_honbun/g101RG00001019.html"
     :fee-observation/note "積替え保管を含む場合は政令標準どおり"}
    {:fee-observation/id "sanpai-shuun-tokyo-tokyo-tokubetsu-renewal-no-storage"
     :fee-observation/procedure :sanpai-shuun-tokyo
     :fee-observation/authority "東京都（特別管理産業廃棄物）"
     :fee-observation/licence-type :tokubetsu-kanri-no-storage
     :fee-observation/stage :renewal
     :fee-observation/channel :any
     :fee-observation/rule-form :fixed
     :fee-observation/amount 43000
     :fee-observation/source-kind :instrument
     :fee-observation/basis "東京都廃棄物条例 別表 十一の項"
     :fee-observation/as-of "2026-08-07"
     :fee-observation/source-url "https://www.reiki.metro.tokyo.lg.jp/reiki/reiki_honbun/g101RG00001019.html"
     :fee-observation/note "政令標準 74,000 円からの逸脱"}
    {:fee-observation/id "sanpai-shuun-tokyo-tokyo-change"
     :fee-observation/procedure :sanpai-shuun-tokyo
     :fee-observation/authority "東京都"
     :fee-observation/licence-type :sanpai
     :fee-observation/stage :change
     :fee-observation/channel :any
     :fee-observation/rule-form :fixed
     :fee-observation/amount 71000
     :fee-observation/source-kind :authority-guidance
     :fee-observation/basis "東京都環境局の手続案内（政令標準額 71,000 円に一致）"
     :fee-observation/as-of "2026-08-07"
     :fee-observation/source-url "https://www.kankyo.metro.tokyo.lg.jp/resource/industrial_waste/on_processor/license_application"
     :fee-observation/note "**更新より安い。** 最安は更新ではなく変更許可"}
    {:fee-observation/id "sanpai-shuun-tokyo-saitama-renewal"
     :fee-observation/procedure :sanpai-shuun-tokyo
     :fee-observation/authority "埼玉県"
     :fee-observation/licence-type :sanpai
     :fee-observation/stage :renewal
     :fee-observation/channel :any
     :fee-observation/rule-form :fixed
     :fee-observation/amount 73000
     :fee-observation/source-kind :authority-guidance
     :fee-observation/basis "埼玉県の手続案内（政令標準額 73,000 円に一致）"
     :fee-observation/as-of "2026-08-07"
     :fee-observation/source-url "https://www.pref.saitama.lg.jp/a0506/kurashi/gomi/sangyo/shushuunpan/index.html"
     :fee-observation/note "東京都と隣接しながら減額なし。実測した 21 自治体すべてが標準どおりで、外れたのは東京都だけ"}]

   :procedure/standard-period-days {:value 60
                                    :verify (schema/unverified "東京都環境局の標準処理期間の公表値を確認")}
   :procedure/valid-years 5

   ;; ITAD(PC 廃棄)で運搬する産業廃棄物の品目(事業計画に記載)
   :procedure/waste-categories
   [{:id :waste-plastics :name "廃プラスチック類" :itad-note "PC 筐体・ケーブル被覆"}
    {:id :metal-scrap :name "金属くず" :itad-note "シャーシ・HDD・電源ユニット"}
    {:id :glass-ceramic :name "ガラスくず・コンクリートくず及び陶磁器くず" :itad-note "ディスプレイパネル・基板ガラス"}]

   :procedure/requirements
   [{:requirement/id :jw-course
     :requirement/name "講習会修了"
     :requirement/detail "（公財）日本産業廃棄物処理振興センター（JWセンター）の産業廃棄物処理業講習会『収集・運搬課程（新規）』を、申請者（法人の場合は代表者・役員または政令使用人）が修了していること。修了証は申請書類。"
     :requirement/blocking? true}
    {:requirement/id :financial-basis
     :requirement/name "経理的基礎"
     :requirement/detail "事業を的確かつ継続して行うに足りる経理的基礎（債務超過でない等）。直前3年分の貸借対照表・損益計算書・法人税納税証明書で疎明する。"
     :requirement/blocking? true}
    {:requirement/id :not-disqualified
     :requirement/name "欠格要件非該当"
     :requirement/detail "法14条5項2号（法7条5項4号準用）の欠格要件（一定の刑・暴力団関係・許可取消歴等）に、法人・役員・政令使用人・5%以上株主が該当しないこと。"
     :requirement/blocking? true}
    {:requirement/id :business-plan
     :requirement/name "事業計画・運搬施設"
     :requirement/detail "運搬する産業廃棄物の種類と数量、運搬車両（車検証・写真）、運搬容器、駐車場の使用権原、飛散・流出防止措置を事業計画として示す。"
     :requirement/blocking? true}]

   :procedure/documents
   [{:document/id :application-form :document/name "許可申請書（都様式）" :document/who :company}
    {:document/id :business-plan-outline :document/name "事業計画の概要（品目・数量・運搬先）" :document/who :company}
    {:document/id :teikan :document/name "定款の写し" :document/who :company}
    {:document/id :touki :document/name "履歴事項全部証明書（登記事項証明書）" :document/who :company}
    {:document/id :yakuin-juminhyo :document/name "役員等の住民票（本籍記載・マイナンバー無し）" :document/who :officers}
    {:document/id :yakuin-seinen :document/name "役員等の登記されていないことの証明書" :document/who :officers}
    {:document/id :zaimu-3y :document/name "直前3年分の貸借対照表・損益計算書・株主資本等変動計算書" :document/who :company}
    {:document/id :nouzei :document/name "法人税の納税証明書（その1）直前3年分" :document/who :company}
    {:document/id :jw-certificate :document/name "JWセンター講習会修了証の写し" :document/who :officers}
    {:document/id :vehicle :document/name "運搬車両の車検証写し・車両写真" :document/who :company}
    {:document/id :containers :document/name "運搬容器の写真" :document/who :company}
    {:document/id :parking :document/name "駐車場の使用権原を示す書類（賃貸借契約書等）" :document/who :company}]

   :procedure/steps
   [{:step/id :verify-current-rules :step/order 1 :step/requires-human true
     :step/title "最新の手数料・様式・受付方法を東京都環境局で確認"
     :step/detail "収録値は標準値。申請の手引き最新版を取得し、様式改定・電子申請可否を確認する。"
     :step/errand {:kind :verify-authority-info :draft-via :tayori
                   :evidence-schema {:authority :string :verified :map
                                     :source :string :date :iso-date}}}
    {:step/id :resolve-legal-questions :step/order 2 :step/requires-human true
     :step/title "事業スキームの法的整理（行政書士相談）"
     :step/detail ":legal-questions を行政書士に諮り、宅配回収 ITAD で本許可が必要なスキームかを確定させる。"
     :step/errand {:kind :consult-professional :draft-via :tayori
                   :evidence-schema {:office :string :date :iso-date
                                     :resolutions :map}}}
    {:step/id :book-jw-course :step/order 3 :step/requires-human true
     :step/title "JWセンター講習会（収集・運搬課程 新規）の受講予約と受講"
     :step/detail "受講者 = 代表者または役員。人気日程は埋まるため最優先で予約。修了試験合格まで。"
     :step/errand {:kind :book-course :draft-via :koyomi
                   :evidence-schema {:provider :keyword :course :string :date :iso-date
                                     :attendee :string :confirmation-no :string}}}
    {:step/id :collect-documents :step/order 4 :step/requires-human false
     :step/title "申請書類一式の収集（:procedure/documents のチェックリスト消化）"
     :step/errand {:kind :collect-documents :draft-via nil
                   :evidence-schema {:doc :keyword :obtained-date :iso-date}}}
    {:step/id :prepare-business-plan :step/order 5 :step/requires-human false
     :step/title "事業計画書の作成（品目・数量・車両・容器・駐車場）"}
    {:step/id :submit :step/order 6 :step/requires-human true
     :step/title "申請書提出と手数料納付"
     :step/detail "提出は human gate。控えと受付番号を台帳に記録する。"}
    {:step/id :respond-to-review :step/order 7 :step/requires-human true
     :step/title "審査対応（補正指示への応答）"}]

   ;; 結論を出さずに保持する法的論点(行政書士・弁護士確認事項)
   :procedure/legal-questions
   [{:question/id :haikibutsu-gaitousei
     :question/title "宅配回収 ITAD の廃棄物該当性"
     :question/detail "有償買取（リユース目的）は古物営業の範囲で廃棄物処理法の外になりうる一方、処分費を収受して引き取る PC は産業廃棄物。総合判断説（昭和52年通知系）の下でスキーム毎に判定が分かれる。"
     :question/status :open}
    {:question/id :unsou-itaku
     :question/title "宅配便（貨物運送事業者）による回収の扱い"
     :question/detail "排出事業者が運送事業者へ運送委託する形の宅配回収で、当社に収集運搬許可が必要か（自社は運搬せず処分委託・消去のみを担うスキームの可否）。"
     :question/status :open}
    {:question/id :kuiki
     :question/title "許可の地域範囲"
     :question/detail "収集運搬許可は積む場所・降ろす場所の都道府県ごとに必要。全国宅配回収の場合にどの都道府県の許可を取るか（または運送委託で回避するか）はスキーム確定後に決める。"
     :question/status :open}]})
