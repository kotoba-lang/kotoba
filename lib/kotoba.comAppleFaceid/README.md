# kotoba-lang/com-apple-faceid

[![CI](https://github.com/kotoba-lang/com-apple-faceid/actions/workflows/ci.yml/badge.svg)](https://github.com/kotoba-lang/com-apple-faceid/actions/workflows/ci.yml)

The Face ID capability as a portable `.cljc` protocol — `IFaceID`, an
`-available?`/`-authenticate!` seam that lets an auth flow depend on
"prompt biometrics, get a status back" without depending on Apple's SDK.

## Why protocol + mock only

Face ID authentication runs through Apple's native `LocalAuthentication`
framework (`LAContext.evaluatePolicy`, `LABiometryType.faceID`) — there is
no way to call that from pure `.cljc` on the JVM, ClojureScript, or
babashka; it only exists inside an iOS/macOS process with the real
hardware. So unlike `kotoba-lang/godaddy-dns` (where the real HTTP-backed
implementation ships alongside the protocol), this repo ships only the
`IFaceID` protocol and a deterministic `mock-faceid` for tests and demos.
A real implementation lives in whatever host actually has access to
`LocalAuthentication` (a native app shell, a React Native bridge, …) and
implements `IFaceID` there.

Sibling of [`kotoba-lang/com-apple-touchid`](https://github.com/kotoba-lang/com-apple-touchid)
— identical shape, distinct `LABiometryType`.

See [`kotoba-lang/faceid`](https://github.com/kotoba-lang/faceid) for the
result-shape substrate layer that composes this with other auth factors
(host-port pattern, no network/crypto here either, but a different
abstraction level).

## Usage

```clojure
(require '[faceid.biometric :as biometric])

(def faceid (biometric/mock-faceid))

(biometric/-available? faceid)
;; => {:available? true :biometry-type :face-id}

(biometric/-authenticate! faceid {:reason "Unlock notes"})
;; => {:status :success}

(biometric/authenticate-or-throw! faceid {:reason "Unlock notes"})
;; => nil, or throws ex-info on anything other than :success
```

## Test

```bash
kbb -M:test
```
