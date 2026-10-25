# Kotoba Identity v1 — first-party verification components

The current profile is v2 with a Web-first reviewed route and separately weighted
app route; see [weighted trust routes](weighted-trust-routes.md). The passport
mechanism described below remains the app-route verifier.

This release adds working cryptographic verification and identity state transitions.
It does not turn the pre-existing structural method catalog into an automated
legal eKYC provider. Production enrollment remains closed until the integration
and operational items below have been completed. Self is not required by these
components. There is no ZK prover, selective-disclosure proof, face matcher,
NFC web API or deployed enrollment service in this release.

## Implemented trust path

1. `ekyc.passport/verify-passport` verifies CMS SignedData using PKI.js/WebCrypto,
   an explicitly configured CSCA trust set, fresh CRLs and current certificate
   validity. The caller cannot supply a trusted root in an enrollment request.
   Embedded revocation material is replaced by configured lists; no network
   fetching from certificate-supplied URLs occurs. Unknown trust or stale lists
   stop verification.
2. It parses ICAO LDS Security Object version 0, SHA-256/384/512, matches the
   authenticated DG1 and DG2 hashes, checks TD3 MRZ checksums/calendar dates,
   document expiry and adulthood. This is deliberately a narrow profile:
   SHA-1, LDS version 1, TD1/TD2, expired signing certificates, unsupported
   algorithms or malformed encodings do not fall back to an assumed pass.
3. The output is `document-authentic`, with `holder-status=review-required`.
   Passive authentication cannot establish live chip possession or identify
   the person operating the device. NFC success and client booleans cannot
   establish either fact. Copied signed passport bytes remain valid bytes.
4. A deployment-secret HMAC converts the private document key into an internal
   tag. Raw MRZ, passport number, birth date and portrait never enter the public
   credential. Keep the HMAC scope stable at the issuer; plan key-version
   migration before rotation so document uniqueness does not reset.
5. The applicant proves control of a key bound to an authenticated account and
   server-issued one-time challenge. A separate registered operator performs
   supervised live document/portrait comparison and records liveness, scope,
   sanctions/PEP/adverse-media review and a private evidence reference. The
   operator cannot approve themselves. The document digest and portrait digest
   in the signed decision must match the verified upload.
6. `identity-policy/transition` produces the next state and pending effects.
   `identity-authority/execute` releases effects only after the private canonical
   store confirms CAS with the expected next revision and audit receipt.
   A conflict retries from fresh state; unconfirmed/unavailable storage emits
   no issuance/inference effect. Caller-controlled `*-verified` flags are never
   accepted by a public route: these are internal host events.
7. `identity-crypto/issue` signs an Ed25519 JWS credential with the exact bound
   holder key, pairwise subject, audience, adult attribute, profile, issuance/
   expiry and status identifier. JWT NumericDate claims use seconds; internal
   lifecycle timestamps use milliseconds. It is a Kotoba JWT profile, not a
   claim of SD-JWT or W3C credential conformance.
8. Presentation requires the holder signature over the credential digest,
   exact service audience and a fresh challenge, plus a current online status
   result. The admission host must atomically consume the challenge before
   granting access. A valid credential alone is not a research scope or AML
   clearance. Revocation updates identity and credential state; expired
   screening/scope prevents free-quota reservations.
9. Free reservations are tied to principal, UTC day and unique request ID, stop
   at 50 per day and return only a `free` execution effect. The host must persist
   the reservation before dispatch and recheck revocation before a queued job
   starts. No automatic billing or blind retry of uncertain inference outcomes.

## What deduplication establishes

The private document tag prevents reusing the same document across accounts in
one issuer deployment. It does **not** prove one-person-one-account across
multiple passports, renewed documents or countries. Those cases require a
reviewed account-linking process. Do not advertise a universal human nullifier.
Pairwise identifiers and audience-specific holder keys reduce cross-service
linkability, but the issuer remains trusted and sees the evidence during review.
This is not zero-knowledge verification.

## Canonical state and data handling

Production authority: `https://kotobase.net`.
Logical database: `kotoba-identity`; private tenant ref:
`kotobase/db/<provisioned-tenant-graph>/kotoba-identity`.
Snapshot/evidence block codec: encrypted DAG-CBOR; datoms contain CID references,
policy versions and access-controlled audit metadata, not document bytes.
Encryption-key custody, tenant authorization, CID verification and atomic pointer
updates belong to the production Kotobase host. `read!` and `cas!` are currently
ports; **that authenticated storage host has not been implemented or provisioned
by this release**. Test ports are fixtures, not persistence evidence.

No raw document, MRZ key, private key or portrait should enter analytics, prompt
logs, model requests or public chain storage. Public-chain integration is not
required in v1. If introduced later, publish only reviewed key/status commitments,
not per-person raw identifiers or revocation events that create tracking signals.
Retention, deletion, reviewer access, appeals and permitted operating regions must
be documented before collecting real customer evidence.

## iPhone capture host

`native/ios` is a small CoreNFC transport using an immutable NFCPassportReader
revision. Product policy remains in `.cljk`; Swift only accesses the OS NFC API
and returns bounded SOD/DG1/DG2 bytes in memory with the pending challenge.
It is not an installed app. The consuming iOS app needs its NFC entitlement,
NFC purpose text, ISO7816 application identifier `A0000002471001`, authenticated
challenge retrieval, holder-key storage, explicit capture consent and an encrypted
submission channel. MRZ-key construction remains local to that consuming app.
The server always re-verifies the returned bytes. Audit upstream logging settings
before handling live documents. Client-side authentication flags are not trusted.
Physical NFC, secure messaging and a real passport have not been tested here.
Android remains a separate capture host; common policy/verification is reusable.

## Tests and compatibility

`shadow-cljs release identity-test identity` builds the isolated host suite and
passive-authentication ESM export. The repository's `.cljk` namespace resolution
currently requires an external byte-identical `.cljs` compatibility mapping;
this is not a native Kotoba/Q9 qualification. No production keys or document data
are used in fixtures. Tests generate a synthetic CSCA, DSC, CRL and signed SOD,
then exercise real cryptographic verification and rejection paths. Signature,
wrong-key, tampering, expired challenge, revocation, replay, incomplete review,
quota exhaustion and unconfirmed commit paths are covered.

## Sources

- ICAO Doc 9303 Part 10: https://www.icao.int/sites/default/files/publications/DocSeries/9303_p10_cons_en.pdf
- ICAO Doc 9303 Part 11: https://www.icao.int/sites/default/files/publications/DocSeries/9303_p11_cons_en.pdf
- Trust distribution and receiving-party responsibility: https://www.icao.int/icao-pkd/icao-master-list
- PKI.js CMS verification: https://pkijs.org/docs/api/classes/SignedData/
- iOS capture host: https://github.com/AndyQ/NFCPassportReader/tree/6e37f1ab249fef82771da46d32707f2b94ed090f

### Observed build results, 2026-09-12

- Common host suite after weighted-route update: 11 tests / 93 assertions, zero failures; release builds
  completed with zero compiler warnings via the explicit compatibility mapping.
- iOS arm64 bridge: `swift build --sdk <iPhoneOS26.5.sdk> --triple
  arm64-apple-ios15.0` succeeded. No signing, installation or physical read occurred.
  Xcode destination discovery initially refused the platform; explicitly selecting
  the installed SDK through SwiftPM worked. The pinned reader package reports an
  unhandled `PrivacyInfo.xcprivacy` resource; consuming-app packaging must address
  this before distribution. Do not treat this library build as App Store readiness.
