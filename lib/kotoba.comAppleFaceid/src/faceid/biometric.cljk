(ns faceid.biometric
  "The Face ID capability — an injected host protocol.

  `IFaceID` is the seam: a real implementation would bridge to Apple's
  `LocalAuthentication` framework (`LAContext.evaluatePolicy` with
  `.deviceOwnerAuthenticationWithBiometrics`, distinguished by
  `LABiometryType.faceID`), which cannot run inside pure `.cljc`/JVM/
  babashka — there is no portable 'real' implementation to ship here,
  only the protocol and a deterministic mock. A host (an iOS/macOS app
  shell, a React Native bridge, whatever calls into Apple's frameworks)
  supplies the real `IFaceID`; this repo lets the rest of a kotoba-lang
  auth flow depend on the shape of that capability without depending on
  Apple's SDK at all.

  Sibling of `kotoba-lang/com-apple-touchid` — same shape, distinct
  `LABiometryType`."
  #?(:clj (:require [kotoba.lang.text])
     :cljs (:require [kotoba.lang.text])))

(defprotocol IFaceID
  "Face ID host capability."
  (-available? [this]
    "Returns {:available? bool :biometry-type :face-id/:none
    :reason (optional keyword when unavailable, e.g.
    :not-enrolled/:locked-out/:no-hardware)}.")
  (-authenticate! [this opts]
    "Prompts Face ID with the given `:reason` string (required by
    Apple's API; `opts` is {:keys [reason fallback-title]}). Returns
    {:status :success/:user-cancel/:user-fallback/:system-cancel/
    :lockout/:not-available/:error, :error (optional ex-info-shaped
    map on :error)}."))

(defrecord MockFaceID [available? biometry-type outcome]
  IFaceID
  (-available? [_]
    (if available?
      {:available? true :biometry-type biometry-type}
      {:available? false :biometry-type :none :reason :no-hardware}))
  (-authenticate! [_ {:keys [reason] :as _opts}]
    (cond
      (not available?)
      {:status :not-available}

      (nil? reason)
      {:status :error
       :error {:type :invalid-argument :message "reason is required"}}

      :else
      {:status outcome})))

(defn mock-faceid
  "A deterministic in-memory `IFaceID` for tests and demos — no device,
  no user interaction. `outcome` is the `:status` `-authenticate!` will
  always return (default `:success`); `available?`/`biometry-type` fix
  what `-available?` reports."
  [& [{:keys [available? biometry-type outcome]
       :or {available? true biometry-type :face-id outcome :success}}]]
  (->MockFaceID available? biometry-type outcome))

(defn authenticate-or-throw!
  "Convenience wrapper: calls `-authenticate!` and throws `ex-info` on
  anything other than `:success`, so callers that only want the happy
  path (and are fine with an exception otherwise) don't have to branch
  on `:status` themselves. Returns nil on success."
  [faceid opts]
  (let [{:keys [status] :as result} (-authenticate! faceid opts)]
    (when (not= status :success)
      (throw (ex-info (str "Face ID authentication did not succeed: " status)
                       result)))
    nil))
