# touchid

TouchID substrate for kotoba-lang.

Stores only local-device authentication request and attestation metadata. Raw
fingerprint samples or templates are invalid.

For the minimal `ITouchID` protocol + mock (Apple's proprietary
LocalAuthentication capability as a host-injected seam, zero deps, no host
assumptions), see [kotoba-lang/com-apple-touchid](https://github.com/kotoba-lang/com-apple-touchid).
This repo is the result-shape/substrate layer — device registry, replay
prevention, production LocalAuthentication adapter — consumed by
[kotoba-lang/authentication](https://github.com/kotoba-lang/authentication).
