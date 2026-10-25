(ns kekkai.cli.sign
  "Ed25519 netmap-envelope signing, in ClojureScript.

  A second signer, and that needs the same justification the third *verifier*
  needed. `kekkai.envelope/seal` is JVM-only (`java.security`), which would
  force this CLI to shell out to a JVM for the one command that matters most —
  `netmap publish`. Measured before writing a line of it: the payload
  `kekkai.netmap/publish` produces is **byte-identical** under Clojure and
  ClojureScript for the reference plane, and Ed25519 (RFC 8032) is
  deterministic, so an identical payload gives an identical signature.

  That measurement is not a fact about the language, it is a fact about *this
  data*: maps of eight keys or fewer are array-maps on both runtimes and print
  in insertion order. A netmap that grew a nine-key map would start printing in
  hash order and the two runtimes would silently disagree. So the equality is
  pinned as a test against `kekkai`'s committed fixture rather than assumed —
  if it ever breaks, it breaks in CI and not in a signature someone cannot
  verify.

  What this refuses to do: invent a canonical encoding of its own. The bytes
  that get signed are exactly what `pr-str` produces with namespace-map
  printing pinned off, because that is what the JVM publisher signs and what
  both verifiers already accept."
  (:require [kotoba.lang.text :as str]
            ["node:crypto" :as crypto]))

(defn encode-payload
  "The exact bytes that get signed: UTF-8 of `pr-str`, namespace-map printing
  pinned off.

  Pinned rather than assumed because the default differs between contexts — the
  same trap `kekkai.envelope` documents on the JVM side. A `#:netmap{…}` payload
  is valid EDN that the JVM reads back happily and that a node may not."
  [netmap]
  (.from js/Buffer
         (binding [*print-namespace-maps* false]
           (pr-str netmap))
         "utf8"))

(defn- sha256-hex [buf]
  (-> (.createHash crypto "sha256") (.update buf) (.digest "hex")))

(defn private-key
  "An Ed25519 private key object from base64 PKCS8 — the format
  `kekkai.cacao/generate-identity` persists and `kekkai keygen` writes."
  [private-b64]
  (.createPrivateKey crypto
                     #js {:key (.from js/Buffer private-b64 "base64")
                          :format "der" :type "pkcs8"}))

(defn seal
  "-> the envelope map. `identity` is `{:private-b64 … :public-b64 …}`."
  [netmap {:keys [private-b64 public-b64]}]
  (when-not (and (string? private-b64) (string? public-b64))
    (throw (ex-info "signing a netmap needs an Ed25519 identity"
                    {:type :kekkai/missing-signing-identity})))
  (let [payload (encode-payload netmap)
        signature (.sign crypto nil payload (private-key private-b64))]
    {:netmap/payload-b64 (.toString payload "base64")
     :netmap/signature-b64 (.toString signature "base64")
     :netmap/signer-spki-b64 public-b64
     :netmap/sha256 (sha256-hex payload)}))

(defn envelope-string
  "The envelope as EDN text, printed with the same binding as the payload — an
  envelope a node cannot read is no better than one it cannot verify."
  [envelope]
  (binding [*print-namespace-maps* false]
    (pr-str envelope)))

(defn authority-spki-b64
  "The value a node configures as `:netmap-authority-spki-b64`.

  Published separately from the envelope on purpose: an envelope carrying the
  only copy of its signer's key would authenticate itself."
  [{:keys [public-b64]}]
  public-b64)

(defn generate-authority
  "A fresh Ed25519 identity, in the base64 PKCS8/SPKI shape
  `kekkai.cacao/load-identity` reads — so a key made here can be used by the
  JVM control plane and vice versa."
  []
  (let [{:keys [privateKey publicKey]}
        (js->clj (.generateKeyPairSync crypto "ed25519") :keywordize-keys true)]
    {:private-b64 (.toString (.export privateKey #js {:format "der" :type "pkcs8"})
                             "base64")
     :public-b64 (.toString (.export publicKey #js {:format "der" :type "spki"})
                            "base64")}))

(defn fingerprint
  "A short, human-comparable form of an authority key.

  Operators read this aloud when telling a node which publisher to trust; the
  full SPKI is 44 base64 characters and nobody checks all of them."
  [public-b64]
  (->> (sha256-hex (.from js/Buffer public-b64 "base64"))
       (partition 4)
       (take 4)
       (map #(apply str %))
       (str/join "-")))
