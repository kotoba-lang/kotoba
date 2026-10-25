(ns kotoba.annex.identity
  "kotoba-annex の actor identity — **自分の Ed25519 鍵を自己生成**し、その鍵由来の
   did:key が自分の graph（skill build-actor: 「actor は鍵を持つことで自分の graph の
   owner → depth-1 の自己 mint が構造的に authorized。owner hand-off も共有 token も
   要らない」）。したがって credential の受け渡しは発生しない。

   ⚠ **秘密鍵（seed）は `.kotoba-annex/identity.edn` に置き gitignore する。
   git に絶対コミットしない**（cloud-itonami/identity.clj と同じ規約）。"
  (:require [cljs.reader :as reader]
            [ed25519.core :as ed]
            ["fs" :as fs]
            ["path" :as path]
            ["crypto" :as ncrypto]))

(def ^:const identity-dir ".kotoba-annex")
(def ^:const identity-file "identity.edn")

(defn identity-path
  ([] (identity-path (or js/process.env.KOTOBA_ANNEX_HOME (js/process.cwd))))
  ([home] (path/join home identity-dir identity-file)))

(defn- new-seed-hex []
  (ed/hexify (js/Uint8Array. (ncrypto/randomBytes 32))))

(defn load-or-create-identity!
  "seed（32byte Ed25519）を読み込み、無ければ生成して永続化する。
   {:seed-hex :seed :did} を返す。did は鍵由来 did:key（= 自分の graph 名）。"
  ([] (load-or-create-identity! (identity-path)))
  ([p]
   (let [seed-hex (if (fs/existsSync p)
                    (:seed-hex (reader/read-string (fs/readFileSync p "utf8")))
                    (let [h (new-seed-hex)]
                      (fs/mkdirSync (path/dirname p) #js {:recursive true})
                      (fs/writeFileSync p (pr-str {:seed-hex h
                                                   :note "kotoba-annex actor seed — NEVER commit"})
                                        #js {:mode 0600})
                      h))
         seed (ed/unhex seed-hex)]
     {:seed-hex seed-hex
      :seed seed
      :did (ed/did-key-from-seed seed)})))
