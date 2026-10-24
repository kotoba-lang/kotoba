# shomen — operator quickstart

カタログを**引く**・**足す**・**確度を上げる**人のための手順。下の各コマンドは
2026-09-23 に `58b8378`（この文書を足す直前の main）で実際に走らせたもので、
出力はそのとき印字されたものをそのまま写してある。

前提は `kbb` が PATH に在ること（依存はゼロなので他に要るものは無い）。作業は
repo の root で行う。

## 1. suite が緑であることを確かめる

```bash
kbb --backend sci --classpath src:test run_tests.cljk
```

```text
0 failures, 0 errors.

PASS — 21 tests, 61 assertions, 0 failures, 0 errors
```

赤なら exit 1（`FAIL — …` 行）。**触る前に緑でなければ、自分の変更の可否を判定
できない**ので、先にそれを直すか報告する。

⚠ 失敗行の file 表示は `run_tests.cljk:<行>` になるが、行番号は**テスト側の
ファイル**のもの（例: `run_tests.cljk:11` は `test/shomen/catalog_test.cljk` の
11 行目）。`run_tests.cljk` を開いても該当行は無い。

## 2. カタログの現在地を 1 画面で見る

```bash
kbb --backend sci --classpath src -e '(require (quote [shomen.catalog :as c]) (quote [shomen.coverage :as v])) (print (v/report c/entries))'
```

```text
shomen catalog: 10 entries
route
  ask-administration    1
  ask-ministry          2
  electronic-now        4
  electronic-soon       1
  unverified            2
confidence
  unverified-seed       10
unverified (route refused, not classified): 2 [:jp-civil-suit-filing :jp-notarial-deed]
undelegable interim (principal must act): 1 [:jp-naturalisation-application]
conform :full ok
```

読み方:

- `unverified` は分類の 1 つではなく**分類を拒否した**件数。電子の道の状態
  （`:e/status`）を測っていない entry で、提言も繋ぎも出ない。ここを減らすのが
  カタログの一番の仕事。
- `undelegable` は出頭・押印・公証が残るため飛脚（`cloud-itonami/hikyaku`）に
  渡せない手続き。本人が行く。
- `conform :full` が `VIOLATIONS n` なら、どこかの entry の形が壊れている（§4）。

## 3. 1 件を引く（下流の actor が受け取るもの）

`-e` の中で `'` を使うと shell の引用と衝突するので、2 行以上はファイルに書いて
渡す:

```bash
cat > /tmp/shomen-q.cljk <<'EOF'
(require '[shomen.catalog :as cat] '[shomen.classify :as c] '[clojure.pprint :refer [pprint]])
(pprint (c/classify (cat/entry :jp-immigration-residence-permission-fee)))
EOF
kbb --backend sci --classpath src /tmp/shomen-q.cljk
```

```text
{:req/id :jp-immigration-residence-permission-fee,
 :route :ask-ministry,
 :remaining [:revenue-stamp],
 :advocacy
 {:target :ministry,
  :channels #{:public-comment :regulatory-reform-hotline},
  :asks "命令等（政令・省令・規則）の改正。意見公募は案の公示中のみ",
  :route :ask-ministry,
  :remaining [:revenue-stamp],
  :legal-bases
  ["出入国管理及び難民認定法 §67（手数料）→ 出入国管理及び難民認定法関係手数料令（収入印紙による納付）"]},
 :interim
 {:delegable? true,
  :blocked [],
  :route :ask-ministry,
  :tasks
  [{:task :receive-principal-documents,
    :note "本人が作成・署名・押印済みの文書を受け取る。飛脚は作成しない"}
   {:task :buy-revenue-stamp,
    :amount-jpy nil,
    :amount-rule
    "手数料令（2025-04 改定: 在留期間更新・在留資格変更 6,000 円、オンライン申請 5,500 円 —— 要確認）。許可時に収入印紙を貼付した手数料納付書を提出"}
   {:task :affix-revenue-stamp,
    :cancel-by :receiving-office,
    :note "消印しない。受理した官署が消印する"}
   {:task :enclose}
   {:task :post,
    :traceable? true,
    :note "追跡できる種別（特定記録・書留・内容証明）。普通郵便にしない"}
   {:task :archive-receipt}]}}
```

`:advocacy` は `cloud-itonami/teigen`（提言）、`:interim` は `cloud-itonami/hikyaku`
（繋ぎ）の入力になる。id の一覧は `(prn (map :req/id cat/entries))`。

## 4. entry を足す前に形を検査する

`shomen.requirement/conform` は**違反を最初の 1 件で止めずに全部返す**。足す entry
を `:full` で通してから `src/shomen/catalog.cljk` の `entries` に入れる。下の例は
既存 entry から出典 URL と印紙の消印者を抜いた下書きで、検査がそれを 2 件とも
名指しすることを見せる（法令の中身を作らないため、既存 entry から削って作った）:

