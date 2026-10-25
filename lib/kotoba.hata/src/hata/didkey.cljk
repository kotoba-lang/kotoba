(ns hata.didkey
  "app DID → IPNS name の導出（ADR-2610082200 §9・§14）。

  「app DID だけから開ける」の DID 側の半分: did:key の ed25519 鍵を取り
  出し、IPNS name を導く。codec 依存（multiformats / ipns）なので pure core
  には入れず、codec classpath 上でのみ読める。鍵の生成も検証もしない —
  形の分解と名前の導出だけ。"
  (:require [ipns.core :as ipns]
            [multiformats.core :as mf]))

(def ^:private ed25519-pub-multicodec [0xed 0x01])

(defn did-key-bytes
  "did:key:z6Mk... → base58btc-decode 済みの multicodec 付き鍵 bytes。
  形不良は throw させず nil — 導出の失敗は「測れなかった」の意味で返る。"
  [did]
  (when (and (string? did) (.startsWith did "did:key:z"))
    (try
      (mf/base58btc-decode (subs did (count "did:key:z")))
      (catch #?(:clj Throwable :cljs :default) _ nil))))

(defn did-key-pubkey
  "did:key の ed25519 公開鍵 32 bytes、または nil（ed25519 以外・形不良）。"
  [did]
  (let [bs (did-key-bytes did)]
    (when (and bs
               (<= 34 (count bs))
               (= ed25519-pub-multicodec (vec (take 2 bs))))
      (vec (take 32 (drop 2 bs))))))

(defn did-key->ipns-name
  "app DID から IPNS name（k51...）を導く。導けなければ nil — 呼び出し側は
  「測れなかった」に落とし、推測した名前で開かない。"
  [did]
  (when-let [pubkey (did-key-pubkey did)]
    (ipns/pubkey->name pubkey)))

(defn pubkey->did-key
  "ed25519 公開鍵 32 bytes → did:key 文字列（テストと帳簿の照合用）。"
  [pubkey]
  (str "did:key:z" (mf/base58btc (into ed25519-pub-multicodec pubkey))))
