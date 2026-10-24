# word-id

**語で表す ID。** `sponge-pumpkin-cellar-nestle` のような、電話で読み上げて
書き取れる識別子と、その裏の整数（この例では 888,888,888）との全単射。

what3words が座標に対してやっていることを、アカウント ID に対してやる。
違いは 2 つ: 地理的な近接という概念が無いので、代わりに **checksum 語**を
1 語持つ。そして語彙は値として渡すので、既定の英語 1021 語に縛られない。

```clojure
(require '[word-id.core :as w]
         '[word-id.english :as english])

(def v english/vocabulary)

(w/encode v 888888888)
;; => {:word-id/code 888888888
;;     :word-id/words ["sponge" "pumpkin" "cellar" "nestle"]
;;     :word-id/text "sponge-pumpkin-cellar-nestle"}

(w/parse v "SPONGE, pump / cellar nestl")
;; => {:word-id/code 888888888
;;     :word-id/corrections [{:word-id/given "pump"  :word-id/read-as "pumpkin" :word-id/basis :prefix}
;;                           {:word-id/given "nestl" :word-id/read-as "nestle"  :word-id/basis :prefix}]
;;     ...}

(w/mint v [0x12 0x34 0x56 0x78 0x9a 0xbc])   ; エントロピーは呼び出し側が渡す
;; => {:word-id/text "..." :word-id/bytes-consumed 6 ...}
```

## ID は文字列ではなく整数の別表記

これが設計の全体を決めている。保存するのも比較するのも衝突を見るのも整数で、
語に戻すのは表示のときだけ。だから `parse` は大文字・区切り・前後の空白・
途中までの綴り・1 文字の打ち間違いを全部吸収して**同じ整数**に落とせる。

`payload 3 語 = 1021³ = 1,064,332,261 通り`。足りなければ `:payload-words` を
上げる（上限 5。理由は下記）。

## checksum が catch するもの、しないもの

検査は 1 本の合同式。

    2·d₀ + 3·d₁ + 4·d₂ + 1·c  ≡  0  (mod 1021)

重みが全て相異なり、法が素数（＝零因子が無い）なので:

- **1 語の置換は必ず検出する**
- **2 語の入れ替えは必ず検出する**

どちらも `tiny` 語彙（5 語 × 2 桁 = 25 通り）で**全数検査**している —
全 ID × 全位置 × 全置換、および全 ID × 全入れ替え。

**検出はするが、位置は特定しない。** どの位置の誤りでも同じずれを説明できる
ので、「3 語目が違う」とは言えない。言えるのは「1 語だけ直せば正しくなる
候補が 4 つある」ことで、それが `repairs`。返る 4 つはどれも**等しく正当な
ID** なので、UI の「もしかして」に使ってよいが自動採用してはならない。

## 語彙サイズは素数でなければならない

切りのよさではない。1024 語なら重み 2 の桁を 512 ずらす誤りが余りを変えず、
**検出できない誤りが構造的に存在する**。`word-id.vocabulary/problems` は素数
でない語彙を警告ではなく**拒否**する。

語彙にはもう 2 つ構造を課す。**先頭 4 文字が一意**（`spon` まで打てば
`sponge` に確定する。BIP-39 と同じ規則）、**相互の編集距離が 2 以上**
（`crest` と `chest` が同居すると 1 文字の誤りが別の正しい語になる）。

## 既定語彙 1021 語の出所

`src/word_id/english.cljk` は**生成物**。手で編集しない。

    kbb --backend sci --classpath src scripts/derive_wordlist.cljk           # 再生成
    kbb --backend sci --classpath src scripts/derive_wordlist.cljk --check   # canonical か検査

候補は `scripts/candidates.edn` に手で書くが、採否は生成器が決める:
`/usr/share/dict/web2`（Webster's Second International、public domain）に
実在すること、4〜7 文字の a-z、先頭 4 文字が一意、編集距離 2 以上、denylist に
無いこと。生き残りを辞書順に貪欲に採り、そこから 1021 語を等間隔で選ぶ。

**足りなければ生成器は落ちる。** web2 から自動で埋めない — 数は揃うが混ざる
のは `aalii` / `abaca` のような口に出せない語で、この語彙の唯一の存在理由が
消える。足りないときは候補を足す。

生成した語彙は最後に **この library 自身の `vocabulary/problems`** に通す。
規則が生成器と library の 2 箇所にあると必ずずれるので、判定は library 側
だけが持つ。

## 持たないもの

**乱数**。`mint` は byte 列を受け取る。CSPRNG を持たないのは移植性のためでは
なく検査可能性のため — 固定の byte を渡せば結果が決まるので、発行の正しさを
テストで固定できる。

**IO**。語彙はファイルではなく値。`word-id.english/vocabulary` も値。

**衝突の管理**。発行済み ID の集合を持つのは発行側の仕事。この library は
「一様に引く」ところまでで、`insufficient-entropy` を返したら byte を足して
呼び直す（棄却抽出なので必要な byte 数は入力に依る）。

## payload 語数の上限が 5 な理由

`code` は語彙サイズの payload 乗まで取る。JavaScript の number が誤差なく
表せるのは 2^53 まで。1021⁵ = 1.1×10¹⁵ はその中、1021⁶ = 1.1×10¹⁸ は外。
6 語を許すと **JVM では正しくブラウザでは静かに丸まる** ID ができる。
`vocabulary/configuration-problems` がこれを拒否する。

## テスト

```bash
kbb -M:test                                  # JVM
kbb --backend sci --classpath src:test run-tests.cljk          # ClojureScript
```

両方で回すのは、JVM で通ることが CLJS でも同じ答えを出す証拠にならないから
（整数精度と `mod` の符号）。
