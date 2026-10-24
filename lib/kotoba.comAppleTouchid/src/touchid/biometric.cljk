(ns touchid.biometric
  "The Touch ID capability — an injected host protocol, mirroring the slice
  of Apple's `LocalAuthentication` framework an agent needs (check
  availability, prompt for a biometric authentication).

  `ITouchID` is the seam: a real implementation would bridge to Apple's
  `LocalAuthentication` framework (`LAContext.evaluatePolicy` with
  `.deviceOwnerAuthenticationWithBiometrics`), which cannot run inside pure
  `.cljc`/JVM/babashka — there is no portable 'real' implementation to ship
  here, only the protocol and a deterministic mock (the Touch ID analogue
  of `godaddy-dns`'s `mock-dns`). A host targeting iOS/macOS (React Native
  bridge, Swift/ObjC interop, etc.) supplies the real implementation.

  Sibling of `kotoba-lang/com-apple-faceid` — same shape, distinct
  `LABiometryType`."
  #?(:clj (:require [kotoba.lang.text :as str])
     :cljs (:require [kotoba.lang.text :as str])))

(defprotocol ITouchID
  "Touch ID host capability."
  (-available? [this]
    "Returns {:available? bool :biometry-type :touch-id/:none
    :reason (optional keyword when unavailable, e.g.
    :not-enrolled/:locked-out/:no-hardware)}.")
  (-authenticate! [this opts]
    "Prompts Touch ID. `opts` is {:reason string (required by Apple's API)
    :fallback-title string (optional)}. Returns
    {:status :success/:user-cancel/:user-fallback/:system-cancel/:lockout/
    :not-available/:error, :error (optional ex-info-shaped map on
    :error)}."))

;; ───────────────────────────── mock ─────────────────────────────

(deftype MockTouchID [available? biometry-type outcome]
  ITouchID
  (-available? [_]
    (if available?
      {:available? true :biometry-type biometry-type}
      {:available? false :biometry-type :none :reason :no-hardware}))
  (-authenticate! [_ {:keys [reason] :as _opts}]
    (when (str/blank? (str reason))
      (throw (ex-info "Touch ID authenticate! requires a :reason string" {:opts _opts})))
    (if (= outcome :error)
      {:status :error :error {:message "mock touch id error"}}
      {:status outcome})))

(defn mock-touchid
  "A deterministic in-memory ITouchID for tests and demos — no device, no
  entitlements. `outcome` (default :success) is the fixed :status
  -authenticate! returns; pass an outcome of :error to get a
  {:status :error :error {...}} result instead."
  [& [{:keys [available? biometry-type outcome]
       :or {available? true biometry-type :touch-id outcome :success}}]]
  (->MockTouchID available? biometry-type outcome))

;; ───────────────────────────── helpers ─────────────────────────────

(defn authenticate-or-throw!
  "Convenience wrapper over -authenticate! — returns the result map on
  :success, throws ex-info for every other :status."
  [touchid opts]
  (let [result (-authenticate! touchid opts)]
    (if (= :success (:status result))
      result
      (throw (ex-info (str "Touch ID authentication failed: " (:status result))
                       result)))))
