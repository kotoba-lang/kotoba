(ns fleet.identity
  "The dispatcher's own key — a narrowly-scoped fleet agent identity, not the
  operator's ambient credentials.

  Two things need it and they are the same key on purpose:
  1. **kotobase.net** — CACAO is self-minted, so the key IS the authority for
     its own tenant graph. Nobody grants the dispatcher anything; it can only
     ever reach the graph its own DID derives.
  2. **receipts** — a governor decision is signed, so a receipt can be checked
     against the enrolled public key in `manifest/fleet-agents.edn` instead of
     being trusted because it was found in a file.

  Enrollment (`manifest/fleet-agents.edn`) records the DID and the grants the
  fleet recognises for it (`fleet-sandbox/*`). Nothing here can advance a pin,
  pass governance quorum, or sign for another agent — the same containment the
  murakumo CI signer has (ADR-2607178000): a stolen copy can at most add noise
  to an append-only log.

  The secret never lands in a repo: it is read from the kagi vault by exact
  item name (`--identity kagi:<item>`), or from a PEM path for a test key."
  (:require ["node:child_process" :as cp]
            ["node:fs" :as fs]
            ["node:crypto" :as crypto]
            [kotoba.lang.text :as str]
            [ed25519.core :as ed]))

(defn- kagi-pem
  "Read ONE item from the kagi vault by exact name. Never enumerates the vault."
  [item]
  (let [root (or (.-FLEET_ROOT js/process.env) (js/process.cwd))
        bin (str root "/orgs/kotoba-lang/kagi/bin/kagi")]
    (when-not (fs/existsSync bin)
      (throw (ex-info (str "kagi CLI not found at " bin
                           " — set FLEET_ROOT to the superproject root") {})))
    (str/trim-newline
     (cp/execFileSync bin #js ["get" item "--compartment" "personal"]
                      #js {:encoding "utf8" :timeout 120000}))))

(defn- pem->seed
  "Raw 32-byte Ed25519 seed from a PKCS8 PEM (JWK .d is the seed, base64url)."
  [pem]
  (js/Uint8Array.
   (js/Buffer.from (.-d (.export (crypto/createPrivateKey pem) #js {:format "jwk"}))
                   "base64url")))

(defn resolve-identity
  "`kagi:<item>` | `pem:<path>` → {:did :seed :source}. The DID is DERIVED from
  the seed, never configured, so a mislabelled key cannot impersonate another."
  [spec]
  (let [[kind v] (str/split (str spec) #":" 2)
        pem (case kind
              "kagi" (kagi-pem v)
              "pem" (fs/readFileSync v "utf8")
              (throw (ex-info (str "identity must be kagi:<item> or pem:<path>, got " spec) {})))
        seed (pem->seed pem)]
    {:seed seed
     :did (ed/did-key-from-seed seed)
     :source (str kind ":" v)}))

(defn sign-hex
  "Ed25519 signature (hex) over `s` — used for governor receipts."
  [{:keys [seed]} s]
  (->> (ed/sign seed (js/Uint8Array. (js/Buffer.from s "utf8")))
       (map #(.padStart (.toString % 16) 2 "0"))
       (apply str)))

(defn verify-hex
  "Check a `sign-hex` signature against a did:key. Counterpart of sign-hex, so a
  receipt can be audited with nothing but the enrolled public DID."
  [did s sig-hex]
  (try
    (ed/verify-did did
                   (js/Uint8Array. (js/Buffer.from s "utf8"))
                   (js/Uint8Array. (js/Buffer.from sig-hex "hex")))
    (catch :default _ false)))

(defn sha256-hex [s]
  (-> (crypto/createHash "sha256") (.update s "utf8") (.digest "hex")))
