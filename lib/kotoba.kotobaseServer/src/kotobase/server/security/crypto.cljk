(ns kotobase.server.security.crypto
  "Rotation-aware authenticated encryption profiles for the peer crypto seam."
  (:require [kotobase.cacao :as cacao]
            #?(:cljs [aes.gcm-siv :refer [gcmsiv]])
            #?(:cljs [sha2.core :as sha2])))

(def ^:private envelope-version 2)
(defn blind-fn [component] #?(:clj component :cljs (js/Promise.resolve component)))
(defn encrypt-fn [bytes] #?(:clj bytes :cljs (js/Promise.resolve bytes)))
(defn decrypt-fn [bytes] #?(:clj bytes :cljs (js/Promise.resolve bytes)))
(def plaintext-profile {:kind :plaintext :blind-fn blind-fn
                        :encrypt-fn encrypt-fn :decrypt-fn decrypt-fn})

#?(:cljs
   (do
     (defn- utf8 [s] (.encode (js/TextEncoder.) s))
     (defn- concat-bytes [& parts]
       (let [n (reduce + (map #(.-length ^js %) parts)) out (js/Uint8Array. n)]
         (loop [offset 0 xs parts]
           (if-let [part (first xs)]
             (do (.set out part offset)
                 (recur (+ offset (.-length ^js part)) (next xs))) out))))
     (defn- key-bytes [label encoded]
       (when-not (seq encoded)
         (throw (ex-info (str "missing " label) {:type :crypto-key-missing :key label})))
       (let [key (cacao/base64->bytes encoded)]
         (when-not (= 32 (.-length key))
           (throw (ex-info (str label " must decode to exactly 32 bytes")
                           {:type :crypto-key-invalid :key label :length (.-length key)})))
         key))
     (defn- u8->vec [^js u8] (vec (js/Array.from u8)))
     (defn- vec->u8 [v] (js/Uint8Array.from (clj->js v)))

     (defn aes-256-gcm-siv-profile
       [{:keys [graph tenant-id block-kind schema-version keyring
                aead-key-b64 blind-key-b64]
         :or {tenant-id "default" block-kind "engine-block" schema-version 1}}]
       (when-not (seq graph)
         (throw (ex-info "graph is required for graph-bound encryption"
                         {:type :crypto-graph-missing})))
       (let [keyring (or keyring {"active" "legacy-v1"
                                  "keys" {"legacy-v1" {"aead" aead-key-b64
                                                        "blind" blind-key-b64}}})
             active (get keyring "active") entries (get keyring "keys")
             _ (when-not (and (string? active) (seq active) (contains? entries active))
                 (throw (ex-info "keyring active key is missing"
                                 {:type :crypto-keyring-invalid :active active})))
             _ (when (> (.-length (utf8 active)) 255)
                 (throw (ex-info "key id exceeds 255 UTF-8 bytes"
                                 {:type :crypto-key-id-invalid})))
             decoded (into {}
                           (map (fn [[kid entry]]
                                  [kid {:aead (key-bytes (str "aead key " kid)
                                                         (get entry "aead"))
                                        :blind (key-bytes (str "blind key " kid)
                                                          (get entry "blind"))}])) entries)
             aead-key (get-in decoded [active :aead])
             blind-key (get-in decoded [active :blind])
             context (str tenant-id "\u0000" graph "\u0000" block-kind "\u0000"
                          schema-version "\u0000")
             aad-for #(utf8 (str "kotobase/aead/v2\u0000" context %))
             nonce-domain (utf8 (str "kotobase/nonce/v2\u0000" context active "\u0000"))
             blind-domain (utf8 (str "kotobase/blind/v2\u0000" context active "\u0000"))]
         {:kind :aes-256-gcm-siv :key-id active :key-ids (set (keys decoded))
          :blind-fn
          (fn [component]
            (js/Promise.resolve
             (str "h1:" (sha2/hmac-sha256-hex (u8->vec blind-key)
                                              (u8->vec (concat-bytes blind-domain
                                                                     (utf8 (pr-str component))))))))
          :encrypt-fn
          (fn [bytes]
            (let [plain (js/Uint8Array. bytes)
                  nonce (vec->u8 (subvec (sha2/hmac-sha256 (u8->vec aead-key)
                                                           (u8->vec (concat-bytes nonce-domain plain)))
                                         0 12))
                  kid-bytes (utf8 active)
                  ciphertext (.encrypt (gcmsiv aead-key nonce (aad-for active)) plain)]
              (js/Promise.resolve
               (concat-bytes (js/Uint8Array.from #js [envelope-version
                                                       (.-length kid-bytes)])
                             kid-bytes nonce ciphertext))))
          :decrypt-fn
          (fn [bytes]
            (try
              (let [envelope (js/Uint8Array. bytes)]
                (when (< (.-length envelope) 31)
                  (throw (ex-info "encrypted block is truncated"
                                  {:type :crypto-envelope-invalid})))
                (let [version (aget envelope 0)]
                  (when-not (= envelope-version version)
                    (throw (ex-info "unsupported encrypted block version"
                                    {:type :crypto-envelope-version :version version})))
                  (let [kid-length (aget envelope 1) nonce-start (+ 2 kid-length)
                        _ (when (> (+ nonce-start 28) (.-length envelope))
                            (throw (ex-info "encrypted block envelope is malformed"
                                            {:type :crypto-envelope-invalid})))
                        kid (.decode (js/TextDecoder.) (.slice envelope 2 nonce-start))
                        selected (get-in decoded [kid :aead])
                        _ (when-not selected
                            (throw (ex-info "encrypted block references unknown key id"
                                            {:type :crypto-key-unavailable :key-id kid})))
                        nonce (.slice envelope nonce-start (+ nonce-start 12))
                        ciphertext (.slice envelope (+ nonce-start 12))]
                    (js/Promise.resolve
                     (.decrypt (gcmsiv selected nonce (aad-for kid)) ciphertext)))))
              (catch :default e (js/Promise.reject e))))}))

     (defn profile [{:keys [security-mode] :as opts}]
       (case security-mode
         ("private" "sealed" :private :sealed) (aes-256-gcm-siv-profile opts)
         ("legacy-public" "public" :legacy-public :public nil) plaintext-profile
         (throw (ex-info "unknown KOTOBASE_SECURITY_MODE"
                         {:type :crypto-mode-invalid :security-mode security-mode}))))))

#?(:clj
   (defn profile [{:keys [security-mode]}]
     (case security-mode
       ("legacy-public" "public" :legacy-public :public nil) plaintext-profile
       (throw (ex-info "production crypto profile is only available on cljs"
                       {:type :crypto-profile-unavailable :security-mode security-mode})))))
