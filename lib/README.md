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
| `org.ietf.diameter` | `org.ietf.diameter/src` | `diameter.avp`, `diameter.avps`, `diameter.bytes`, `diameter.message` (an external specification, publisher ietf.org) |
| `org.ietf.coap` | `org.ietf.coap/src` | `coap.block`, `coap.code`, `coap.message`, `coap.options` (an external specification, publisher ietf.org) |
| `org.ietf.xdr` | `org.ietf.xdr/src` | `xdr.core` (an external specification, publisher ietf.org) |
| `org.ietf.websocket` | `org.ietf.websocket/src` | `websocket.bytes`, `websocket.frame`, `websocket.handshake` (an external specification, publisher ietf.org) |
| `org.ietf.asn1` | `org.ietf.asn1/src` | `asn1.core`, `asn1.oid` (an external specification, publisher ietf.org) |
| `org.ietf.rtsp` | `org.ietf.rtsp/src` | `rtsp.bytes`, `rtsp.interleaved`, `rtsp.message`, `rtsp.session-header` (an external specification, publisher ietf.org) |
| `org.ietf.ospf` | `org.ietf.ospf/src` | `ospf.bytes`, `ospf.checksum`, `ospf.dd`, `ospf.header` (an external specification, publisher ietf.org) |
| `org.ietf.csv` | `org.ietf.csv/src` | `csv.core` (an external specification, publisher ietf.org) |
| `org.ieee.systemverilog` | `org.ieee.systemverilog/src` | `systemverilog.assertion`, `systemverilog.class`, `systemverilog.datatype`, `systemverilog.interface` (an external specification, publisher ieee.org) |
| `org.ieee.tar` | `org.ieee.tar/src` | `tar.bytes`, `tar.core` (an external specification, publisher ieee.org) |
| `org.ieee.upf` | `org.ieee.upf/src` | `upf.domain`, `upf.parser`, `upf.power-state`, `upf.strategy` (an external specification, publisher ieee.org) |
| `org.ieee.vhdl` | `org.ieee.vhdl/src` | `vhdl.architecture`, `vhdl.entity`, `vhdl.parser`, `vhdl.signal` (an external specification, publisher ieee.org) |
| `org.iso.aac` | `org.iso.aac/src` | `aac.adts`, `aac.bits`, `aac.decode`, `aac.dequant` (an external specification, publisher iso.org) |
| `org.iso.jpeg` | `org.iso.jpeg/src` | `jpeg.bytes`, `jpeg.core`, `jpeg.decode` (an external specification, publisher iso.org) |
| `org.iso.opentype` | `org.iso.opentype/src` | `opentype.bytes`, `opentype.cmap`, `opentype.core` (an external specification, publisher iso.org) |
| `org.iso.pdf` | `org.iso.pdf/src` | `pdf.core` (an external specification, publisher iso.org) |
| `org.omg.bpmn` | `org.omg.bpmn/src` | `bpmn.execute`, `bpmn.model`, `bpmn.ports`, `bpmn.validate` (an external specification, publisher omg.org) |
| `org.omg.cmmn` | `org.omg.cmmn/src` | `cmmn.execute`, `cmmn.model`, `cmmn.ports`, `cmmn.validate` (an external specification, publisher omg.org) |
| `org.omg.dmn` | `org.omg.dmn/src` | `dmn.execute`, `dmn.model`, `dmn.ports`, `dmn.validate` (an external specification, publisher omg.org) |
| `org.w3.aria` | `org.w3.aria/src` | `aria.core` (an external specification, publisher w3.org) |
| `org.w3.did` | `org.w3.did/src` | `did.core` (an external specification, publisher w3.org) |
| `org.w3.nquads` | `org.w3.nquads/src` | `nquads.core` (an external specification, publisher w3.org) |
| `org.w3.jsonLdApi` | `org.w3.jsonLdApi/src` | `json-ld-api.core`, `json-ld-api.to-rdf` (an external specification, publisher w3.org) |
| `org.w3.svg` | `org.w3.svg/src` | `svg.core`, `svg.css`, `svg.reader`, `svg.shapes` (an external specification, publisher w3.org) |
| `org.w3.webaudio` | `org.w3.webaudio/src` | `w3.webaudio`, `w3.webaudio.protocol` (an external specification, publisher w3.org) |
| `org.w3.webrtcSignaling` | `org.w3.webrtcSignaling/src` | `kotoba.rt.core` (an external specification, publisher w3.org) |
| `org.w3.woff` | `org.w3.woff/src` | `woff.bytes`, `woff.core`, `woff.glyf`, `woff.woff2` (an external specification, publisher w3.org) |
| `org.ietf.ssh` | `org.ietf.ssh/src` | `ssh.connection`, `ssh.kex`, `ssh.keys`, `ssh.record` (an external specification, publisher ietf.org) |
| `org.ietf.netconf` | `org.ietf.netconf/src` | `netconf.bytes`, `netconf.framing`, `netconf.message`, `netconf.operations` (an external specification, publisher ietf.org) |
| `org.w3.rdf` | `org.w3.rdf/src` | `rdf.core`, `rdf.dataset`, `rdf.validate` (an external specification, publisher w3.org) |
| `org.w3.rdfCanon` | `org.w3.rdfCanon/src` | `rdf-canon.core` (an external specification, publisher w3.org) |
| `org.w3.vcBitstringStatusList` | `org.w3.vcBitstringStatusList/src` | `status-list.core` (an external specification, publisher w3.org) |
| `org.w3.vcDataIntegrity` | `org.w3.vcDataIntegrity/src` | `data-integrity.bytes`, `data-integrity.core`, `data-integrity.ecdsa`, `data-integrity.eddsa` (an external specification, publisher w3.org) |
| `org.omg.sysmlv2` | `org.omg.sysmlv2/src` | `sysml.conformance`, `sysml.kerml`, `sysml.model`, `sysml.text` (an external specification, publisher omg.org) |
| `org.omg.uml` | `org.omg.uml/src` | `uml.model`, `uml.validate`, `uml.xml` (an external specification, publisher omg.org) |
| `org.apache.parquet` | `org.apache.parquet/src` | `parquet.bytes`, `parquet.decode`, `parquet.footer`, `parquet.snappy` (an external specification, publisher apache.org) |
| `org.apache.avro` | `org.apache.avro/src` | `avro.binary`, `avro.datum`, `avro.file`, `avro.schema` (an external specification, publisher apache.org) |
| `org.apache.iceberg` | `org.apache.iceberg/src` | `iceberg.manifest`, `iceberg.metadata`, `iceberg.rest`, `iceberg.schema` (an external specification, publisher apache.org) |
| `org.w3.owl2` | `org.w3.owl2/src` | `owl.functional`, `owl.model`, `owl.reason`, `owl.rl` (an external specification, publisher w3.org) |
| `kotoba.cron` | `kotoba.cron/src` | `cron.execute`, `cron.model`, `cron.validate` (Kotoba project library) |
| `kotoba.catalogMaturity` | `kotoba.catalogMaturity/src` | `catalog-maturity.core` (Kotoba project library) |
| `kotoba.cartpoleMath` | `kotoba.cartpoleMath/src` | `kami.cartpole-math`, `kotoba.cartpole-math` (Kotoba project library) |
| `kotoba.card` | `kotoba.card/src` | `kotoba.card`, `kotoba.card.actuation`, `kotoba.card.export`, `kotoba.card.lifecycle` (Kotoba project library) |
| `kotoba.canvaskit` | `kotoba.canvaskit/src` | `canvaskit.gesture`, `canvaskit.hit-test`, `canvaskit.scroll-view`, `canvaskit.viewport` (Kotoba project library) |
| `kotoba.cam` | `kotoba.cam/src` | `cam`, `cam.follow`, `cam.look-constraint`, `cam.shake` (Kotoba project library) |
| `kotoba.btcMining` | `kotoba.btcMining/src` | `btc-mining.core` (Kotoba project library) |
| `kotoba.btcCrypto` | `kotoba.btcCrypto/src` | `btc-crypto.base58`, `btc-crypto.bech32`, `btc-crypto.bip32`, `btc-crypto.bip39` (Kotoba project library) |
| `kotoba.crypto` | `kotoba.crypto/src` | `kotoba.crypto`, `kotoba.crypto.-to-bytes`, `kotoba.crypto.aead`, `kotoba.crypto.aead-provider` (Kotoba project library) |
| `kotoba.briefing` | `kotoba.briefing/src` | `briefing.model`, `briefing.validate` (Kotoba project library) |
| `kotoba.bmc` | `kotoba.bmc/src` | `bmc.canvas`, `bmc.gate`, `bmc.io`, `bmc.ledger` (Kotoba project library) |
| `kotoba.blockCache` | `kotoba.blockCache/src` | `block.cache`, `block.cache.worker` (Kotoba project library) |
| `kotoba.blind` | `kotoba.blind/src` | `blind.bytes`, `blind.core` (Kotoba project library) |
| `kotoba.baseL2` | `kotoba.baseL2/src` | `kotoba.lang.base-l2.abi`, `kotoba.lang.base-l2.l2`, `kotoba.lang.base-l2.paymaster`, `kotoba.lang.base-l2.rpc` (Kotoba project library) |
| `kotoba.ethCrypto` | `kotoba.ethCrypto/src` | `eth-crypto.core`, `eth-crypto.js-core`, `eth-crypto.keccak`, `eth-crypto.secp256k1` (Kotoba project library) |
| `kotoba.touchid` | `kotoba.touchid/src` | `touchid.adapters.apple-local-authentication`, `touchid.adapters.edn-local-auth`, `touchid.adapters.local-auth`, `touchid.core` (Kotoba project library) |
| `kotoba.saml` | `kotoba.saml/src` | `saml.adapters.conditions`, `saml.adapters.metadata`, `saml.adapters.xml`, `saml.adapters.xml-parser` (Kotoba project library) |
| `kotoba.onetime` | `kotoba.onetime/src` | `onetime.adapters.authenticator`, `onetime.adapters.delivery`, `onetime.adapters.digest`, `onetime.adapters.totp` (Kotoba project library) |
| `kotoba.identity` | `kotoba.identity/src` | `identity.adapters.datomic-kotoba`, `identity.adapters.did`, `identity.adapters.eas`, `identity.adapters.edn-ledger` (Kotoba project library) |
| `kotoba.faceid` | `kotoba.faceid/src` | `faceid.adapters.apple-local-authentication`, `faceid.adapters.edn-local-auth`, `faceid.adapters.local-auth`, `faceid.core` (Kotoba project library) |
| `kotoba.audio` | `kotoba.audio/src` | `audio`, `audio.binaural`, `audio.effects`, `audio.filter` (Kotoba project library) |
| `kotoba.atom` | `kotoba.atom/src` | `atom.core`, `kotoba.atom` (Kotoba project library) |
| `kotoba.atmosphere` | `kotoba.atmosphere/src` | `atmosphere`, `atmosphere.wind-field` (Kotoba project library) |
| `kotoba.html` | `kotoba.html/src` | `html.core`, `kotoba.html` (Kotoba project library) |
| `kotoba.byoubuUi` | `kotoba.byoubuUi/src` | `byoubu-ui.core`, `byoubu-ui.style`, `byoubu-ui.tokens` (Kotoba project library) |
| `kotoba.css` | `kotoba.css/src` | `css.build`, `css.core`, `css.utility`, `kotoba.css` (Kotoba project library) |
| `kotoba.byoubu` | `kotoba.byoubu/src` | `byoubu.catalog`, `byoubu.color`, `byoubu.core`, `byoubu.facts` (Kotoba project library) |
| `kotoba.apn` | `kotoba.apn/src` | `apn.grid`, `apn.model`, `apn.provision`, `apn.runner` (Kotoba project library) |
| `kotoba.annotation` | `kotoba.annotation/src` | `annotation.core` (Kotoba project library) |
| `kotoba.agent` | `kotoba.agent/src` | `agent.run` (Kotoba project library) |
| `kotoba.adnet` | `kotoba.adnet/src` | `adnet.billing`, `adnet.core`, `adnet.entitlement` (Kotoba project library) |
| `kotoba.activity` | `kotoba.activity/src` | `kotoba.activity` (Kotoba project library) |
| `kotoba.ioIpld` | `kotoba.ioIpld/src` | `ipld.core`, `ipld.dag-json`, `ipld.dag-pb`, `ipld.data-model` (Kotoba project library) |
| `kotoba.devProtobuf` | `kotoba.devProtobuf/src` | `protobuf.wire` (Kotoba project library) |
| `kotoba.sparql` | `kotoba.sparql/src` | `sparql.core` (Kotoba project library) |
| `kotoba.datalog` | `kotoba.datalog/src` | `datalog.core`, `datalog.index`, `datalog.query`, `datalog.singleton` (Kotoba project library) |
| `kotoba.ioMultiformats` | `kotoba.ioMultiformats/src` | `multiformats.base32`, `multiformats.core`, `multiformats.multiaddr` (Kotoba project library) |
| `com.google.snappy` | `com.google.snappy/src` | `snappy.core` (Kotoba project library) |
| `kotoba.columnar` | `kotoba.columnar/src` | `columnar.aggregate`, `columnar.bytes`, `columnar.evolve`, `columnar.group` (Kotoba project library) |
| `kotoba.datomSource` | `kotoba.datomSource/src` | `datom.source`, `datom.source.adjacency`, `datom.source.conformance`, `datom.source.plane` (Kotoba project library) |
| `kotoba.dslCore` | `kotoba.dslCore/src` | `kotoba.dsl.problem` (Kotoba project library) |
| `kotoba.xml` | `kotoba.xml/src` | `kotoba.xml`, `xml.core`, `xml.parse` (Kotoba project library) |

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
