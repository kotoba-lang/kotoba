# kyoninka（許認可）

The closed eight-status transition and explicit human-approval gate also has a
native `.kotoba` kernel. It compiles to restricted JavaScript and Wasm without
a JVM runtime. Procedure text, legal questions, current authority information,
fees, documents, persistence, and external actions remain host-owned CLJC data
and code.

許認可手続きを **procedure-as-data**（Datomic 互換 EDN + 純関数 + 状態機械 +
append-only 台帳イベント）で表すライブラリ。ADR-2607141620（com-junkawasaki/root）。

**2026-08-07 に日本以外へ広げた。** それまでは日本専用で、schema に法域属性が
1 つも無く「日本であること」が暗黙だった（`:procedure/fee-jpy` は通貨を属性名に
焼いていた）。いまは `:procedure/jurisdiction`（ISO 3166-1 alpha-3）が必須で、
手数料は通貨中立（最小単位の整数 + `:minor-unit`）。

| ns | 法域 | 手続き | 根拠法 | 窓口 |
|---|---|---|---|---|
| `kyoninka.sanpai` | JPN | 産業廃棄物収集運搬業許可（東京都・積替え保管なし） | 廃棄物処理法 14条1項 | 東京都環境局 |
| `kyoninka.kobutsu` | JPN | 古物商許可（営業所: 千代田区丸の内） | 古物営業法 3条 | 管轄警察署経由 東京都公安委員会 |
| `kyoninka.gbr-waste-carrier` | GBR（England のみ） | 廃棄物運搬業登録 upper tier | COPA(A) 1989 s.1 + SI 2011/988 Part 8 | Environment Agency（GOV.UK オンライン） |
| `kyoninka.gbr-scrap-metal` | GBR（England and Wales） | スクラップ金属業免許（site / collector） | Scrap Metal Dealers Act 2013 | 地方自治体（council） |
| `kyoninka.deu-abfall-transport` | DEU | 廃棄物収集運搬（§53 届出 / §54 許可） | KrWG §53/§54 + AbfAEV | 州（Land）当局 |

**収録できなかった値は書いていない。** 英国スクラップ金属と独の手数料は
`:amount` を持たない —— 額を決めるのが手続きの外（council / 州）だから。
代表額を選べば残り全部で嘘になる。標準処理期間も、法にも公表にも決定期限が
無い制度が 3 本ある。**空欄は手抜きではなく測定結果**で、`:verify` がその区別を持つ。

## 手数料 —— 額が 1 個でない制度をどう持つか

`:procedure/fee` は「額を決めるのは誰か」を `:set-by :level` で持つ:

| level | 意味 | `:amount` を書けるか |
|---|---|---|
| `:statute` | 額が法令本文にある | ○ |
| `:national-authority` | 国の規制庁が定める。全国一律だが法定ではない | ○ |
| `:statute-standard` | 国が標準額を定め、下位の当局が条例でそれに拠る | ○ |
| `:sub-national` | 各当局が自分で決める。**全国値が存在しない** | ✕ |

実際に引いた額は `:procedure/fee-observations` に**当局ごとの独立した事実**として
置く。**この集合の min/max は制度の幅ではない。** Cheshire East £235 と
Newham £1,089 は「見た 14 council がその範囲だった」でしかなく、外側の額が
無い証拠にはならない。法定の幅（ある州の規則自身が `250–5.000 €` と定めるような
もの）は観測の**中**にだけ置き、その場合は定めている条文を `:basis` で名指しさせる
—— 名指しできない幅は、たいてい複数の当局を畳んだ標本のばらつきである。

### 額の「形」は 5 つある。幅を既定にしない

`:rule-form` が宣言する。ドイツ 16 州の実測がこの形を要求した:

| form | 意味 | 実測 |
|---|---|---|
| `:range` | 両端が定まった幅 | 11 州（BY 250–6.000 €、SL 100–10.000 € 等） |
| `:floor` | 下限のみ、**上限なし** | NI ≥160 €、HH ≥371 € |
| `:ceiling` | 上限のみ、下限なし | MV ≤5.500 € |
| `:fixed` | 定額 | HE のみ（電子 800 € / 紙 1.000 €） |
| `:no-amount-set` | **規則が額を一切定めない** | NRW（純粋な時間手数料） |

**`:no-amount-set` は「調べていない」ではなく「額という形の答えが無い」。**
初版は `:amount` か `[min max]` の 2 択で書いており、この 5 州が表現できなかった。

### 観測は 3 軸 + 出所の種類で持つ

