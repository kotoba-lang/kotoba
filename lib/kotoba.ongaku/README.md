# ongaku

BGM selection and license-policy gating for render pipelines — the craft
library split out of gftdcojp's private `ongakuka` actor (ADR-2607023000:
コードは kotoba-lang、職能は cloud-itonami-isco、商売は gftdcojp).

Catalog-agnostic and channel-agnostic: you bring your own catalog EDN. The
library scores candidates by mood and duration, and structurally refuses any
use the asset's license policy forbids (raw public file exposure, AI training,
Content ID / fingerprint registration).

ISCO-08 2652 covers Musicians, Singers **and Composers**, so this library
gates both directions of the same occupation:

| | namespace | gates |
|---|---|---|
| **使い方（下流）** | `ongaku.compose` / `ongaku.policy` | 既製カタログの選定と、その資産のライセンスが禁じる利用 |
| **渡し方（上流）** | `ongaku.rights` / `ongaku.work` / `ongaku.commission` | 受注で譲渡する権利と、約束した納品物 |

Both halves are pure functions over data you bring — no catalog, no client
roster, no business data lives here (ADR-2607023000: 技芸は kotoba-lang、
商売は -ka repo).

## Rights — 持っていない権利は売れない

```clojure
(require '[ongaku.rights :as rights])

;; 既製カタログ資産について studio が持つのは非独占の使用許諾だけ
(rights/validate-grant [(rights/right {:kind :sync :exclusive? false})]
                       (rights/right {:kind :master :exclusive? true}))
;; => [{:problem/type :not-held
;;      :problem/message "保有していない権利は譲渡できない: master(独占) worldwide" ...}]
```

非独占しか持たない権利の独占譲渡、保有地域の外への譲渡、保有期間を超える
譲渡、既発の独占譲渡と地域・期間が重なる二重譲渡も同じく拒否する。

## Work — 作れない物は約束できない

生成パイプラインの出力は音源と stems だけで、譜面も MIDI も DAW セッションも
**そもそも存在しない**。純 AI 生成の作品に「譜面つき」を売ることは守れない
約束なので、受注時に落とす。

```clojure
(require '[ongaku.work :as work])

(work/producible-kinds :authored)   ;; => #{:master-audio :stems :midi :score :session}
(work/producible-kinds :generated)  ;; => #{:master-audio :stems}
```

`:generated` / `:hybrid` の作品は `:work/model-id` と `:work/disclosure` を
持たなければ納品できない（`ai.gftd.ongakuka.track` の `modelId` と同じ要求）。

## Commission

`ongaku.commission/validate` は上の2つを受注1件に対してまとめて回し、問題の
vector（または `nil`）を返す。**その問題を hard reject にするか人間承認に
回すかは決めない** —— それは職能側の governor の判断
（`cloud-itonami-isco-2652` の `music-practice.governor`）。技芸は事実を返し、
職能が処分を決める。

## Contract

```clojure
(require '[ongaku.compose :as compose])

(compose/compose catalog {:channel-id "demo"
                          :mood :calm
                          :duration/sec 120})
;; => {:ongaku/plan :plan/background-music
;;     :asset/id "..." :asset/path "..." :credit/text "..."
;;     :policy/render-only? true :policy/raw-public-access? false ...}
```

The returned plan carries a **local asset path and credit text, never a public
URL**. Callers mux the file into their render and publish the credit.

## Catalog shape

```clojure
{:ongaku.catalog/version 1
 :ongaku.catalog/assets
 [{:asset/id "..." :asset/title "..." :asset/local-path "..."
   :audio/duration-sec 180.0
   :music/moods #{:calm} :music/channels #{"demo"}
   :credit/text "BGM: ... / ..."
   :policy/render-only? true
   :policy/raw-public-access? false
   :policy/ai-training? false
   :policy/content-id-registration? false}]}
```

The legacy `:ongakuka.catalog/assets` key is also read. Production catalogs
(asset lists, channel rosters) are business data and stay in their private
repos; tests here use a synthetic fixture.

## Holdings — 使用許諾は「渡せる権利」ではない

`ongaku.policy` が答えるのは『自分がどう使ってよいか』、`ongaku.holdings` が
答えるのは『**依頼主に何を渡せるか**』。この 2 つは別物で、**使用許諾を
持っていることは、それを他人に渡せることを意味しない。**

```clojure
(require '[ongaku.holdings :as holdings])

(holdings/grantable-rights dova-asset)      ;; => []  何も渡せない
(holdings/grantable-rights cc-by-asset)     ;; => [非独占 :sync 1 件のみ]
(holdings/grantable-rights {:asset/id "x"}) ;; => []  ライセンス未記載 = fail-closed
```

| license | 渡せるもの | なぜ |
|---|---|---|
| `:license/dova-syndrome-license` | **なし** | 自分の動画等での使用許諾。原盤の再配布・サブライセンスは認められていない |
| `:license/cc-by-4.0` | 非独占 `:sync` のみ | 再配布・改変は認められる（帰属表示が条件）。ただし §2(a)(5)(A) で下流の受領者は原ライセンサから直接ライセンスを受けるので、**独占は原理的に渡せない** |
| `:license/cc0` | 非独占 `:sync` のみ | 権利を可能な限り放棄した dedication。下流は自由に使えるが、放棄は**全世界に対して**行われているので独占は渡せない |
| `:license/public-domain` | 非独占 `:sync` のみ | 誰も権利を持っていないので独占も渡せない |

**この表が答えるのは「その資産が X で出ていると仮定して何を渡せるか」であって、
「その資産を X で出してよかったか」ではない。** 後者は別の法的判断で、たとえば
生成物に CC0 を貼る根拠は生成モデルの出力条項に依存する —— この表は答えない。

`license-holdings` は**人が維持する法的判断**であって、実装がライセンス本文を
解釈して導いたものではない。各エントリは根拠（`:basis`）・確認日（`:checked`）・
出典（`:source-url`）を必ず持ち、テストがそれを強制する。

**未知のライセンスと未記載はどちらも `[]`。** 判断が無いことを「制限が無い」と
読み替えない。`explain` が理由を人が読める形で返すので、受注が `:not-held` で
落ちたときにそれを提示できる。

`ongaku.work` の provenance には **`:licensed`**（第三者の録音を license で
使っている）がある。手元に在るのはミックス済みの音声 1 本なので
`producible-kinds` は `#{:master-audio}` だけ —— stem も譜面も DAW セッションも
この studio の手元には無い。**何が実在するか（provenance）と何を渡せるか
（holdings）は別の問いで、別々に答える。**

## Occupation

ISCO-08 `2652` (Musicians, Singers and Composers) —
[cloud-itonami-isco-2652](https://github.com/cloud-itonami/cloud-itonami-isco-2652).

## Test

```bash
kbb -M:test                                              # JVM suite
kbb --backend sci --classpath src:test test/run_portable.cljk  # portable suite, no JVM
```

First run end to end (catalog → plan → refusal → holdings):
[docs/operator-quickstart.md](docs/operator-quickstart.md).

## License

Apache-2.0.
