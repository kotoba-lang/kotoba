# faceid

FaceID substrate for kotoba-lang.

Stores only local-device authentication request and attestation metadata. Raw
face images, embeddings, or templates are invalid.

For the minimal `IFaceID` protocol + mock (Apple's proprietary
LocalAuthentication capability as a host-injected seam, zero deps, no host
assumptions), see [kotoba-lang/com-apple-faceid](https://github.com/kotoba-lang/com-apple-faceid).
This repo is the result-shape/substrate layer — device registry, replay
prevention, production LocalAuthentication adapter — consumed by
[kotoba-lang/authentication](https://github.com/kotoba-lang/authentication).
