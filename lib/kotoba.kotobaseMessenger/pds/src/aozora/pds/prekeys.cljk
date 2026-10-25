(ns aozora.pds.prekeys
  "app.aozora.convo.registerPrekeys write handler.

  A signed X25519 prekey bundle (identity key + signed prekey + one-time-
  prekey pool) for full X3DH E2E session establishment (see
  yoro-ui.interop.signal). One record per actor under a fixed rkey —
  re-registering (e.g. on prekey rotation) replaces the previous bundle
  (including the WHOLE oneTimePreKeys pool) rather than accumulating
  records, the same deterministic-rkey convention aozora.pds.convo/mark-read
  uses. oneTimePreKeys is NOT per-fetch-consumed the way a stateful prekey
  server tracks OPKs — see the registerPrekeys lexicon's description for why
  (self-sovereign-repo write model has no cross-actor consumption path).

  Single-bundle-per-actor is a real multi-device hazard: signing in on a
  SECOND device silently overwrites the first device's identityKey, breaking
  every peer's existing Double Ratchet session with device 1 without warning
  anyone (no cross-device ratchet-state sync exists — see the messenger
  coverage audit). This handler can't fix that (full multi-device needs
  per-device sessions + fan-out, unbuilt anywhere in kotoba-lang/org-signal
  either), but it CAN stop the silent, undetected part: re-registering with a
  DIFFERENT identityKey than the one already on file is rejected unless the
  caller passes `force true` — an explicit, informed choice, not an accident
  of loading the app on a new browser. Rotating the SAME identityKey's
  signedPreKey (the normal 7-day rotation in yoro-ui.interop.signal/
  ensure-identity!) is always allowed — same device, same identity, no risk."
  (:require [kotoba.lang.text :as str]
            [aozora.pds.repo :as repo]
            [aozora.appview.prekeys :as appview-prekeys]
            [aozora.pds.per-actor :as per-actor]))

(defn- non-blank [s] (when (and (string? s) (seq s)) s))
(defn- now-iso [] (.toISOString (js/Date.)))

(defn- require-auth [input]
  (or (non-blank (:_auth-did input))
      (non-blank (:repo input))))

(defn- existing-bundle [env did]
  (if (nil? env)
    (js/Promise.resolve {:found false})
    (let [[client db] (per-actor/appview-client-db env)]
      (-> (appview-prekeys/get-prekey-bundle client db {:did did})
          (.catch (fn [_] {:found false}))))))

(defn register-prekeys
  "POST app.aozora.convo.registerPrekeys.

  Persists the caller's current X25519 identity key + signed prekey +
  one-time-prekey pool under rkey \"self\". Rejects a re-registration under a
  DIFFERENT identityKey unless `force` is explicitly true (see ns docstring)."
  [client db {:keys [identityKey signedPreKey signedPreKeySig signedPreKeyId oneTimePreKeys updatedAt force _env] :as input}]
  (let [did (require-auth input)
        value (cond-> {:did did
                       :identityKey identityKey
                       :signedPreKey signedPreKey
                       :signedPreKeySig signedPreKeySig
                       :signedPreKeyId signedPreKeyId
                       :updatedAt (or updatedAt (now-iso))}
                (seq oneTimePreKeys) (assoc :oneTimePreKeys (vec oneTimePreKeys)))]
    (if (or (nil? did)
            (str/blank? (or identityKey ""))
            (str/blank? (or signedPreKey ""))
            (str/blank? (or signedPreKeySig ""))
            (nil? signedPreKeyId))
      (js/Promise.resolve {:error "InvalidRequest"
                           :message "identityKey, signedPreKey, signedPreKeySig, signedPreKeyId, and valid session required"})
      (-> (existing-bundle _env did)
          (.then (fn [{:keys [found] existing-key :identityKey}]
                   (if (and found (not= existing-key identityKey) (not= true force))
                     {:error "IdentityConflict"
                      :message "a different identityKey is already registered for this account — this looks like a new device. Existing peer sessions will break if you proceed. Pass force=true to confirm."}
                     (-> (repo/create-record client db {:repo did
                                                        :collection "app.aozora.convo.prekeyBundle"
                                                        :rkey "self"
                                                        :record value})
                         (.then (fn [r] (assoc r :did did)))))))))))
