(ns saifu.sign
  "policy-gated SIGN_MODE_DIRECT signing through the wallet signer seam.

  **鍵は kagi の中から出さない**（ADR-2608039900 決定 1）: この ns は
  `saifu.tx` が正準化した SignDoc の sha256 digest を `wallet.signer/Signer`
  （本番: kagi.chain-signer/vault-signer — 全署名が governor 検閲 + 台帳）に
  渡し、64 byte r‖s の Cosmos 署名に組み立てるだけ。秘密鍵はここに来ない。

  **署名の前に必ず policy gate**（決定 2〜4）: `sign!` は `saifu.policy/gate`
  の disposition が `:commit` のときだけ署名し、`:escalate` / `:hold` は
  拒否として **データで**返す（例外ではない — escalate は『人間が承認する
  まで進めない』という正常な状態）。`spent` は呼び出し側が kagi の
  append-only 台帳から出す（メモリのカウンタではない — 決定 3）。

  broadcast はまだ無い（実装順 5 番目、未着手）。"
  (:require [saifu.policy :as policy]
            [saifu.tx :as tx]
            [wallet.signer :as signer]))

#?(:clj
   (defn sha256
     "SHA-256（JDK — 暗号プリミティブは機構、自前実装しない）。
     octet vector / byte-array のどちらも受ける。"
     ^bytes [bs]
     (.digest (java.security.MessageDigest/getInstance "SHA-256")
              (if (bytes? bs) bs (byte-array (map unchecked-byte bs)))))
   :cljs
   (defn sha256 [_]
     (throw (js/Error. "saifu.sign/sha256: not yet implemented for cljs"))))

#?(:clj
   (defn signature64
     "{:r :s}（wallet.signer/sign-digest! の返り値）→ Cosmos の 64 byte
     r‖s（32+32 big-endian 固定長）。DER でも recovery byte 付きでもない。"
     ^bytes [{:keys [r s]}]
     (let [out (byte-array 64)
           put! (fn [^java.math.BigInteger n ^long offset]
                  (let [^bytes b (.toByteArray n)
                        len (alength b)]
                    (if (<= len 32)
                      (System/arraycopy b 0 out (+ offset (- 32 len)) len)
                      (System/arraycopy b (- len 32) out offset 32))))]
       (put! r 0)
       (put! s 32)
       out))
   :cljs
   (defn signature64 [_]
     (throw (js/Error. "saifu.sign/signature64: not yet implemented for cljs"))))

(defn pubkey33
  "Signer の compressed secp256k1 公開鍵（AuthInfo と address 導出が使う形）。"
  [sgnr path]
  (signer/compress (signer/public-key64 sgnr path)))

(defn sign!
  "policy gate を通してから SignDoc に署名する。

    sgnr  … wallet.signer/Signer（本番は kagi）
    path  … BIP-44 導出パス（Cosmos は m/44'/118'/0'/0/0）
    authz … {:policy … :request … :spent … :now …}（saifu.policy/gate の引数。
             spent は kagi 台帳から）
    doc   … {:body … :auth-info … :chain-id … :account-number …}
             （saifu.tx の builders の出力）

  → {:signed {:sign-doc :digest :signature :tx-raw} :decision …}
    または {:refused decision}（:commit 以外 — escalate/hold はデータ）。"
  [sgnr path authz doc]
  #?(:clj
     (let [{:keys [policy request spent now]} authz
           decision (policy/gate policy request spent now)]
       (if (not= :commit (:disposition decision))
         {:refused decision}
         (let [sd (tx/sign-doc-bytes doc)
               digest (sha256 sd)
               sig64 (signature64 (signer/sign-digest! sgnr path digest))]
           {:signed {:sign-doc sd
                     :digest (vec digest)
                     :signature (vec sig64)
                     :tx-raw (tx/tx-raw-bytes {:body (:body doc)
                                               :auth-info (:auth-info doc)
                                               :signatures [(vec sig64)]})}
            :decision decision})))
     :cljs (throw (js/Error. "saifu.sign/sign!: not yet implemented for cljs"))))
