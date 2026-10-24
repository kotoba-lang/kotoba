(ns kotoba.kip.quorum
  "What makes a KIP Final: >= threshold distinct valid signatures from an
  allow-list, over one canonical payload.

  Deliberately the same shape as `kagami.grant/admit-quorum`, which decides
  canonical west pin advances — allow-set plus threshold plus distinct valid
  signatures, crypto injected, verdict plus reasons out. Two quorum mechanisms
  with different shapes in one workspace would be two things to get right.

  ## Nothing here does crypto

  `verify-fn` and `did->pubkey-hex` are arguments. That keeps this namespace
  loadable from nbb with no dependencies, and it keeps the key list out of the
  library: the allow-list is `manifest/fleet-keys.edn` `:canonical` in the
  superproject — the same one kagami reads — and a copy of it here would be a
  second answer to who may sign.

  The operator-side wiring lives in the superproject at
  `scripts/verify-kip-quorum.cljs` (node:crypto + `kagami.did` + fleet-keys)."
  (:require [kotoba.lang.text :as str]))

;; --------------------------------------------------------------- the payload

(def ^:private signed-fields
  "The fields a signature commits to, in this order. Order is protocol: change
  it and every existing signature stops verifying, which is correct but is a
  breaking change to the wire and needs its own KIP."
  [:kip/id :kip/number :kip/track])

(defn- normalise-surfaces
  "`:kip/surfaces` is a set written as a vector. Sorted and de-duplicated so a
  cosmetic reorder does not invalidate a quorum.

  This is the same line the rest of the design draws: KIP-0001 exempts changes
  that leave the parsed value identical, and compares parsed values rather than
  text. A reordered list is a null edit; an added or removed surface is not, and
  that still breaks every signature."
  [kip]
  (let [s (:kip/surfaces kip)]
    (vec (sort (distinct (map str (if (coll? s) s [])))))))

(defn content-digest
  "Hash of the KIP with the quorum stripped.

  Signatures accumulate inside the document, so the digest must not cover them
  — otherwise the first signature changes what the second one is signing and a
  quorum can never form.

  `:kip/status` is excluded for the same class of reason. A quorum signature is
  what MOVES a KIP to :final, so it has to be made while the document still
  says :last-call; if status were covered, admitting the KIP would invalidate
  the very signatures that admitted it. Measured 2026-08-16: signing at
  :last-call and then setting :final changed the digest and broke both
  signatures. The signature approves the content and its admission, not the
  state the admission produces.

  Everything else is covered, including the prose and `:kip/last-call-started`:
  a Final KIP whose specification was edited afterwards, or whose clock was
  backdated, is a different KIP, and this is what notices.

  Keys are sorted so the digest does not depend on map ordering."
  [hash-fn kip]
  (let [stripped (-> (dissoc kip :kip/quorum :kip/status)
                     ;; normalised here too, or a reorder would change the
                     ;; digest while leaving the surfaces slot identical — the
                     ;; two halves of the payload must agree about what a
                     ;; surface list is.
                     (assoc :kip/surfaces (normalise-surfaces kip)))
        ;; sort-by str, NOT (sort (map str ...)) — the latter hands `get` a
        ;; string key, every lookup returns nil, and the digest then depends
        ;; only on which keys exist. Caught by
        ;; `editing-a-final-kip-invalidates-its-quorum`, which is the one
        ;; property this whole namespace exists to provide.
        ordered (mapv (fn [k] [(str k) (pr-str (get stripped k))])
                      (sort-by str (keys stripped)))]
    (hash-fn (pr-str ["kip-content/v1" ordered]))))

(defn canonical-str
  "The deterministic signing payload for admitting `kip` to :final."
  [hash-fn kip]
  (pr-str (into ["kip-quorum/v1"]
                (concat (map #(get kip %) signed-fields)
                        [(normalise-surfaces kip)
                         (content-digest hash-fn kip)]))))

;; ---------------------------------------------------------------- signing
(defn sign
  "-> {:signer did :signature hex :at iso}. `sign-fn` takes the payload string.

  The caller supplies `signer` rather than deriving it from the key, matching
  kagami: the CLI knows which did it loaded, and deriving it here would mean
  this namespace handling key material."
  [hash-fn sign-fn signer at kip]
  {:signer signer
   :signature (sign-fn (canonical-str hash-fn kip))
   :at at})

;; ---------------------------------------------------------------- admission
(defn admit
  "Does this KIP carry a quorum?

  ctx: {:policy {:allow #{did} :threshold n}
        :verify-fn (fn [pubkey-hex payload sig-hex] bool)
        :did->pubkey-hex (fn [did] hex)
        :hash-fn (fn [s] hex)}

  -> {:verdict :admit|:reject :valid-signers #{} :claimed n :reasons []}

  A signature from a did outside `:allow` is not an error, it just does not
  count — same as kagami. What is an error is a signature that claims an
  allowed did and does not verify, because that is either tampering or a
  payload disagreement, and both need saying."
  [kip signatures {:keys [policy verify-fn did->pubkey-hex hash-fn]}]
  (let [{:keys [allow threshold]} policy
        payload (canonical-str hash-fn kip)
        sigs (filter map? signatures)
        checked (mapv (fn [{:keys [signer signature] :as s}]
                        (let [allowed? (contains? (set allow) signer)
                              ok? (and allowed?
                                       (some? signature)
                                       (try (boolean
                                             (verify-fn (did->pubkey-hex signer)
                                                        payload signature))
                                            (catch #?(:clj Exception :cljs :default) _ false)))]
                          (assoc s :allowed? allowed? :valid? ok?)))
                      sigs)
        valid (into #{} (comp (filter :valid?) (map :signer)) checked)
        bad-allowed (filterv #(and (:allowed? %) (not (:valid? %))) checked)
        reasons (cond-> []
                  (empty? allow) (conj :empty-allow-list)
                  (nil? threshold) (conj :no-threshold)
                  (seq bad-allowed) (conj :invalid-signature-from-allowed-did)
                  (< (count valid) (or threshold 1)) (conj :quorum-not-met))]
    {:verdict (if (seq reasons) :reject :admit)
     :valid-signers valid
     :claimed (count sigs)
     :invalid-from-allowed (mapv :signer bad-allowed)
     :payload-digest (content-digest hash-fn kip)
     :reasons reasons}))

(defn verifier
  "A `:verify-fn` for `kotoba.kip.core/quorum-signers`, closing over `ctx`.

  `quorum-signers` calls it per signature and keeps the ones it approves, so
  this returns a predicate rather than a verdict. Use `admit` when you want the
  reasons; use this when you want core's document-level check to stop counting
  signatures it cannot verify."
  [kip ctx]
  (let [{:keys [valid-signers]} (admit kip (:kip/quorum kip) ctx)]
    (fn [{:keys [signer]}] (contains? valid-signers signer))))

(defn explain
  "One line per signature, for a report. Says allowed/valid separately so
  `skipped` and `failed` cannot be read as each other."
  [kip signatures ctx]
  (let [{:keys [valid-signers]} (admit kip signatures ctx)]
    (mapv (fn [{:keys [signer]}]
            (str (subs (str signer) 0 (min 28 (count (str signer)))) "…  "
                 (cond (contains? valid-signers signer) "valid"
                       (contains? (set (:allow (:policy ctx))) signer) "ALLOWED BUT SIGNATURE INVALID"
                       :else "not in allow-list (does not count)")))
          (filter map? signatures))))

(defn policy-summary [{:keys [allow threshold]}]
  (str threshold " of " (count allow) " (" (str/join ", " (map #(subs (str %) 8 20) (sort allow))) "…)"))
