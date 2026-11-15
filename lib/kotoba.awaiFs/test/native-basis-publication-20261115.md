# Native physical publication digest binding, 2026-11-15

The Native path implements the existing `kotobase.physical-publication/v1`
canonical domain for a restricted profile: a SHA-256-hex logical commit root,
CIDv1 dag-cbor/SHA-256 physical root, engine profile `:prolly`, engine format 3,
and SHA-256 as this caller-selected digest algorithm. It checks the independently
trusted publication digest, verifies the signed logical proof, requires the
referenced manifest's engine format to be 3, and verifies its snapshot checkpoint
and logical database/epoch. A digest or engine-format mismatch is refused.

Babashka 1.12.218 was run once as a local reference, not a Native dependency.
The `.cljk` source was copied as `.cljc` into the task output and loaded from
`kotoba.kotobaseEngineContract`. Source revision `da9a83665244066428a6b799270ca991e231ef6a`:
`identity.cljk` SHA-256 `fef4483244f5cabe0c9da23021622792772fa97d58e097cf67b2b8145bb6a349`,
`canonical.cljk` SHA-256 `e11bc9420ab76f9b09a1a21a523763a7dadfcd6074060eb0d080ab4c21696af5`.
The no-newline reference canonical bytes hash to
`68a40080587e7cf2becf4d51f9374207cf4b0c33c273abe257631c665c109774`;
the Native verifier accepted that digest for the stored fixture. The complete
107-case local macOS arm64 Native corpus passed, including changed digest and
wrong manifest format negative controls. Positive executable SHA-256
`3072fc54210a15d14b2aa3a264428760607bc342d3af963920c0082a2d854789`;
source lock `28b23c0483c940128bc523071f6f2ca979af573c6dfd9dcfdf990d7117e24324`.

The publication contract specifies canonical data, not a mandated hash or
signature. The digest and issuer key must be authenticated independently by
the caller; this fixture uses a test key and plaintext and does not establish
production authority, rollback resistance, policy/receipt or durable storage.
