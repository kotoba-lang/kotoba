# btc-crypto (Bitcoin 暗号・エンコーディング)

Bitcoin 固有の暗号プリミティブとエンコーディングを portable Clojure (`.cljc`) で。
[kotoba-lang/eth-crypto](https://github.com/kotoba-lang/eth-crypto) の secp256k1
点演算・RFC 6979 決定論的 ECDSA（Bitcoin も同じ曲線）と
[kotoba-lang/crypto](https://github.com/kotoba-lang/crypto) の SHA-256 の上に、
Bitcoin 固有の RIPEMD-160・Base58Check・Bech32/Bech32m・BIP-32/39/44・WIF・
アドレス導出・tx 署名・strict-DER ECDSA 検証を追加する。
ADR: `90-docs/adr/2607012200-kotoba-lang-btc-mining-wallet-substrate.md`。

すべての公開関数は既知のテストベクタ（BIP-32 Test vector 1、trezor/python-mnemonic
の BIP-39 vectors.json、BIP-173 の bech32 例、BIP-143 の Native P2WPKH worked
example、privkey=1 の著名なアドレス/WIF、実際の genesis block header）で
**byte-for-byte 検証済み**（`kbb -M:test`、67 assertions green）。

## Namespaces

- `btc-crypto.ripemd160` — RIPEMD-160（JDK には無いため pure 実装）
- `btc-crypto.base58` — Base58 / Base58Check（WIF・legacy アドレスの符号化）
- `btc-crypto.bech32` — Bech32 (BIP-173) / Bech32m (BIP-350)、segwit アドレス
  ⇄ (witver, program)
- `btc-crypto.core` — `sha256d`、`hash160`、`compressed-pubkey`、WIF
  encode/decode、P2PKH/P2WPKH アドレス導出
- `btc-crypto.bip32` — HD 鍵導出（`seed->master`、`ckd-priv`、`derive-path`、
  xprv/xpub `serialize`）。**private-key path のみ**（CKDpub/xpub-only 導出は
  v1 スコープ外 — seed を持つ wallet はそもそも不要）
- `btc-crypto.bip39` — mnemonic ⇄ seed。`mnemonic->seed` は wordlist 不要
  （PBKDF2-HMAC-SHA512 のみ）。`entropy->mnemonic`/`mnemonic->entropy` は
  `resources/bip39/english.txt`（公式 bitcoin/bips のワードリストをそのまま
  同梱、sha256 で読み込み時に検証）が要る
- `btc-crypto.tx` — legacy P2PKH SIGHASH_ALL と BIP-143 P2WPKH SIGHASH_ALL
  の tx 署名（SIGHASH_ALL のみ、P2SH/multisig/Taproot は対象外）
- `btc-crypto.signature` — Bitcoin Core互換 strict-DER parser、sighash type、
  low-S分類、圧縮/非圧縮SEC公開鍵のECDSA verify

## Quick start

```clojure
(require '[btc-crypto.bip32 :as bip32]
         '[btc-crypto.bip39 :as bip39]
         '[btc-crypto.core :as btc]
         '[clojure.java.io :as io])

(def wordlist (bip39/load-wordlist (slurp (io/resource "bip39/english.txt"))))
(def seed (bip39/mnemonic->seed "abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon about"))
(def account (-> (bip32/seed->master seed) (bip32/derive-path "m/84'/0'/0'/0/0")))

(btc/address-of-privkey (:private-key account))
;=> {:p2pkh "1..." :p2wpkh "bc1..."}
```

## なぜ手書きの BIP-39 wordlist を埋め込まないか

2048 語のリストを記憶から書き起こすと1語でも誤りがあれば実際の recovery
phrase を静かに破壊しうる。同梱の `resources/bip39/english.txt` は
`github.com/bitcoin/bips` の `bip-0039/english.txt` から取得したそのままの
コピーで、`load-wordlist` が読み込み時に SHA-256
(`2f5eed53a4727b4bf8880d8f3f199efc90e58503646d9ff8eff3a2ed3b24dbda`) を
検証する。改変・破損・別言語ファイルの取り違えは即座に例外になる。

## Test

```
kbb -M:test
```

## Bitcoin-fork networks (Litecoin, Dogecoin, Bitcoin Cash)

Added 2026-07-26 after a market-cap review: these three carry ~5M RUNE of
THORChain pool depth between them, and the secp256k1 math, HASH160, Base58Check
and Bech32 code here is shared with Bitcoin unchanged — so a chain is a row of
constants, not an implementation.

```clojure
(btc/address-of-privkey privkey :litecoin)
;=> {:p2pkh "LNf1pU6qC6qQCSYJeRg398wgYXZf5gBWao"
;    :p2wpkh "ltc1qykjmavvs8r65m88urkkql8rn5vnkkh7n57t387"}
(btc/address-of-privkey privkey :dogecoin)      ;=> {:p2pkh "D8aA6Wje…"}  (no SegWit)
(btc/address-of-privkey privkey :bitcoin-cash)  ;=> {:cashaddr "bitcoincash:qqj6t043…"}
```

`address-of-privkey` returns **only the forms that network actually has** — no
`:p2wpkh` for Dogecoin, and `p2wpkh-address` throws there rather than inventing an
HRP. A fabricated address for an unsupported form is how funds reach somewhere
unspendable.

### None of the constants were transcribed from memory

| what | how it was established |
|---|---|
| P2PKH version bytes (LTC `0x30`, DOGE `0x1e`) | Base58Check-**decoded out of real addresses** of those chains. Bitcoin's `0x00` was the control and came out right |
| every address format | a **live THORChain node accepted** each derived address as a destination for that chain. It rejects malformed ones (`unable to parse address`) and it *discriminates*: a Dogecoin-versioned address offered as Litecoin was refused, and an early Litecoin attempt reusing Bitcoin's bech32 checksum was caught the same way |
| CashAddr's 5 generator constants | a real BCH address **round-trips**: its checksum verifies here, and re-encoding the hash it decodes to reproduces the address character-for-character. One wrong constant fails that immediately |
| cross-check | `@scure/base` independently confirms the checksums, and that all forms encode the same hash160 |

**CashAddr is not Bech32.** It shares the charset, which is the trap — the checksum
is a 40-bit BCH code with its own five generators against Bech32's 30-bit one.
Reusing Bech32's polymod produces strings that look exactly like valid addresses
and are not.

### Where this stops, deliberately

- **`wif-encode` refuses the forks.** WIF is a key-export format with no oracle to
  validate against, and the conventional "P2PKH version + 0x80" relationship is not
  asserted unmeasured. It throws rather than emitting a plausible-looking string.
- **Litecoin and Dogecoin are spendable**: they use Bitcoin's transaction format and
  sighash unchanged, so `btc-crypto.tx` works as-is — the network only affects
  addresses.
- **Bitcoin Cash is RECEIVE-ONLY.** It requires `SIGHASH_FORKID` with a BCH-specific
  digest, which is not implemented. `(:spendable? (btc/network :bitcoin-cash))` is
  `false`, and that is checked by a test so it cannot quietly become wrong.