```bash
cat > /tmp/shomen-draft.cljk <<'EOF'
(require '[shomen.catalog :as cat] '[shomen.requirement :as req] '[shomen.classify :as c] '[clojure.pprint :refer [pprint]])
(def draft (-> (cat/entry :jp-immigration-residence-permission-fee)
               (assoc :req/id :draft-example)
               (dissoc :req/source-urls)
               (update :req/fee dissoc :fee/cancel-by)))
(pprint (req/conform [draft] :full))
(def unknown (assoc draft :req/electronic {:e/status :unknown}))
(prn (c/route unknown))
(prn (c/advocacy unknown))
(prn (c/interim unknown))
EOF
kbb --backend sci --classpath src /tmp/shomen-draft.cljk
```

```text
{:level :full,
 :entries 1,
 :violations
 [{:req-id :draft-example,
   :rule :missing-source-urls,
   :detail ":req/source-urls が無い —— 出典の無い記述は検証できない"}
  {:req-id :draft-example,
   :rule :stamp-without-cancel-by,
   :detail
   "収入印紙で納める手続きなのに :fee/cancel-by が無い —— 誰が消印するかを言わない印紙の記述は、印紙を無効にする"}],
 :ok? false}

:unverified
{:refused :unverified, :detail "電子の道の状態が :unknown。調べる前に提言を書かない"}
{:refused :unverified}
```

**電子の道を調べていないなら `{:e/status :unknown}` と書く。** 推測で
`:not-permitted` と書くと、その entry は `:ask-*` に分類され、`teigen` は調べて
いない法令に向けて改正要望を書く。`:unknown` なら上のとおり拒否として下流に届く。

閉じた語彙（`shomen.vocabulary`。これ以外の値は `conform` が拒否する）:

```text
analog-kinds (:notarisation :original-attachment :paper :presence :revenue-stamp :seal)
requirement-sources (:cabinet-order :ministerial-ordinance :none :notice-or-practice :statute)
electronic-statuses (:enacted-not-in-force :in-force :not-permitted :permitted-not-provided :unknown)
confidences (:counsel-verified :maintainer-verified :unverified-seed)
authorities (:court :immigration :legal-affairs-bureau :ministry :municipality :notary :tax-office)
```

（印字: `kbb --backend sci --classpath src -e '(require (quote [shomen.vocabulary :as v])) (doseq [s (quote [analog-kinds requirement-sources electronic-statuses confidences authorities])] (println s (sort (deref (ns-resolve (quote shomen.vocabulary) s)))))'`）

## 5. entry を足したら、テストの件数も一緒に直す

`test/shomen/catalog_test.cljk` は件数（10）と route の内訳を**固定値で**持っている。
entry を足してテストを直さないと suite は赤くなる —— これは意図で、件数が黙って
変わらないようにしている。実測（scratch コピーに 11 件目を足した）:

```text
FAIL in (catalog-conforms) (/private/tmp/shomen-scratch/run_tests.cljk:11)
expected: (= 10 (:entries r))
  actual: (not (= 10 11))
FAIL in (coverage-is-honest) (/private/tmp/shomen-scratch/run_tests.cljk:48)
expected: (= 10 (:entries s))
  actual: (not (= 10 11))
FAIL — 21 tests, 59 assertions, 2 failures, 0 errors
```

既存と同じ `:req/id` で足すと、さらに `catalog-conforms` の `:duplicates` 検査
（12 行目）が落ちる（同じ実測で 3 failures）。直す場所は 11 行目・48 行目の件数と、
新しい entry の route が `unverified` なら 49–50 行目・53 行目の未測定件数。

## 6. 確度を上げる（seed → verified）

一次資料（e-Gov の条文・所管省庁の案内）で entry を確かめたら、その entry の
`:req/confidence` を `:maintainer-verified`（資格者の確認なら `:counsel-verified`）
にし、`:req/verified` を確認した日付に、`:req/source-urls` を実際に読んだ URL にする。

**上げた瞬間 suite は赤くなる**。`all-seed` が「全件 seed」を固定しているため:

```text
FAIL in (all-seed) (/private/tmp/shomen-scratch/run_tests.cljk:16)
seed は seed と名乗る —— 1 件でも verified を名乗ったら、それは検証の記録が要る
expected: (every? (fn* [%1#] (= :unverified-seed (:req/confidence %1#))) cat/entries)
FAIL — 21 tests, 60 assertions, 1 failures, 0 errors
```

そのテストを「verified を名乗る entry の id 集合」と一致する形に書き換えるのが、
検証の記録を残す手順である（どの entry を誰が確かめたかを commit に書く）。§2 の
報告は `confidence` の段で `maintainer-verified 1 / unverified-seed 9` と分けて出す。

`teigen` と `hikyaku` の governor は `:unverified-seed` の entry から live の提出・
発送を起こさない。確度を上げることは、下流が実際に動くための前提である。
