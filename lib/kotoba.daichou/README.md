# daichou（台帳）

**agent の行為を、承認ごと、改ざん耐性のある連鎖として残す。自己ホスト。**

`.cljc` の再利用ライブラリで、IO を持たない。値と関数だけ。

## なぜ作ったか

記録するだけの実装は既にある — [microsoft/agent-governance-toolkit](https://github.com/microsoft/agent-governance-toolkit)（MIT・無料）、Microsoft Agent 365（GA・$15/user/月）、Asqav（Elastic License 2.0）。**この台帳が違うのは2点だけ**:

1. **承認を欠いた受領証を作れない。** `:approval`（誰が・何を決めたか・どの policy 版で）が無いと `receipt/make` は例外を投げる。後から承認を書き足す余地を残さない。
2. **完全性が手元で完結する。** Asqav を実際に入れて確認したところ、`local_sign` は署名せず `{... "status": "pending"}` の素の JSON をキューに積むだけで、**署名・ハッシュ・連鎖はすべてサーバ側**だった（README も "All cryptography runs server-side"）。**agent の行為を第三者クラウドへ送れない組織では、あちらの改ざん耐性は一切得られない。** ここはその制約下で動く。

## 使う

```clojure
(require '[daichou.chain :as chain])

(-> []
    (chain/append {:action   {:action/agent "claude-code" :action/type "git:push" :action/target "main"}
                   :approval {:approval/by "gftd-governor"
                              :approval/decision :allow          ; :allow / :deny / :review
                              :approval/policy-version "fleet-policy@2026-07-31"}
                   :at       "2026-07-31T00:00:01Z"})
    chain/verify)
;; => {:ok? true :length 1}
```

検証は**壊れた位置**を返す。壊れた事実だけを返す検証器は、運用では「台帳全体が信用できない」としか読めない。

```clojure
(chain/verify tampered)
;; => {:ok? false :length 3 :broken-at 1 :reason :receipt-altered}
```

## 署名

Ed25519（RFC 8032）。**決定的**なので、同じ鍵と同じ入力なら常に同じ署名になり、
**nbb と JVM が同じ値を計算することを test で証明できる**（乱数を使う方式ではこれができない）。
実装は RFC 8032 の公開テストベクタと一致することを検査している — 自分の実装と自分の
検証器が噛み合うだけの test は、両方が同じように間違っていても緑になるため。

```clojure
(-> receipt
    (receipt/sign {:signer      (fn [msg] ...)   ; 鍵はここに来ない
                   :by          "fleet-writer"   ; 署名した主体
                   :public-key  "d75a98…"}))
(chain/verify c {:verifier (fn [pk msg sig] ...)})
;; => {:ok? true :length 2 :signatures-checked? true}
```

**`verifier` を渡さなければ署名は見ない。** その場合 `:signatures-checked? false` が返る —
見ていないものを「通った」と報告しないため。逆に verifier を渡した台帳に無署名の行が
あれば `:reason :unsigned` で落ちる（署名を検証すると決めた台帳に無署名の行があるのは、
検証していないのと同じ）。

### 3層で縛っていて、どれも単独では足りない

| 層 | 何を縛るか | これだけを見ると見逃すもの |
|---|---|---|
| `:receipt/action-ref` | 行為 | 承認の差し替え |
| `:receipt/hash` | 行為 + 承認 + 時刻 + action-ref + 前件ハッシュ | 台帳ごとの作り直し |
| `:receipt/signature` | 上のハッシュ | （鍵が漏れた場合） |

- 本文だけ書き換える → `action-ref` と `hash` が合わなくなる（**署名は当たったままなので、署名だけを見ると見逃す**）
- 本文と `action-ref` と `hash` を全部作り直す → 内部は完全に整合し `intact?` は通る。**ここで唯一残る歯止めが署名**
- 署名は `:receipt/hash` の**外**にある（中に入れると、署名を足した瞬間にハッシュが変わって自分自身と整合しなくなる — 最初の実装がそうなっており test が掴んだ）

**署名した主体（`:signature/by`）と承認した主体（`:approval/by`）は別物として残る。** fleet が書き、governor が承認する構成では一致しない。

### 鍵はこの層に来ない

`signer` は `hex-message -> hex-signature` の関数で、鍵は呼び出し側（**kagi**）が閉じ込めたまま署名だけを返す。第二の keyring を作らないため（ADR-2607310300 D6）。JVM では seed からの公開鍵導出も行わない — 鍵ペアを持っているのは kagi で、必要なら `kotoba-lang/ed25519`（pure Clojure、seed → 公開鍵/did:key）を呼び出し側で使う。

なお PQC 側（ML-DSA-65）はここでは重ねない。kagi が Ed25519 + ML-DSA-65 の hybrid を
持っているので、対量子が要る場面はそちらの責務。

## 設計上、意図的に狭くしてあるところ

- **浮動小数を受け付けない。** ClojureScript では `1` と `1.0` が同じ値なので、「整数と小数を区別する」正規化は JVM でしか成り立たない。**両 runtime で同じ連鎖にならない台帳は、台帳として無いのと同じ**（nbb で作った受領証を JVM の検証器に出せない）。金額や計測値は文字列か整数（最小単位）で入れる。これは実装後に**両 runtime で走らせて見つけた**欠陥で、区別する代わりに受け付けないことにした。
- **map のキー衝突を潰さない**（`{:a 1 "a" 2}` は例外）。潰すと改ざんが隠れる。
- **鍵の保管・取得を持たない。** 署名を足すときは kagi 経路を使う（`kagami` と同じ流儀）。第二の keyring を作らない。
- **送信経路を持たない。** クラウドへ送るかどうかは利用側の判断で、この層は関与しない。

## runtime

第一の実行経路は **nbb / ClojureScript**、JVM は互換スイート用（AGENTS.md の runtime 優先順位）。`test/daichou/chain_test.cljk` は**両方で走らせる前提**で、その中の golden hash が「片方で作った連鎖がもう片方で検証できる」ことを固定している。

```bash
kbb --backend sci --classpath "src:test" -e '(require (quote [clojure.test :as t]) (quote daichou.chain-test)) (t/run-tests (quote daichou.chain-test))'
kbb -M:test
```

## 位置づけ

- 設計判断の正本: `com-junkawasaki/root` の `90-docs/adr/2607302210-*.edn`（D33 ②、D42）
- 競合の実測データ: `gftdcojp/kabuto`（`market-maturity.edn` / `conformance.edn`）
- 隣接: `kagami`（repo の pin 事象の台帳。ドメインが違う）、`ai-gftd-cybersecurity`（証跡の出力と規制への写像）
