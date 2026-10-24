# denchu

**電柱広告（utility-pole advertising）の在庫・窓口・料金・出稿を扱う純 `.cljc`
ドメインライブラリ。**

「電柱」は媒体の名前であってメタファではない。この repo が答えるのは 4 つ:

| 問い | ns |
|---|---|
| その座標に柱があるか（複数の観測源をどう1本に束ねるか） | `denchu.pole` |
| その柱にどんな掲出面がありうるか | `denchu.slot` |
| その柱の広告を**誰に申し込むか**（媒体社／指定代理店と問い合わせ先） | `denchu.media` |
| 所有者が未確定でも**誰に聞けばよいか**（供給区域からの候補） | `denchu.area` |
| いくらか（**常に参考値**）／法令上何が要るか／出稿はどう進むか | `denchu.pricing` `denchu.facts` `denchu.order` |

観測の収集そのものは持たない。それは `loop-denchu-survey`（orchestrator）が
`org-openstreetmap-overpass` と `com-mapillary-graph-api` を叩いて行い、
ここには正規化済みの観測が入ってくる。

## この repo が意図的に**持たない**もの

日本の電柱広告は open inventory ではない。柱は電力会社・通信会社の設備で、
広告の販売は所有者が指定した代理店を通してしか行われない。したがって:

- **空き在庫数を推定する関数が無い。** 1本の柱に何面掛かっているか、空きが
  あるかは所有者と代理店だけが知っている。推定した空き数は必ず「在庫がある」
  という嘘になる。`denchu.slot/candidate-slots` は全面 `:availability :unknown`
  を返し、そこから出る経路は `apply-agency-answer`（回答元の記録を必須にする）
  ただ1本。
- **確定価格が無い。** `denchu.pricing/quote-order` の戻り値は必ず
  `:quote/confidence :indicative`。地域区分が未指定なら `:quote/total nil` と
  `:quote/unknowns` を返し、**平均や中央値で埋めない**。
- **掲出可否を幾何情報から導かない。** `:pole/ad-eligible` は全件 `:unknown`
  から始まる。OSM にも Mapillary にも「この柱に広告を出せるか」は書かれていない。
- **所有者を推測しない。** `operator` 相当のタグに実社名がある時だけ決まる。

## 所有者が未確定でも問い合わせは組める（`denchu.area`）

実測では OSM の柱の大半に `operator` が無く、261 本中 0 本しか所有者が決まらな
かった。ここで詰まると問い合わせ 1 通も出せない。

だが**制度的事実**がある: 一般送配電事業者の供給区域と NTT 東西の営業区域は
法令・会社公表で決まっており、ある県に柱があるならその所有者は限られた候補の
いずれか。これは座標からの推測ではなく区域の定義そのもの。したがって:

- `denchu.area/candidates` が管轄（ISO 3166-2:JP、**survey が宣言した値**。座標から
  逆引きしない）から候補事業者を返す
- `denchu.media/contact-route` が `:candidate-by-area` を返し、候補代理店を出す
- `denchu.order` は候補ルートでの問い合わせを許し、`inquiry-draft` は
  **設備所有者の確認そのものを第一の問い合わせ事項にする** — 推定社名を断定として
  書くと相手が追認して誤った所有者が確定してしまう
- **`:pole/owner` は `:unknown` のまま。候補は柱ではなく経路に載る**

境界は畳まない。静岡県は富士川で電力が東電PG／中電PGに分かれ、通信は NTT 西日本
だが熱海市・裾野市の一部が東日本 — こういう県は候補を複数返す（片方に畳むと畳んだ
側の柱で必ず間違う）。福井（嶺南）・三重・岐阜・兵庫の一部も同様に記録している。

## 法令構造（`denchu.facts`、取り違えると設計が嘘になる点）

1. 屋外広告物法に基づき、**各自治体の屋外広告物条例**が許可を出す（国ではない）。
2. 多くの条例は電柱・街路灯柱への**貼り紙・貼り札・広告旗を禁止物件**として
   列挙する。一方、電力/通信会社の柱に所定の手続きで付ける巻付・袖看板は許可
   対象として別に扱われる。**「電柱広告は条例で禁止」と要約しない** — 禁止
   されているのは無断の貼付物である。
3. 道路上空に突き出す形態（袖看板）は道路法の**道路占用許可**が別途関わる。
4. 実務上これらの申請は代理店が代行する（テルウェル東日本は道路占用申請と
   NTT電柱使用許可申請を自社および販売会社が行うと明記）。代行される事実は
   要件が消えることを意味しない。

`denchu.facts/coverage` は収録管轄が現在 JPN 1 件であることを申告する。未収録の
管轄は spec-basis **無し**であって、advisor が要件を創作してよいという意味ではない。

## 出稿ステートマシン（`denchu.order`）

```
:draft → :quoted → :inquiry-proposed → :inquiry-sent → :agency-confirmed
       → :permit-filed → :installed → :active → :ended
                    ↘ :held / :rejected
```

workspace の Actors 不変条件をそのまま持ち込む — 提案する側と censor する側を
分け、`violations` が空でなければ `advance` は状態を変えない。主な不変条件:

- 参考見積なしに問い合わせを組まない
- 窓口も区域候補も無い柱に問い合わせを組まない（`no reachable agency`）
- **代理店の回答なしに実額を主張しない**（`:agency-confirmed` の前に実額は存在しない）
- 管轄の spec-basis と必要証跡が揃うまで許可申請に進まない
- 袖看板は道路占用の判定記録がなければ許可申請に進まない
- `:inquiry-sent` は `:external-send` risk が付く（承認キューに載る印）

## 使う

```clojure
(require '[denchu.pole :as pole] '[denchu.media :as media]
         '[denchu.pricing :as pricing] '[denchu.order :as order])

(def poles (:poles (pole/fuse observations {:radius-m 8.0})))
(media/contact-route (first poles))
;; => {:route/status :routable :route/agencies [{:agency/legal-name "東電タウンプランニング株式会社" ...}]}

(pricing/quote-order {:agency-rate :telwel-east-higashikanto :zone :A :units 2 :months 12})
;; => {:quote/total 97200 :quote/tax :excluded :quote/confidence :indicative ...}
```

## 料金表の出典（`denchu.pricing/rate-cards`）

| 代理店 | 公開値 | 出典 |
|---|---|---|
| 東電タウンプランニング（東電PG柱） | 月々2,640円（税込）〜、地域により異なる。製作費非公開 | <https://www.ttplan.co.jp/service/ad_pole/> |
| テルウェル東日本 東関東支店（NTT東柱・千葉） | 月額 A2,800／B2,600／C2,400／D2,200／E2,000 円（税抜、2025-06-01改定）、製作費15,000円（税抜、取付込） | <https://www.telwel-east.co.jp/denchu-koukoku/fee/> |

いずれも `:rate/as-of "2026-08-04"`。ここに無い代理店の料金は **不明であって 0 ではない**。

## テスト

```bash
kbb --backend sci --classpath src:test test/run.cljk     # 47 tests / 256 assertions
```

第一の runtime は ClojureScript / nbb。`.kotoba` に載せていないのは、柱→観測列→
タグ map という入れ子の値が要るのに recursive logical values が W4 待ちであるため
（現在地であって到達目標ではない）。

MIT。
