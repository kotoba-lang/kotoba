# kotoba-lang/org-jpki

**公的個人認証サービス（JPKI）署名用電子証明書で作られた署名を、受け取って検証する
側**の実装。portable `.cljc`。

```clojure
(require '[jpki.core :as jpki] '[cms.jvm :as jvm])

(jpki/verify-signature signed-data
  {:content bytes :roots [jpki-root] :at "2026-08-01T00:00:00Z"
   :digest-fn jvm/digest :verify-fn jvm/verify})
;=> {:verified true :revocation :not-checked …}

(jpki/basic-four certificate)   ;; 明示的に呼んだときだけ読む
```

## 埋める穴と、埋めない穴

`cloud-itonami-app` の esign は**立会人型**（事業者署名型）。三省 Q&A の整理では
電子署名法 2 条に当たり得るし、固有性が十分なら 3 条の推定も及び得る。
**当事者型**は別の道で、本人の証明書で署名されるため 3 条の推定が最も素直に働く。

実装するのは**検証側だけ**。カード側のセレモニー（NFC/PC-SC の APDU、署名用
パスワード、カード内での署名生成）はハードウェアと専用ドライバを要し、ここには無い。
**「JPKI 対応」と言えるのは、外部で作られた署名を検証できる、という意味だけ。**

## 失効確認はここでは完結しない

JPKI の失効情報は**署名検証者として認定・届出をした事業者**だけが J-LIS から
取得できる。だからこの実装は失効を確認せず、**確認したふりもしない**。
`:revocation` は常に返り、常に `:not-checked`。省略すれば「確認した」と読まれる。

失効確認なしで言えるのは「発行時点でこの鍵が本人のものだった」まで。
「署名時点で有効だった」は言えない。`presumption-note` がその差を文にする。

## 基本4情報は要求されたときだけ読む

氏名・生年月日・住所・性別は subjectAltName の otherName（arc `1.2.392.200149.8.5`）
にある。**個人情報そのもの**なので `parse-certificate` は読まない。`basic-four` を
明示的に呼んだときだけ読み、判断は呼び出し側に残す。`:sex` は JIS X 0303 のコードを
そのまま返す — 語に変換した時点でこの library が分類の語彙を決めてしまう。

## fixture は本物ではない

実物の署名用電子証明書は個人情報を含み公開リポジトリに置けない。テストは
**JPKI と同じ形に作った合成証明書**に対して行っている。検証されているのは構造の
読み取りと拒否条件であって、**実カードとの相互運用性ではない**。それは実カードで
確かめるまで未証明。

## Test

```bash
kbb -M:test
kbb -M:lint
```

Apache-2.0.