`:licence-type`（何の免許か。法域ごとの語彙を登録制にしている）、`:stage`
（`:new` / `:renewal` / `:change` / `:grant-or-renewal` / `:grant-or-change` /
`:unstated`）、`:channel`（`:electronic` / `:paper` / `:any`）。

- **段階を畳まないのは、14 council のうち 6 つが「Grant/Renewal」を 1 額で示していた**から。
  `:new` と書くとその council が区別していないという事実が消える。`:grant-or-renewal`
  （当局の設計）と `:unstated`（当局が書いていない）も別の値にする。
- **経路を軸にしたのは 4 州が経路で額を変えていた**から。しかも DEU §53 の無料は
  §53 という手続にではなく**電子経路に**付いている（HE の条文は
  「elektronischen Anzeige …wird keine Gebühr erhoben」で紙は 50 €）。
- `:source-kind` が `:instrument`（条文の行項目まで辿れた）/ `:authority-guidance`
  （所管庁の公式表明だが条文に対応づかない）/ `:practice`（運用平均）を分ける。
  **どちらも「公式」だが同格ではない** —— Thüringen はポータルに 250–5.000 € と
  出るが、ThürVwKostOMUEN には §§53/54 の項目自体が無い（条例が 2012 年の
  KrWG 施行に追随せず旧法の Transportgenehmigung のまま）。

軸が効くことは数字で出る: gbr-scrap-metal の 38 観測は素朴には £235〜£1,089
（4.6 倍）に見えるが、**site かつ新規と明記された行だけに絞ると 5 件・
£371〜£804.78（2.2 倍）** で、最安も最高も「段階を書いていない」行だった。

### 実測が既存の記述を 4 件否定した

| 記述 | 実測 |
|---|---|
| 「site 新規 £181（Leeds）」 | Leeds は site/collector を分けていない。£181 は取引種別だけの額 |
| 「NI は AllGO 2.1.35 で平均 ca. 360 €」 | 条文は「時間費用、ただし最低 160 €」。360 € は所管庁 Merkblatt の運用平均 |
| 「HH は 50–1.000 €」 | §54 の値として裏付けが取れず。確認できたのは最低 371 € |
| 「DEU §53 届出は多くの州で無料」 | 無条件無料は Bremen 1 州のみ。13 州は有料 |

日本側も 2 件: **19,000 円 / 81,000 円は「国が定めた額」ではなく政令の標準額**
（地方自治法228条1項、徴収根拠は各自治体の手数料条例）。そして
**「積替え保管ありの新規は 82,000 円」はどの公式資料にも存在しない** ——
新規は 22 自治体すべてが積替えで区別していない。区別が実在するのは
**東京都の更新だけ**（積替えなし 42,000 円 / あり 73,000 円）で、条例本文の明文。

## 設計原則（正直さがコードの形をしている）

1. **標準値には必ず `:verify` フラグ** — 手数料・標準処理期間・様式は改定される。
   「最新の実値を窓口で確認する」ことが全手続きの `:step/order 1` にコードとして
   組み込まれている。収録値をそのまま信じて申請してはいけない。
2. **法的論点は `:legal-questions` として保持し、結論を出さない** — 例: 宅配回収
   ITAD の廃棄物該当性（買取 = 古物営業 vs 廃棄物 = 廃掃法、運送委託の扱い、
   許可の地域範囲）。行政書士確認で `:question/status :resolved` にするまで
   スキームを断定しない。
3. **提出・官庁接触・支払いは human gate** — 状態機械（`schema/transitions`）の
   `:human` 遷移と `:step/requires-human true` の step は `:human-approved true`
   なしに進められない。ライブラリは next-action を**提案するだけ**。
4. **台帳が正** — case map は `progress/replay` で台帳イベントから再構成できる射影。

## 使い方

```clojure
(require '[kyoninka.sanpai :as sanpai]
         '[kyoninka.progress :as p])

(def c (p/new-case sanpai/procedure {:case-id :itad-sanpai :applicant "Gftd Japan株式会社"}))
(p/next-actions sanpai/procedure c)   ; => 最初は必ず「最新の実値確認」「行政書士相談」
(p/checklist sanpai/procedure c)      ; => 書類チェックリスト
(p/summary sanpai/procedure c)        ; => 進行サマリ
(p/advance c {:to :preparing})        ; => {:ok? true :case ...}
```

消費者: `gftdcojp/cloud-itonami` の `cloud_itonami/license.cljc`
（Gftd Japan の 2 case を台帳 `resources/licenses/itad-license-ledger.edn` で進行管理）。

## テスト

```bash
kbb --backend sci --classpath "src:test" test/run_tests.cljk   # 第一経路
kbb -X:test                                   # JVM (compat)
```
