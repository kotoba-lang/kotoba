# one-time-link

**一度きりのリンクの寿命の判断。トークンそのものは受け取らない。**

サインインリンク・招待・アドレス確認・パスワード再設定 — 形はどれも同じで、
「秘密をメールに載せて送り、開いた 1 回だけ効かせる」。同じものを 2 回書くと
必ず片方に穴が空く。

```clojure
(require '[one-time-link.core :as otl])

;; 発行側: トークンは呼び出し側が作り、digest だけを渡す
(otl/issue-plan {:digest (sha256 token)
                 :kind :session
                 :subject "acme/ops:alice@acme.example"
                 :now (System/currentTimeMillis)
                 :last-issued-at previous})
;; => {:one-time-link/issue? true
;;     :one-time-link/record {:one-time-link/digest "…" :one-time-link/kind :session
;;                            :one-time-link/expires-at 1785000600000 …}}

;; 消費側
(otl/redeem stored-record (sha256 presented-token) now :expect-kind :session)
;; => {:one-time-link/redeemed? true :one-time-link/kind :session :one-time-link/subject "…"}
;; => {:one-time-link/redeemed? false :one-time-link/refused :expired}
```

## なぜこの repo が在るか

`cloud-itonami`（Cloudflare Worker / CLJS）と `cloud-itonami-app`（JVM）が
**独立に同じものを実装していた**。実測（2026-08-06）:

| | cloud-itonami-app | cloud-itonami |
|---|---|---|
| 有効期限 | `email-login-seconds 600` | `email-login-ttl-ms (* 10 60 1000)` |
| 冷却 | `email-login-cooldown-seconds 60` | `email-login-cooldown-ms (* 60 1000)` |
| トークン | 32 byte CSPRNG | 32 byte CSPRNG |
| 保存 | SHA-256 digest（平文は保存しない） | SHA-256 digest（同上） |
| 応答 | 常に同じ（列挙耐性） | 常に同じ（列挙耐性） |

同じ結論に別々に到達していた。**同じ結論なら 1 箇所にある方がよい** —— 片方だけ
直る事故が構造的に起きなくなる。

## digest しか見ないのは、型で強制するため

両方の実装が独立に「保存するのはトークンではなく digest」に達していた。理由も
同じ: リンクはメールを通るので、送信側・受信側・その間のプロバイダのどこかに
平文が残る。保管側も漏れたときに、そこから生きたリンクを組み立てられる状態に
しない。

その結論を docstring ではなく**引数の形**にした。この ns の関数はトークンを
受け取らないので、**うっかり平文を保存する経路が書けない。**

## 種類は発行時に決まる

`:kind` を record に焼き、`redeem` の `:expect-kind` がそれに照らす。いまの
状態から推測しない — リンクが飛んでいる 10 分の間に状態が変われば、送った
つもりのものと違うものが渡る。cloud-itonami で実際にこの分岐が要った: 根
（パスキー）が出来た口座に「新しい根を作れる」登録リンクが通ってしまう。

## 持たないもの

**乱数・ハッシュ・KV・メール送信。** 呼び出し側がトークンを作り、digest を渡し、
返った record を保存し、リンクを配る。ここは「いま出してよいか」「これは通して
よいか」だけを答える。

**利用者向けの文言。** `public-outcome` はメッセージを引数に取る — 言語と語彙は
プロダクトのもの。

## 定数時間比較の移植性（実際に踏んだ）

`digest=?` の最初の実装は `(bit-xor (int (nth a i)) (int (nth b i)))` だった。
JVM では正しい。**ClojureScript では `nth` が 1 文字の文字列を返し `(int "a")`
が NaN になるため `bit-xor` が常に 0 になり、長さの同じ digest が全て一致した。**

ブラウザと Worker でだけ壊れる種類のバグで、**初回の cljs 実行が捕まえた**。
両ホストでテストを回しているのはこのため。

## テスト

```bash
kbb -M:test                              # JVM
kbb --backend sci --classpath src:test run-tests.cljk      # ClojureScript
```

消費側が JVM（cloud-itonami-app）と Cloudflare Worker（cloud-itonami）に
分かれているので、片方だけでは証拠にならない。
