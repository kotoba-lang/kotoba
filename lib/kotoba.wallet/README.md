# wallet (non-custodial マルチチェーン wallet)

MetaMask / Coinbase Wallet 型の non-custodial マルチチェーン wallet を portable
Clojure (`.cljc`) で。単一の BIP-32/39/44 seed から **データ表**（`wallet.chains` —
CoinMarketCap 主要チェーンを登録、family driver は `:evm` と `:utxo` の 2 つ）で
アカウントを導出し、**本物の SIWE (EIP-4361)** — `cacao`（Ed25519 did:key の
actor 内部認証専用）とは別に、secp256k1 の `personal_sign` で署名し `ecrecover`
で検証する、siwe.js/viem/ethers 等の実 Ethereum tooling がそのまま検証できる
フロー — を提供する。
ADR: `90-docs/adr/2607012200-kotoba-lang-btc-mining-wallet-substrate.md`、
signer seam は `90-docs/adr/2608241100-wallet-signer-seam-kagi-chain-signing.edn`。

秘密鍵は wallet の外に一切出さない（non-custodial）。
[kotoba-lang/btc-crypto](https://github.com/kotoba-lang/btc-crypto)（共有
secp256k1 HD tree・BTC/LTC/DOGE/BCH アドレス/tx）と
[kotoba-lang/eth-crypto](https://github.com/kotoba-lang/eth-crypto)（ETH
アドレス/tx/keccak）に依存。

## Custody は 2 形態

- **`account` / `sign-tx`** — 従来の in-process 経路。呼び出し側が
  `{:private-key …}` を受け取り、永続化するなら `wallet.keystore` で暗号化する
- **`account-with` / `sign-tx-with`** — **signer seam**（`wallet.signer/Signer`）。
  結果は秘密鍵を一切含まず、署名は Signer に委譲される。ハードウェアウォレット
  と同じ境界をソフトウェアで引く（ADR-2608039900 決定 1 の一般化）。
  - `wallet.signer/seed-signer` — in-process 実装（**DEV/TEST GRADE**、seed が
    このプロセスのヒープに載る。seam を秘密鍵経路とバイト一致で検査するために在る）
  - `kagi.chain-signer/signer`（kotoba-lang/kagi）— **本番 custody**。seed は
    kagi compartment から出ず、全署名が AccessGovernor の検閲と append-only
    台帳を通る

## Namespaces

- `wallet.chains` — **チェーンは data**。CMC 主要ネットワークの registry
  （EVM: eth/bnb/polygon/avalanche/arbitrum/optimism/base、UTXO:
  btc/ltc/doge/bch(受取専用)、TRON: trx(アドレス実装、tx は raw-data
  protobuf 未実装を名指しして拒否)、外部所有: atom→saifu、staged:
  sol/xrp/ton/sui/apt/near/ada/dot/xmr — staged は捏造アドレスを
  返さず、**待っている機構を名指しして拒否**する）
- `wallet.chain` — `ChainDriver` protocol + family driver（`evm-driver` /
  `utxo-driver` / `tron-driver`）+ `account`/`account-with`（BIP-44 パス導出）+
  `sign-tx`/`sign-tx-with`。EVM は EIP-155 legacy と EIP-1559 の両方、
  tx の `:chain-id` は registry から注入し、不一致は**拒否**する。
  UTXO も signer seam で署名できる（legacy P2PKH / BIP-143 P2WPKH、
  sighash と RFC-6979 署名は btc-crypto の BIP-143 公式ベクタ検証済み機構）
- `wallet.signer` — Signer protocol（`public-key64` / `sign-digest!`）+
  `seed-signer` + `compress`
- `wallet.siwe` — 本物の SIWE (EIP-4361): `message`、`sign-message`/
  `sign-message-with`、`verify-message`、`sign-in`/`sign-in-with`/`verify-sign-in`
- `wallet.keystore` — ローカル暗号化キーストア。`kotoba.lang.crypto` の
  `IAEAD` data contract 上に JVM 向けの実 AES-256-GCM 実装
  （`kc/mock-aead` はテスト専用、と `crypto` 自身がドキュメント化している）+
  PBKDF2-HMAC-SHA256 によるパスフレーズ鍵導出を同梱

## Quick start

```clojure
(require '[btc-crypto.bip32 :as bip32]
         '[btc-crypto.bip39 :as bip39]
         '[wallet.chain :as wallet]
         '[wallet.signer :as signer]
         '[wallet.siwe :as siwe])

(def seed (bip39/mnemonic->seed "<12/24-word mnemonic>" "<optional passphrase>"))
(def master (bip32/seed->master seed))

;; ── signer seam(推奨): 結果に秘密鍵が入らない ─────────────────────────
(def sgnr (signer/seed-signer master))   ; 本番は kagi.chain-signer/signer

(wallet/account-with sgnr :eth)  ;=> {:chain :eth :path "m/44'/60'/0'/0/0" :address "0x..." :chain-id 1}
(wallet/account-with sgnr :bnb)  ;=> 同じ address、:chain-id 56(EVM は 1 鍵 1 アドレス多チェーン)
(wallet/account-with sgnr :ltc)  ;=> {:p2pkh "L..." :p2wpkh "ltc1..."}
(wallet/account-with sgnr :sol)  ;=> 拒否(staged — 待っている機構を named error で返す)

(wallet/sign-tx-with sgnr (wallet/account-with sgnr :base)
                     {:nonce 0 :max-priority-fee-per-gas 1000000000
                      :max-fee-per-gas 30000000000 :gas 21000
                      :to "0x..." :value 0 :data "0x"})
;=> "0x02..." (:chain-id 8453 は registry から注入。EIP-1559 raw tx)

(siwe/sign-in-with {:domain "example.com" :address (:address (wallet/account-with sgnr :eth))
                    :uri "https://example.com" :chain-id 1
                    :nonce "..." :issued-at "2026-08-24T00:00:00Z"}
                   sgnr "m/44'/60'/0'/0/0")

;; ── 従来経路: 呼び出し側が秘密鍵を持つ ─────────────────────────────────
(def eth (wallet/account master :eth))   ;=> {:chain :eth ... :private-key ...}
(siwe/verify-sign-in (siwe/sign-in {...} (:private-key eth))
                     {:expected-domain "example.com"})
```

## Test

```
kbb -M:test
```

signer seam は **parity oracle** で検査している: signer 経路の出力が秘密鍵経路
（eth-crypto/btc-crypto 自身の repo で検証済み）と**バイト一致**すること、および
異なる account の署名が一致しないこと（等式検査が定数比較に劣化していないこと）。
