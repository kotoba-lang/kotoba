# Browser intake, review and encrypted vault

This release implements the intake state machine, WebCrypto vault, holder/reviewer
signature coordinator and private HTTP service factory. These are tested components;
they do not provision production Kotobase/KMS ports or open customer intake.

## Components

- `identity-intake`: one active case per Principal, five case starts per rolling
  day, 15-minute capture window and maximum seven-day case access. Distinct immutable
  document/video slots, pending-review, assigned review, approval/rejection and
  deleting/deleted states. Assigned active reviewers only; self-review is denied.
- `identity-vault`: AES-256-GCM through per-case nonextractable keys from an explicit
  key service. Random 96-bit IV; authenticated additional data binds version, case,
  Principal, slot and capture nonce. Only ciphertext is passed to the block port.
  CIDv1 raw/SHA-256 addresses are computed and verified on write readback and read.
  Plaintext digest is checked after decryption. Audit commit precedes evidence reads.
- `identity-intake-host`: Ed25519 proof of possession binds the initial holder key
  to the authenticated Principal. Submission proof binds case nonce and both
  plaintext digests. Operator JWS binds case revision; current registered key and
  reviewer status are rechecked at CAS. A recording is unverified evidence.
- `identity-intake-service/handler`: bounded Request/Response adapter for the
  private `IDENTITY_AUTHORITY` service binding. No public Worker routes or workers.dev
  endpoint may expose it. Request header Principal is supplied exclusively by the
  authenticated Kotoba Cloud edge; a JSON Principal is never authoritative.

Approval requires a separately supervised live session reference, signed document,
holder/adult/liveness checks, current sanctions/PEP/adverse-media review and approved
research scope. A successful transition creates the existing identity policy record
in the same canonical CAS. Credential issuance is a later host effect; the intake
coordinator currently returns the commit receipt, not an issued credential.

## Required ports — not fabricated production endpoints

The host supplies persistent-data `:read!`, authoritative `:cas!`, private
`:put-block!`/`:get-block!` and KMS `:create-key!`/`:key!`/`:destroy-key!`. The ports
must identify `https://kotobase.net`, private visibility and authoritative CAS.
These are trusted deployment configuration, not client assertions and not proof
that a provider is secure. Both source-level validation and independent production
access-control, contention, restart and recovery tests are required.

`:read!` returns `{:revision n :state persistent-map}`. `:cas!` takes the expected
revision and complete next state, and returns conflict or a durable committed
receipt with revision n+1. It must encrypt sensitive case metadata in the private
canonical graph; do not serialize this map into public datoms. Records contain
holder public keys, purpose/scope and encrypted block/key references, never DEKs.

Block write receipt: `{:status :stored :cid cid :receipt-ref ref}`. Key creation
returns an opaque, case-bound reference; resolution returns only the matching
nonextractable AES-GCM key. Enforce key capabilities server-side. The key service
must make deletion irrevocable across replicas, backups and old state revisions.
`:destroy-key!` returns `{:status :destroyed :receipt-ref ref}` only after confirmed
cryptographic erasure. Ciphertext may still exist; this is not a physical-erasure
claim. Deleting status denies access immediately and remains retryable if key
removal fails. A prior in-flight authorized read may have already reached a client.

Use encrypted blocks under Kotobase's authenticated CID boundary and private datom
metadata. No public IPLD, R2/DO fallback, queryable plaintext metadata or application
logs. The existing default/legacy storage surface is not qualified by these tests.
The observed engine sources explicitly require missing private-mode service ports;
the head store includes a fallback unsuitable for this authoritative CAS contract.
No live global Kotobase configuration was changed by this release.

## Operational activation work

- Bind a qualified private Kotobase graph and KMS service; isolate review keys and
  applicant evidence access; register actual reviewer Principals/public keys.
- Publish and approve operator/retention/contact notice. Both `:intake-enabled?`
  and `:notice-approved?` must be true to start cases. Seven days is currently an
  access limit, **not a running automatic deletion job or legally selected policy**.
- Schedule expiry/reconciliation/deletion, including orphan keys/ciphertext. Never
  destroy a new key after an ambiguous CAS result until canonical readback proves
  it is unreferenced. Apply request/rate/concurrency limits before allocating keys;
  the reducer's five-case limit does not itself prevent concurrent orphan keys.
- Provide fresh authentication, browser key recovery/resume and reviewer signing-key
  enrollment. The browser key is currently memory-only: closing the page loses it.
  Upload retries/lost receipts need canonical reconciliation before a retry UI.
- Connect supervised live review and screening feeds. No automated document
  authenticity/face matching or real-time liveness guarantee is made for browser
  capture; the MIME allowlist is a transport bound, not document validation.
- Persist/dispatch credential effects and connect session observers before enabling
  verified free inference. Existing identity and scope gates remain independent.

## Verification

19 tests / 178 assertions pass in the eKYC suite, including real Ed25519 holder and
reviewer signatures, reviewer replay rejection, private HTTP Principal isolation,
AEAD context mismatch, private CID readback, unauthorized reads, deletion, rejected
incomplete approval and atomic identity approval transitions. Storage/KMS ports are
explicit in-memory test fixtures; **no physical passport or production PII was used**.
The byte-identical CLJS compatibility build is not native/Q9 qualification.
