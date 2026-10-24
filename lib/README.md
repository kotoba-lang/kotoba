# Bundled Kotoba libraries

The bundled standard libraries live in this repository:

| Canonical ID | Source | Legacy namespace APIs |
|---|---|---|
| `kotoba.coll` | `kotoba.coll/src` | `kotoba.coll`, `kotoba.lang.coll` |
| `kotoba.spec` | `kotoba.spec/src` | `kotoba.spec`, `kotoba.lang.spec` |
| `kotoba.json` | `kotoba.json/src` | `kotoba.json`, `kotoba.lang.json`, `json.*` |
| `kotoba.set` | `kotoba.set/src` | `kotoba.set` |
| `kotoba.walk` | `kotoba.walk/src` | `kotoba.walk` |
| `kotoba.string` | `kotoba.string/src` | `kotoba.string` |
| `kotoba.time` | `kotoba.time/src` | `kotoba.time`, `kotoba.lang.time` |
| `kotoba.bytes` | `kotoba.bytes/src` | `kotoba.bytes`, `kotoba.bytes.sha1`, `kotoba.bytes.sha256` |
| `kotoba.pprint` | `kotoba.pprint/src` | `kotoba.pprint` |
| `kotoba.error` | `kotoba.error/src` | `kotoba.lang.error` |
| `kotoba.text` | `kotoba.text/src` | `kotoba.text`, `kotoba.lang.text` |
| `kotoba.test` | `kotoba.test/src` | `kotoba.test`, `kotoba.lang.test` |
| `kotoba.edn` | `kotoba.edn/src` | `kotoba.edn`, `kotoba.lang.edn` |
| `kotoba.io` | `kotoba.io/src` | `kotoba.io`, `kotoba.lang.io` |
| `kotoba.process` | `kotoba.process/src` | `kotoba.process`, `kotoba.lang.process` |
| `kotoba.async` | `kotoba.async/src` | `kotoba.async`, `kotoba.lang.async` |
| `kotoba.scheduler` | `kotoba.scheduler/src` | `kotoba.scheduler`, `kotoba.lang.scheduler` |
| `kotoba.store` | `kotoba.store/src` | `kotoba.store`, `kotoba.lang.store` |
| `kotoba.fmt` | `kotoba.fmt/src` | `kotoba.fmt`, `kotoba.lang.fmt` |
| `kotoba.log` | `kotoba.log/src` | `kotoba.log`, `kotoba.lang.log` |
| `kotoba.fs` | `kotoba.fs/src` | `kotoba.fs`, `kotoba.lang.fs` |
| `kotoba.lsp` | `kotoba.lsp/src` | `kotoba.lsp`, `kotoba.lang.lsp` |
| `kotoba.lsp.rpc` | `kotoba.lsp.rpc/src` | `kotoba.lsp-rpc`, `kotoba.lang.lsp-rpc` |
| `kotoba.lint` | `kotoba.lint/src` | `kotoba.lint`, `kotoba.lang.lint` |
| `kotoba.lint.kotoba` | `kotoba.lint.kotoba/src` | `kotoba.lint-kotoba`, `kotoba.lang.lint-kotoba` |
| `gov.nist.sha3` | `gov.nist.sha3/src` | `sha3.core` (FIPS 202 SHA-3 and SHAKE; an external specification, so its ID is the publisher's reverse domain, nist.gov) |
| `gov.nist.sha2` | `gov.nist.sha2/src` | `sha2.core`, `sha2.sha512`, `hash.subpath-dispatch` (FIPS 180-4 SHA-2; an external specification, publisher nist.gov) |
| `gov.nist.mlKem` | `gov.nist.mlKem/src` | `mlkem.core` (FIPS 203 ML-KEM-768: keygen, encaps, decaps; an external specification, publisher nist.gov) |
| `org.ietf.x25519` | `org.ietf.x25519/src` | `x25519.core`, `x25519.field` (RFC 7748 X25519; an external specification, publisher ietf.org) |
| `org.ietf.ed25519` | `org.ietf.ed25519/src` | `ed25519.core`, `ed25519.sign`, `ed25519.edwards`, `ed25519.scalar` (RFC 8032 Ed25519 keys, signing and verification; an external specification, publisher ietf.org) |
| `org.ietf.chacha20Poly1305` | `org.ietf.chacha20Poly1305/src` | `chacha20.core`, `chacha20.poly1305`, `chacha20.aead`, `chacha20.xchacha` (RFC 8439 ChaCha20-Poly1305 and XChaCha20; an external specification, publisher ietf.org) |
| `org.ietf.jcs` | `org.ietf.jcs/src` | `jcs.core` (RFC 8785 JSON Canonicalization Scheme; an external specification, publisher ietf.org) |
| `org.ietf.cbor` | `org.ietf.cbor/src` | `cbor.core` (RFC 8949 CBOR encode and decode, with a typed encoder; an external specification, publisher ietf.org) |
| `org.ietf.deflate` | `org.ietf.deflate/src` | `deflate.bits`, `deflate.checksum`, `deflate.compress`, `deflate.core` (an external specification, publisher ietf.org) |
| `org.ietf.blake2` | `org.ietf.blake2/src` | `blake2.core`, `blake2.word` (an external specification, publisher ietf.org) |
| `org.ietf.zstd` | `org.ietf.zstd/src` | `zstd.bits`, `zstd.core`, `zstd.fse`, `zstd.huff` (an external specification, publisher ietf.org) |
| `org.ietf.mime` | `org.ietf.mime/src` | `mime.address`, `mime.codec`, `mime.header`, `mime.parse` (an external specification, publisher ietf.org) |
| `org.ietf.brotli` | `org.ietf.brotli/src` | `brotli.bits`, `brotli.core`, `brotli.data`, `brotli.dictionary` (an external specification, publisher ietf.org) |
| `org.ietf.ical` | `org.ietf.ical/src` | `ical.builder`, `ical.execute`, `ical.ical`, `ical.model` (an external specification, publisher ietf.org) |
| `org.ietf.sip` | `org.ietf.sip/src` | `sip.grammar`, `sip.headers`, `sip.message`, `sip.uri` (an external specification, publisher ietf.org) |
| `org.ietf.opus` | `org.ietf.opus/src` | `opus.celt`, `opus.mdct`, `opus.packet`, `opus.pvq` (an external specification, publisher ietf.org) |
| `org.ietf.sdp` | `org.ietf.sdp/src` | `sdp.attrs`, `sdp.core`, `sdp.grammar` (an external specification, publisher ietf.org) |
| `org.ietf.rtp` | `org.ietf.rtp/src` | `rtp.header`, `rtp.rtcp`, `rtp.seq` (an external specification, publisher ietf.org) |

`catalog.edn` declares exact aliases for old repository/coordinate names.
`kotoba.*` is a project namespace and requires no DNS ownership. Each package
includes its complete same-family per-definition source closure; those small
repos are no longer needed to load these namespaces from this source checkout.
External support dependencies remain explicitly pinned in each `deps.edn`.

Run from repository root:

```sh
node scripts/check-libraries.mjs
node scripts/test-library-provenance.mjs
node scripts/test-libraries.mjs
node scripts/test-libraries.mjs --check-design

bin/kotoba library import kotoba-lang/json --json
bin/kotoba library import kotoba.coll kotoba.spec kotoba.json --json
```

See [public source imports](../docs/library-source-import.md) to execute a
program with `run --runtime sci --library <ID-or-alias>`. The development
catalog facade delegates resolution to the language-owned portable contract.

The test driver uses the installed `.cljk` SCI engine (`KBB_ENGINE` can select
it), the existing native `bin/kbb_deps.cljk` resolver, the checked-in bundled
text bootstrap, and the dependency graph of `lib/deps.edn`. No implicit sibling
classpath or JVM resolver is used. Missing declared dependencies fail the run.
The driver refuses Java/Clojure/bb subprocesses. The standalone libraries'
older runner files are retained as import provenance; use the driver above to
execute all portable suites, including the definition facades. `test-suites.json` registers every imported suite and its host.
`node scripts/test-library-jvm.mjs` runs the original JVM-only suites, current
bytes module admission, and the async JVM/KIR/JavaScript/Wasm oracle in the
current launcher compiler graph. Required native CI separately self-builds the
compiler and executes the bundled library closures with fuel refusal and source
readback. See [native compatibility](../docs/library-native-compat.md) for the
qualified APIs and explicit host/native distinctions.

`imports.json` preserves source commit/tree, original-to-local file paths,
per-file digests, licenses, and executable modes. Imported definition sources
use `.cljk` here; `cljk-origin.edn` records their original extensions without
changing their code bytes. `local-changes.json` explicitly records build metadata
adjustments and removal of inherited empty lines at EOF. Source comments,
changelogs, and READMEs inside
the imports describe their original standalone repositories. This page and
the [implementation ADR](../docs/ADR-kotoba-library-monorepo-and-lexicon-events.md)
describe the current integration.

The tooling packages import 31 licensed origins. Twelve compatibility modules
are derived from the pinned Apache-2.0 LSP owner, with their original definition
forms, explicit namespace bindings and license digests checked separately in
`kotoba.lsp/derivations.json`. No active source is imported from the twelve
license-less split repositories. Their complete Git histories remain recovery
data. See [tooling consolidation](../docs/library-tooling-consolidation.md).

This is source consolidation, host compatibility coverage and the declared
native library fixture qualification. Signed release publication, full Kotoba
source conversion and event publish/subscribe are separate work. Amu and the other execution
and contract owners stay separate. Existing external pins keep working from
the old repositories until their consumers migrate.

See [repository migration decisions](../docs/library-repository-migration.md) and
[reviewed source retirement inventory](repository-migrations.json). Archive
retains repository history and immutable dependency pins; the inventory records
eligibility, while the linked Linear task records actual GitHub readback.

`lib/kbb/` remains the existing guest script library.
