(ns atprotocol.profile
  ":kotoba.app/* → atproto profile view への投影 + 旧 W-Protocol 互換 alias
  (ADR-2607071500)。

  正 (kotoba-protocol): :kotoba.app/kind と :kotoba.app/embed-url。
  atproto へ見せる一級 field は `appKind` / `embedUrl` / `appId` /
  `bundleCid` / `appLatest`。embed-url が ipfs:// scheme なら raw CID も
  `embedCid` として付ける (host が bytes を fetch して CID と一致検証できる
  よう — ADR-2607071500 Addendum 5)。

  旧 W-Protocol (performerType / contentMode / uiType — svelte ActorFrame 期
  の規約) は **deprecated compat alias** としてこの層でのみ導出する。
  新規実装はこれらを読まない・書かない。"
  (:require [kotoba.protocol.app :as app]))

(def legacy-aliases
  "W-Protocol field → 導出規則 (すべて :deprecated true)。
  archive (app-aozora-svelte ActorFrame 等) 互換のためだけに残る。"
  {:contentMode {:deprecated true
                 :derive-from :kotoba.app/kind
                 :mapping {"embed" "interactive"
                           "appview" "interactive"
                           "actor" "timeline"
                           nil "timeline"}}
   :uiType {:deprecated true
            :derive-from :kotoba.app/kind
            :mapping {"appview" "appview"
                      "embed" "iframe"
                      "actor" "esm"
                      nil "appview"}}
   :performerType {:deprecated true
                   :note "actor 種別は kotoba 側に対応語彙が無い (人格分類は app の関心ではない) — 固定値"
                   :value "service"}})

(defn- legacy-fields [kind]
  {:contentMode (get-in legacy-aliases [:contentMode :mapping kind]
                        (get-in legacy-aliases [:contentMode :mapping nil]))
   :uiType (get-in legacy-aliases [:uiType :mapping kind]
                   (get-in legacy-aliases [:uiType :mapping nil]))
   :performerType (get-in legacy-aliases [:performerType :value])})

(defn project-app
  "actor が advertise する app manifest (:kotoba.app/* entity) →
  profile view に埋める app 部分。manifest が invalid なら {:error …}。
  opts: {:gateway} — ipfs/ipns embed-url の解決 (kotoba L4 の retrieval)。
  {:include-legacy? true} で W-Protocol alias も付ける (既定 false)。"
  ([manifest] (project-app manifest nil))
  ([manifest {:keys [gateway include-legacy?]}]
   (let [problems (app/validate-manifest manifest)]
     (if (seq problems)
       {:error :invalid-manifest :problems problems}
       (let [kind (:kotoba.app/kind manifest)
             raw-url (:kotoba.app/embed-url manifest)
             resolved (when raw-url
                        (app/resolve-embed-url (app/parse-embed-url raw-url)
                                               {:gateway gateway}))
             view (cond-> {:appId (:kotoba.app/id manifest)
                           :appKind kind
                           :appVersion (:kotoba.app/version manifest)}
                    (and resolved (:url resolved)) (assoc :embedUrl (:url resolved))
                    ;; embed-url が ipfs:// の場合、host が bytes を fetch して
                    ;; CID と一致検証できるよう raw CID もそのまま渡す (ADR-2607071500
                    ;; Addendum 5 — :kotoba.app/bundle-cid は manifest 作者が別途
                    ;; セットしないと出ないが、これは embed-url 自体から常に導出できる)。
                    (and resolved (:cid resolved)) (assoc :embedCid (:cid resolved))
                    (:kotoba.app/bundle-cid manifest) (assoc :bundleCid (:kotoba.app/bundle-cid manifest))
                    (:kotoba.app/latest manifest) (assoc :appLatest (:kotoba.app/latest manifest))
                    (seq (:kotoba.app/caps manifest)) (assoc :appCaps (vec (:kotoba.app/caps manifest)))
                    ;; kind=actor: wasm モジュール群を CID 解決 URL + imports に投影
                    (seq (:kotoba.app/wasm manifest))
                    (assoc :appWasm
                           (mapv (fn [{:keys [cid imports]}]
                                   (let [r (app/resolve-embed-url
                                            (app/parse-embed-url (str "ipfs://" cid))
                                            {:gateway gateway})]
                                     {:cid cid
                                      :url (:url r)
                                      :imports (vec (or imports []))}))
                                 (:kotoba.app/wasm manifest))))]
         (if include-legacy?
           (merge view (legacy-fields kind))
           view))))))
