# kami-mangaka-expression

> **Standalone SSoT (ADR-2607102200 addendum 12).**  
> Path: `orgs/kotoba-lang/kami-mangaka-expression` — not nested under `kami-engine/`.


Work-agnostic **manga expression patterns** — 「キャラクターごとに、表情・姿勢・
吹き出しの形・文字の薄さ・大きさ・背景トーンを変える」という漫画的表現を **data から**
決める純粋レイヤ (ADR-2607012100, Tier-1 mangaka)。

出典は **HUNTER×HUNTER 王位継承戦編**（冨樫義博）のコマ観察
（`resources/mangaka_expression_patterns.edn` の `:source` / `:observations`）。
抽出した漫画文法:

- **モブのざわめき** — 薄い小さな手書き文字＋小さな雲形＋群衆シルエット背景 (`:chatter`)
- **キャラ名札** — 黒箱に白抜きゴシック (`:nameplate`)
- **割り込み/元気** — 挙手＋放射状集中線＋太く大きなトゲ/バースト吹き出し (`:energetic`+`:shout`)
- **激昂アップ** — 前傾＋歯剥き＋黒トゲ/フラッシュ背景＋汗・怒張 (`:hot-blooded`+`:shout`)
- **冷酷/威圧** — 直立＋重い影(暗ビネット)＋太明朝の決め台詞 (`:cold-menace`)
- **独白/地の文** — 明朝の囲み (`:monologue`/`:narration`)

加えて `hume_manga_face_taxonomy.edn` は Hume AI の表情研究を制作向けに橋渡しする。
現行の48表出次元を、目・眉・まぶた・瞳孔・視線・左右差・ハイライト・涙・口へ分解した
26個の face rig に写像する。これは感情の読心ではない。Hume の値は「観察者からその表出に
見える信頼度」、`:intensity` は漫画としての誇張量であり、両者を混同しない。

## モデル

1 行分のスタイルは

```
archetype(キャラ類型) ← register(セリフ種別) ← expression-cue(感情) ← intensity(強度)
```

の順に merge して決まる（`resolve-style`）。出力は **semantic タグ**のみ:

| キー | 意味 | 語彙 |
|---|---|---|
| `:expression` | 表情 | `kami.mangaka.scene` の Rust Expression と一致 |
| `:posture` | 姿勢 | `:upright :lean-in :arm-raised :recoil :slump :point :cross-arms :turn-away` |
| `:bubble` | 吹き出しの形 | `kami.mangaka.text` ∪ `{:spike :burst}` |
| `:font-role` | 写植ロール | ai-gftd-mangaka の `manga-font-palette` (fontRole) |
| `:weight` | 文字の薄さ↔太さ | `[:faint :light :regular :bold :heavy]` |
| `:scale` | 文字の大きさ | 倍率 (double, `:scale-max` で clamp) |
| `:tone` | 背景トーン | `:focus-lines :radial-burst :flash :vignette-dark :crowd-silhouette …` |
| `:marks` / `:fx` | 描き文字マーク / 効果 | 汗・怒張・集中線 など |

見た目への写像（opacity/font-size/screentone）は **renderer 側**が持つ
（`kami-mangaka-text-clj` の hiccup+CSS / `kami-mangaka-page-clj` の Java2D）。
本モジュールは純 semantic — babashka-safe / JVM・cljs・WASM 可搬。

## API

```clojure
(require '[kami.mangaka.expression :as e])
(def P (e/load-patterns))                      ; clj: resources の edn を読む

(e/resolve-style P {:archetype :hot-blooded :register :shout :intensity 1.0})
;; => {:bubble :spike :weight :heavy :scale 2.4 :tone :flash :fx [:speed-lines]
;;     :marks [:anger-vein :sweat] :expression "Angry" :posture :lean-in …}

;; storyboard へ適用（cast: speaker → archetype）
(e/analyze-page P {"ガター" :hot-blooded "スラッカ" :energetic}
  {:panels [{:characters ["ガター"]
             :dialogue [{:speaker "ガター" :text "バカな！！" :intensity 1.0}]}]})
```

### Hume 48次元 → 目・表情 rig

```clojure
(def F (e/load-face-taxonomy))

(e/resolve-face F
  {:profile {"Amusement" 0.70 "Joy" 0.69 "Interest" 0.58}
   :intensity 0.8
   :gaze :at-subject})
;; => {:measurement :observer-interpretation-confidence
;;     :dimensions [{:label "Amusement" :confidence 0.70 ...} ...] ; top 3を保持
;;     :families {:play ... :attention ...}
;;     :rig :laughing-closed
;;     :eyes {:open ... :upper-lid :raised-arc :brow :outer-raised ...}
;;     :mouth :open-laugh :scene-expression "Happy" :intensity 0.8}
```

目のレシピは `:open`（開眼量）、上下まぶた、眉、瞳孔比、虹彩比、視線、ハイライト、
涙、左右差を持つ。Hume の上位1件だけに潰さず、既定で上位3次元と family 混合比を返す。
文化・文脈・キャラクター固有の display rule は consumer 側で検証・上書きする。

`register` 省略時は `infer-register` が本文から推定（`！！`→`:shout`、`（…）`→`:whisper`）。
明示された `:bubble` / `:weight` / `:scale` は常に解決結果に勝つ。

## 消費側

- **kami.mangaka.text / .page** — 解決済みの `:weight`/`:scale`/`:tone`/`:bubble` と
  `:chatter`/`:nameplate` register を hiccup+CSS / Java2D で描画。
- **ai-gftd-mangaka** — langgraph `ai.gftd.mangaka.analyzeExpression` が `analyze-page`
  を storyboard datom（`:panel/bubbles` 等）に橋渡しし、`:bubble/shape` `:bubble/font`
  `:bubble/font-size` `:panel/tone` を enrich する。
- **genko**（kami-engine-sdk）— fukidashi type / tone を同語彙で受ける。

## テスト

```bash
kbb -M:test                  # vocab lock-step / resolve-style / analyze
kbb --backend sci scripts/run-task.cljk test   # the same suite through the task registry
```

`kbb -M:test` を案内していたが、babashka は ADR-2607173000 で本 workspace の
script host から退役している。同じ task は `scripts/tasks.edn` に復元済みで
（ADR-2608131600）、上の nbb 形で起動する。実測 2026-08-13: 7 tests /
104 assertions, 0 failures。
