# kotoba-lang/com-apple-touchid

[![CI](https://github.com/kotoba-lang/com-apple-touchid/actions/workflows/ci.yml/badge.svg)](https://github.com/kotoba-lang/com-apple-touchid/actions/workflows/ci.yml)

The Touch ID capability as an injected host protocol, in portable `.cljc` —
`ITouchID` is the seam between "prompt the user for Touch ID" and Apple's
real `LocalAuthentication` framework, so callers write against one small
protocol instead of a platform-specific bridge.

## Why protocol + mock only

Touch ID requires Apple's native `LocalAuthentication` framework
(`LAContext.evaluatePolicy` with `.deviceOwnerAuthenticationWithBiometrics`),
which cannot run inside pure `.cljc`, the JVM, or babashka — there is no
portable "real" implementation to ship here, unlike `kotoba-lang/godaddy-dns`
where the real HTTP calls are still just HTTP. This repo defines the seam
(`touchid.biometric/ITouchID`) that a real host adapter — a Swift/ObjC
bridge, a React Native native module, whatever the target platform is —
implements, plus `mock-touchid`, a deterministic in-memory implementation
for tests and demos with no device and no entitlements.

Sibling of [`kotoba-lang/com-apple-faceid`](https://github.com/kotoba-lang/com-apple-faceid) — same shape, distinct
`LABiometryType`.

See [`kotoba-lang/touchid`](https://github.com/kotoba-lang/touchid) for the
result-shape substrate layer that composes this with other auth factors
(host-port pattern, no network/crypto here either, but a different
abstraction level).

## Usage

```clojure
(require '[touchid.biometric :as bio])

(def touchid (bio/mock-touchid))

(bio/-available? touchid)
;; => {:available? true :biometry-type :touch-id}

(bio/-authenticate! touchid {:reason "Unlock your vault"})
;; => {:status :success}

(bio/authenticate-or-throw! touchid {:reason "Unlock your vault"})
;; => {:status :success}, or throws ex-info for any non-:success status
```

A host wiring up the real framework implements `ITouchID` itself and
passes that implementation everywhere `mock-touchid` appears above.

## Test

```bash
kbb -M:test
```
