;; kotoba.signal.x25519 — raw 32-byte X25519 (RFC 7748) Diffie-Hellman for
;; ClojureScript, via @noble/curves (audited pure-JS/WASM-adjacent — no native
;; bindings, runs in browsers/Workers/Node alike). This is the CLJS sibling of
;; kotoba.signal.x25519 (JVM, java.security's "XDH" provider) — same public
;; API shape, different backend, because there is no shared JCA-equivalent
;; between the two platforms. See the package README "Why two backends".
;;
;;   (require '[kotoba.signal.x25519 :as x25519])
;;   (x25519/generate-keypair)          ;=> {:priv Uint8Array(32) :pub Uint8Array(32)}
;;   (x25519/dh my-priv their-pub)      ;=> Uint8Array(32) shared secret (RFC 7748 X25519())
(ns kotoba.signal.x25519
  (:require ["@noble/curves/ed25519.js" :refer [x25519]]))

(defn generate-keypair
  "Fresh X25519 keypair -> {:priv Uint8Array(32) :pub Uint8Array(32)}."
  []
  (let [priv (.randomPrivateKey (.-utils x25519))]
    {:priv priv :pub (.getPublicKey x25519 priv)}))

(defn dh
  "X25519(my-raw-priv, their-raw-pub) -> Uint8Array(32) shared secret.
   Commutative: dh(a-priv, b-pub) == dh(b-priv, a-pub) for a matching keypair —
   the property X3DH / Double Ratchet rely on for both sides to derive the
   same secret without ever exchanging it directly."
  [my-priv their-pub]
  (.getSharedSecret x25519 my-priv their-pub))
