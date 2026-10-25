# sekisho（関所）— 共通認証の判断層

旅人の身元と通行手形を検める場所。設計の正本は superproject の
**ADR-2608039950**。

## `kotoba-lang/authentication` との違い

| repo | 役割 |
|---|---|
| `authentication` | **factor の substrate** — WebAuthn / OIDC / SAML / OTP / CACAO の結果を統合する |
| `authorization` | 認可の facade — `policy` / `cacao` へ委譲 |
| `identity` | subject / attestation の可搬 EDN |
| **`sekisho`** | **プロダクト層の判断** — 口座・組織・復旧。各サイトが自前で持っていたものを 1 箇所に |

## なぜ要るのか（実測、2026-08-03）

    repo              authn 参照   自前 did/storage 実装
    cloud-murakumo        2              12
    local-murakumo        0               4
    net-babiniku          0               8

**各サイトが did:key と localStorage を自前で扱っていた。** それぞれ少しずつ
違う実装を持つと**壊れ方も少しずつ違う**ので、1 箇所直しても他が残る。

実際に起きていた壊れ方（同日修正済み）:

```js
did = 'did:key:z6Mk' + btoa(...).replace(/[^a-zA-Z0-9]/g,'').slice(0,32);
catch(e) { did = 'did:key:z6Mk' + Date.now().toString(36); }
```

base64 を切り詰めたものと**タイムスタンプ**を口座にし、さらに秘密鍵を捨てて
いた —— 構造として正しい did:key でも、**誰も鍵を持っていなければ口座ではない**。

## 何を持ち、何を持たないか

| ns | 役割 |
|---|---|
| `sekisho.didkey` | did:key（Ed25519）の唯一の構造判定。multicodec `0xed01` と 34 byte を実際に検査 |
| `sekisho.tenant` | 組織 / 人 / credential の 3 層。**既存の accountDid を改名しない** |
| `sekisho.account` | 口座の契約 —— バックアップの形と復旧状態の 3 値 |
| `sekisho.assurance` | **何が確かめられているか**と、それが解放する上限 |

**持たないもの**: 鍵生成（WebCrypto）・保管（localStorage）・HTTP・UI。
判断だけを持つのは移植性のためではなく **検査可能性** のため —— 鍵生成を含むと
『壊れた口座を弾けるか』を実際の鍵無しには試せなくなる。

## 信頼の段階（`sekisho.assurance`）

メール検証・パスキー・身分証・顔の一致・KYC・Human Passport の検証済み結果を証拠として受け取り、段階と、
その段階で解放されるものを返す。

    :anonymous → :contactable → :rooted → :attested → :identified
                 連絡が付く      鍵がある   自己申告でない  実在の人物と
                                          証拠が 1 つ   結びついている

| | persona | 送信/日 | 支払い上限 | できること |
|---|---|---|---|---|
| `:anonymous` | 0 | 0 | 0 | — |
| `:contactable` | 1 | 20 | 0 | メール送受信 |
| `:rooted` | 5 | 200 | 0 | + persona 発行、credential 保持 |
| `:attested` | 25 | 2,000 | 50,000 | + authority への提案 |
| `:identified` | 100 | 20,000 | 1,000,000 | + authority の承認 |

**単一のスコアにしない。** 『信頼性スコア 72 点』は書きやすいが、72 点で
断られた人に次の一手が無い。返すのは順序付きの段階と、次の段階に足りていない
ものの**名前**（`:sekisho.assurance/shortfall`）。段階は比較できるが足し算は
できない —— メール検証 2 回は身分証 1 回にならない。

Human Passport の score は `identity` adapter が EAS の schema・attester・scorer・
期限・配備ごとの閾値を検証した後、`:evidence/humanity-verified` という 1 種類の
証拠に翻訳する。生の score を Sekisho の点数にはしない。この証拠は Sybil 耐性として
`:attested` の選択肢にはなるが、身分証・liveness・顔一致を代替せず
`:identified` には到達させない。明示 expiry がない score attestation も 90 日で更新する。

**段階は飛び級できない。** 身分証と顔だけあってパスキーが無い口座は
`:contactable` 止まり。飛び級を許すと、鍵を持たない口座が身分証だけで支払い
上限を得る。

**証拠には期限がある。** liveness は 180 日。期限切れは『やっていない』では
なく**『切れた』として報告する** —— UI が「本人確認をしてください」と
「更新してください」を出し分けられるように。

**自己申告は段階を上げない。** `credential-assurance` の `:platform-claimed`
と同じ扱いで、記録する価値はあるが根拠ではない。

**解放するのは上限であって行為そのものではない。** `:identified` が支払い
上限を上げても、その 1 回には依然として新しい WebAuthn の署名が要る
（cloud-itonami-app の ADR-0006 / ADR-0012）。段階は「いくらまで」を決め、
`authority` が「この 1 件を本人が今承認したか」を決める。

パスキーの 4 段階（`credential-assurance` の `:unknown` 〜
`:hardware-attested`）はこの ns の語彙ではない。呼び出し側が
`:platform-attested` 以上を `:evidence/passkey-hardware`、それ以外の登録済みを
`:evidence/passkey-enrolled` に翻訳して渡す。持てる persona の本数は
`persona-cap` が返す整数 1 つで `kotoba-lang/persona` に渡る —— どちらの repo も
相手の内部を知らない。

## authority を増やさない

DID の権威は `kotobase.net` 1 つ（ADR-2608039950）。第 2 authority を立てるのは
この設計で唯一取り返しのつかない選択で、ブランド名は後から変えられるが
**発行済み DID の namespace は変えられない**。

```bash
kbb -M:test                              # 全部（.clj のテストを含む）
kbb --backend sci --classpath src:test run-tests.cljk      # .cljc の 2 本を ClojureScript で
```

`sekisho.assurance` と `sekisho.didkey` は Cloudflare Worker とブラウザで実際に
動くので、JVM で通ることを証拠にしない。
