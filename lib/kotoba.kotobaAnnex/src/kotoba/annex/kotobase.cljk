(ns kotoba.annex.kotobase
  "kotobase.net backed の store — git-annex の annex key を kotobase.net の
   **実在・deploy 済みの `net.kotobase.store.*` 面**（tenant 隔離 IStore、
   DAG-CBOR ブロック + CID、`kotobase.istore`）に永続化する。
   kotoba.annex.store と同じ store 契約なので directory store と差し替え可能。

   **重要な訂正（2026-07-17 実測）**: 当初は kotobase-server に blob 面を足して
   使う設計だったが、net-kotobase の live worker は kotobase-server ではなく
   `kotobase.istore` を使っており、`net.kotobase.store.{put,get,list,append,read}`
   は **既に kotobase.net で live**（未認証で叩くと `{\"ok\":false,\"error\":
   \"Unauthorized\"}` = 面は存在、認証待ち。実測で確認）。よって **server 変更も
   deploy も不要**で、既存面に CACAO 認証で書く。

   認証は **CACAO 自己発行**（skill build-actor）: actor が自分の Ed25519 鍵を生成し、
   その did:key が自分の graph。`proxy/resolve-viewer` は CACAO を検証して did を
   取り出すだけ（resources は見ない）ので、**自分の鍵 → 自分の tenant 名前空間**で
   完結し、owner の token 受け渡しは要らない。
     aud       = did:web:kotobase.net（pod が enforce、mismatch は 'cacao audience
                 mismatch' で拒否）
     resources = kotoba://op/datom:read + datom:transact + kotoba://graph/<graph>
     headers   = authorization: CACAO <b64> / x-kotoba-did: <iss>

   ⚠ 値サイズ上限: istore の `max-value-bytes` = 900000（900KB）。大きいファイルは
   git-annex の chunking（`chunk=500KiB`）で分割する — 各 chunk が上限内に収まる。"
  (:require [cacao.core :as cacao]
            [kotoba.annex.identity :as ident]))

(def ^:const default-endpoint "https://kotobase.net")
(def ^:const kotobase-aud "did:web:kotobase.net")
(def ^:const annex-coll "annex")
(def ^:const max-value-bytes 900000)

(defn kotobase-resources
  "kotobase graph の CACAO resource scope（cloud-itonami identity-core と同型）。"
  [graph]
  [(str "kotoba://op/datom:read")
   (str "kotoba://op/datom:transact")
   (str "kotoba://graph/" graph)])

(defn mint-auth
  "自分の鍵で kotobase.net 向け CACAO を自己発行し、認証ヘッダを返す。
   graph 既定は自分の did:key（自己所有 graph）。"
  [{:keys [identity graph ttl-seconds] :or {ttl-seconds (* 24 3600)}}]
  (let [{:keys [seed did]} identity
        g (or graph did)
        now (js/Math.floor (/ (js/Date.now) 1000))
        iso #(.toISOString (js/Date. (* 1000 %)))
        minted (cacao/mint {:seed seed
                            :aud kotobase-aud
                            :iat (iso now)
                            :exp (iso (+ now ttl-seconds))
                            :nonce (str (random-uuid))
                            :resources (kotobase-resources g)})]
    (assoc (cacao/auth-header minted) :iss (:iss minted) :graph g)))

(defn- headers [auth]
  #js {"authorization" (:authorization auth)
       "x-kotoba-did" (:x-kotoba-did auth)
       "content-type" "application/json"})

(defn- xrpc [endpoint method auth body fetch]
  (fetch (str endpoint "/xrpc/net.kotobase.store." method)
         #js {:method "POST" :headers (headers auth)
              :body (js/JSON.stringify (clj->js body))}))

(defn- b64 [u8] (.toString (js/Buffer.from u8) "base64"))
(defn- unb64 [s] (js/Buffer.from s "base64"))

(defn kotobase-store
  "opts: {:endpoint :graph :identity :fetch}。identity 省略時は自己生成/読込。
   store 契約の関数は Promise を返す（bin 側で await）。"
  [{:keys [endpoint graph identity fetch]
    :or {endpoint default-endpoint fetch js/fetch}}]
  (let [id (or identity (ident/load-or-create-identity!))
        auth (atom nil)
        auth! (fn [] (or @auth (reset! auth (mint-auth {:identity id :graph graph}))))]
    {:endpoint endpoint :did (:did id)
     :store!   (fn [key bytes]
                 (when (> (.-length bytes) max-value-bytes)
                   (throw (js/Error. (str "value > istore max-value-bytes (" max-value-bytes
                                          ") — use git-annex chunk=500KiB"))))
                 (-> (xrpc endpoint "put" (auth!) {:coll annex-coll :key key
                                                   :val (b64 bytes)} fetch)
                     (.then #(.-ok %))))
     ;; ⚠ **HTTP 200 + エラー body の罠**（2026-07-17 実測）: net.kotobase.store.get は
     ;; キーが無くても **HTTP 200** を返し、body が `{"ok":false,"error":"NotFound"}`。
     ;; `.ok`（HTTP status）だけで判定すると **不在キーを present と誤答**し、
     ;; git-annex は「もう持っている」と見なして **STORE を丸ごとスキップ**する
     ;; （= 何も保存されないのに copy は成功に見える）。必ず **body の :ok と :val** を見る。
     :retrieve (fn [key]
                 (-> (xrpc endpoint "get" (auth!) {:coll annex-coll :key key} fetch)
                     (.then (fn [r] (if (.-ok r) (.json r) nil)))
                     (.then (fn [j]
                              (when (and j (aget j "ok"))
                                (when-let [v (aget j "val")] (unb64 v)))))))
     :present? (fn [key]
                 (-> (xrpc endpoint "get" (auth!) {:coll annex-coll :key key} fetch)
                     (.then (fn [r] (if (.-ok r) (.json r) nil)))
                     (.then (fn [j]
                              (if (and j (aget j "ok") (some? (aget j "val"))) :yes :no)))
                     (.catch (fn [_] :unknown))))
     ;; istore は delete を持たない（content-addressed / append 指向）。REMOVE は
     ;; tombstone を put して present? を false にする（kotobase-server blob 面と同型）。
     :remove!  (fn [key]
                 (-> (xrpc endpoint "put" (auth!) {:coll annex-coll
                                                   :key (str "tomb:" key) :val "1"} fetch)
                     (.then #(.-ok %))))
     :init!    (fn [] true)
     :prepare! (fn [_config] (auth!) true)}))
