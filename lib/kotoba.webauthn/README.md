# webauthn

EDN substrate for WebAuthn / passkey registration and assertion flows.

Cryptographic verification and browser APIs are host ports. This repo keeps
challenge, credential, assertion, and passkey PRF envelope shapes portable.

For the raw W3C WebAuthn relying-party ceremony spec-as-data substrate (zero
deps, no host assumptions), see [kotoba-lang/org-w3-webauthn](https://github.com/kotoba-lang/org-w3-webauthn).
This repo is the result-shape/substrate layer consumed by
[kotoba-lang/authentication](https://github.com/kotoba-lang/authentication).

## `webauthn.assurance` — その credential が実際に何を証明しているか

`authenticatorSelection` で platform authenticator を**要求する**ことと、
それを**得る**ことは別。Chrome DevTools の virtual authenticator は `platform`
を名乗り、user verification を自動で通し、人の指なしに何でも署名する。応答から
`authenticatorAttachment` を読んで「ハードウェアだ」と結論する検査は門ではなく
コメントである。

実際に検証できるのは、弱い順に:

| level | 何に基づくか | 嘘をつくクライアントは… |
|---|---|---|
| `:unknown` | 記録なし | — |
| `:platform-claimed` | 応答中の `authenticatorAttachment` | …ただ `platform` と言えばよい。**署名されていない** |
| `:platform-attested` | 署名済み authenticator data 内の AAGUID | …署名済み authData を偽造する必要がある |
| `:hardware-attested` | 設定された root への attestation chain | …Apple の署名を偽造する必要がある |

下 2 行だけが証拠。`:platform-claimed` を記録するのは台帳に載せる価値があるから
で、`verified` と読まれないように `claimed` と名付けてある。

**純関数。** 保存済みの map を採点するだけで、ceremony も enforcement も持たない
—— ブラウザも端末も人の指も無しに試せる。

```clojure
(require '[webauthn.assurance :as assurance])

(assurance/assurance {:attachment "platform" :aaguid "adce0002-…"})
;; => {:passkey/assurance :platform-attested :passkey/aaguid-label "Chrome on macOS (Touch ID / Secure Enclave)" …}

(assurance/policy-issues credential (assurance/policy-for {:min-assurance :platform-attested}))
;; => [] か、なぜ通らないかの列
```

**なぜここに在るか。** 2026-07-30 に `cloud-itonami-app` で書かれたもの
（支払いを Secure Enclave + Touch ID に縛る決定）。`cloud-itonami`（Cloudflare
edge）には等価物が無く、credential ごとに `backup-eligible?`/`backup-state?` を
記録して復旧姿勢を出してはいたが、**鍵が何を証明しているか**を言う仕組みは
持っていなかった。同じプロダクトの 2 つの面がパスキーの強さについて別々のことを
言う、というのがこの移設で防ぐ失敗。新規 repo を作らなかったのは、
「WebAuthn credential が何を証明するか」がこの repository の主題そのものだから。


## `webauthn.adapters.edge` — the ceremony crypto, for real

The portable namespaces above model the *shapes*. `webauthn.adapters.edge`
(CLJS-only) does the actual WebAuthn Level 2 verification on WebCrypto — no
npm, no platform binding — so a Cloudflare Worker can accept passkeys:

```clojure
(edge/verify-registration! {:rp-id "authn.example" :origin "https://authn.example"}
                           {:client-data-json-b64url … :attestation-object-b64url …
                            :challenge <the one you issued>})
;=> Promise<{:ok true :credential-id … :public-key-b64 … :sign-count n}>

(edge/verify-authentication! config
                             {:client-data-json-b64url … :authenticator-data-b64url …
                              :signature-b64url … :challenge … :public-key-b64 <stored>})
;=> Promise<{:ok true :sign-count n :user-verified? bool}>
```

It is a pure function of its inputs plus WebCrypto. **Storage, key custody and
session issuance are deliberately the caller's** — the prior art this is ported
from fused ceremony verification, a KV schema, an AES-GCM key-wrapping scheme
and CACAO minting into one namespace, which made all four untestable without
Cloudflare bindings.

Two responsibilities the caller must not skip, because they need persistence
this namespace does not have:

- **make the challenge single-use.** A replayable challenge is a replayable
  sign-in. This adapter checks that the presented challenge equals the one you
  issued; ensuring it can only be issued once is a storage property.
- **apply `sign-count-ok?`** against your stored baseline, then persist the new
  count (WebAuthn L2 §7.2 step 19, clone detection).

Verified against `webauthn.virtual-authenticator` — a P-256 authenticator that
really signs, including ceremonies that misbehave on purpose:

```bash
kbb --backend sci --classpath "src:test:../org-chainagnostic-cacao/src" test/webauthn/edge_smoke.cljk
```

