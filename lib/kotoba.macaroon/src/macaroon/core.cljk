(ns macaroon.core
  "Macaroons: a bearer token you can narrow without asking anyone.

  The whole construction is one idea. The token carries a chained MAC —

      sig₀ = HMAC(root-key, identifier)
      sigₙ = HMAC(sigₙ₋₁, caveatₙ)

  — so **anyone holding the token can append a caveat and recompute the
  chain, and nobody can remove one**, because removing a caveat means
  inverting an HMAC. Attenuation needs no key, no round trip and no
  registrar; only the mint and the verify need the root key.

  That is the property this library exists for, and it is the one the tests
  are about. Everything else here is bookkeeping.

  ## What a macaroon is *not*

  **It is a bearer token.** Whoever holds it can use it, and can hand it to
  anyone. There is no holder key, so possession is authority — which is why
  `:holder` caveats exist and why binding one to a principal is a caveat
  rather than a property of the format. `org-biscuitsec` is the same idea
  with public-key attenuation instead, and the two are in this workspace for
  exactly that contrast.

  **It does not decide anything.** Verification answers *is this token
  intact, and are its caveats met*. What the resulting authority covers is
  `authority`'s question, and `macaroon.authority` is the one-way door
  between them. A verified macaroon is inert evidence (root ADR-2608159400),
  not a capability.

  ## Crypto is injected, all of it

  `hmac-fn` is `(fn [key data] bytes)`. There is no default, for the reason
  `blind`'s README gives: a storage or token layer that owns keys is a layer
  that has to be trusted with them. `seal-fn` / `unseal-fn` are only needed
  for third-party caveats.

  ## Wire format

  `serialize` emits canonical EDN. **Byte compatibility with libmacaroons v1
  or v2 is not implemented and not claimed** — no external implementation has
  read anything this produces, and until one has, saying \"macaroon format\"
  would be the kind of claim `org-apache-parquet` learned to distrust from
  inside its own test suite."
  (:require [kotoba.lang.text :as str]
            [macaroon.caveat :as cav]))

(def version "macaroon/edn-v1")

(defn- chain
  "Fold caveats into the signature, root-first. One function, so mint and
  verify cannot drift."
  [hmac-fn root-key identifier caveats]
  (reduce (fn [sig c]
            (hmac-fn sig (cav/canonical c)))
          (hmac-fn root-key identifier)
          caveats))

(defn mint
  "A macaroon over `identifier`, signed with `root-key`.

  The identifier is what the verifier uses to find the root key again, so it
  is public. It must not be the key, and it must not be empty — an empty
  identifier makes every macaroon under one key share a signature prefix."
  [{:keys [location identifier root-key hmac-fn]}]
  (when (str/blank? (str identifier))
    (throw (ex-info "a macaroon needs a non-empty identifier"
                    {:type :macaroon/invalid-identifier})))
  (when-not (fn? hmac-fn)
    (throw (ex-info "hmac-fn is required — this library owns no crypto"
                    {:type :macaroon/no-hmac})))
  {:macaroon/version version
   :macaroon/location location
   :macaroon/identifier identifier
   :macaroon/caveats []
   :macaroon/signature (vec (hmac-fn root-key identifier))})

(defn attenuate
  "Append a first-party caveat. **Needs no key** — that is the point.

  The new signature is `HMAC(old-signature, caveat)`, so the holder can do
  this offline, and the result is a strictly weaker token that the same
  verifier accepts."
  [m caveat hmac-fn]
  (let [c (cav/caveat caveat)]
    (-> m
        (update :macaroon/caveats conj c)
        (assoc :macaroon/signature
               (vec (hmac-fn (:macaroon/signature m) (cav/canonical c)))))))

(defn attenuate-all [m caveats hmac-fn]
  (reduce (fn [acc c] (attenuate acc c hmac-fn)) m caveats))

(defn add-third-party
  "A caveat another service must discharge.

  `caveat-key` is sealed **to the current signature**, so only a verifier
  that has replayed the chain to this exact point can recover it. That is
  what binds the discharge to this position in this token rather than to the
  token as a whole."
  [m {:keys [location caveat-key identifier]} {:keys [hmac-fn seal-fn]}]
  (when-not (fn? seal-fn)
    (throw (ex-info "third-party caveats need seal-fn" {:type :macaroon/no-seal})))
  (let [vid (vec (seal-fn (:macaroon/signature m) caveat-key))
        c {:caveat/kind :opaque
           :caveat/predicate {:third-party/location location
                              :third-party/identifier identifier
                              :third-party/vid vid}}]
    (attenuate m c hmac-fn)))

(defn signature-of
  "Recompute the signature from `root-key`. The verifier's half of `mint`."
  [m root-key hmac-fn]
  (vec (chain hmac-fn root-key (:macaroon/identifier m) (:macaroon/caveats m))))

(defn intact?
  "Does the chain recompute? Answers only integrity, never authority."
  [m root-key hmac-fn]
  (= (vec (:macaroon/signature m)) (signature-of m root-key hmac-fn)))

(defn verify
  "`{:ok? bool :reason kw :caveats {...}}` — intact, and every caveat met.

  Reasons are distinguished because they are acted on differently: a token
  that does not recompute is an attack or a bug, and a token whose `:before`
  has passed is Tuesday.

  A caveat kind the verifier does not understand fails **closed**: `satisfied?`
  returns false for it, so an unrecognised restriction cannot be read as an
  absent one."
  [m {:keys [root-key hmac-fn now holder opaque-verify]}]
  (cond
    (not= version (:macaroon/version m))
    {:ok? false :reason :unknown-version :version (:macaroon/version m)}

    (not (intact? m root-key hmac-fn))
    {:ok? false :reason :signature-mismatch}

    :else
    (let [ctx {:now now :holder holder}
          results (mapv (fn [c] [c (cav/satisfied? c ctx opaque-verify)])
                        (:macaroon/caveats m))
          unmet (mapv first (remove second results))]
      (if (seq unmet)
        {:ok? false :reason :caveat-not-met :unmet unmet}
        {:ok? true :reason :verified :caveats (count results)}))))

(defn serialize [m] (pr-str (into (sorted-map) m)))
