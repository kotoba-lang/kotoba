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
| `org.ietf.turn` | `org.ietf.turn/src` | `kotoba.turn.allocation`, `kotoba.turn.channeldata`, `kotoba.turn.credential`, `kotoba.turn.demux` (an external specification, publisher ietf.org) |
| `org.w3.webgpu` | `org.w3.webgpu/src` | `w3.webgpu` (an external specification, publisher w3.org) |
| `org.ietf.x509` | `org.ietf.x509/src` | `x509.core` (an external specification, publisher ietf.org) |
| `org.ietf.cms` | `org.ietf.cms/src` | `cms.core`, `cms.jvm` (an external specification, publisher ietf.org) |
| `org.ietf.rfc3161` | `org.ietf.rfc3161/src` | `rfc3161.core` (an external specification, publisher ietf.org) |
| `org.ietf.argon2` | `org.ietf.argon2/src` | `argon2.compress`, `argon2.core`, `argon2.u32` (an external specification, publisher ietf.org) |
| `org.ietf.ers` | `org.ietf.ers/src` | `ers.core` (an external specification, publisher ietf.org) |
| `org.ietf.jws` | `org.ietf.jws/src` | `jws.core` (an external specification, publisher ietf.org) |
| `org.ietf.oncrpc` | `org.ietf.oncrpc/src` | `oncrpc.core`, `oncrpc.record` (an external specification, publisher ietf.org) |
| `org.ietf.nfs` | `org.ietf.nfs/src` | `nfs.memory`, `nfs.mount`, `nfs.tcp`, `nfs.v3` (an external specification, publisher ietf.org) |
| `org.ietf.sdJwt` | `org.ietf.sdJwt/src` | `sd-jwt.core` (an external specification, publisher ietf.org) |
| `org.ietf.sdJwtVc` | `org.ietf.sdJwtVc/src` | `sd-jwt-vc.core` (an external specification, publisher ietf.org) |
| `org.w3.webauthn` | `org.w3.webauthn/src` | `webauthn.core` (an external specification, publisher w3.org) |
| `org.w3.png` | `org.w3.png/src` | `png.bytes`, `png.core`, `png.decode`, `png.encode` (an external specification, publisher w3.org) |
| `org.ietf.dnssec` | `org.ietf.dnssec/src` | `dnssec.canonical`, `dnssec.nsec3`, `dnssec.provider`, `dnssec.sign` (an external specification, publisher ietf.org) |
| `org.ietf.radius` | `org.ietf.radius/src` | `radius.attribute`, `radius.auth`, `radius.bytes`, `radius.md5` (an external specification, publisher ietf.org) |
| `org.ietf.snmp` | `org.ietf.snmp/src` | `snmp.message`, `snmp.pdu`, `snmp.types` (an external specification, publisher ietf.org) |
| `org.apache.arrow` | `org.apache.arrow/src` | `arrow.build`, `arrow.decode`, `arrow.flatbuffers`, `arrow.ipc` (an external specification, publisher apache.org) |
| `org.ietf.oauth2` | `org.ietf.oauth2/src` | `oauth2.core`, `oauth2.pkce` (an external specification, publisher ietf.org) |
| `org.ietf.epp` | `org.ietf.epp/src` | `epp.command`, `epp.response`, `epp.server`, `epp.transport` (an external specification, publisher ietf.org) |
| `org.ietf.imap` | `org.ietf.imap/src` | `imap.client`, `imap.protocol`, `imap.transport` (an external specification, publisher ietf.org) |
| `org.ietf.pop3` | `org.ietf.pop3/src` | `pop3.client`, `pop3.protocol`, `pop3.transport` (an external specification, publisher ietf.org) |
| `org.ietf.rdap` | `org.ietf.rdap/src` | `rdap.jcard`, `rdap.response`, `rdap.service`, `rdap.status` (an external specification, publisher ietf.org) |
| `org.ietf.sftp` | `org.ietf.sftp/src` | `kotobase.sftp.fs`, `kotobase.sftp.transport.sftp-subsystem`, `kotobase.sftp.transport.ssh`, `kotobase.sftp.transport.wire` (an external specification, publisher ietf.org) |
| `org.ietf.smtp` | `org.ietf.smtp/src` | `smtp.client`, `smtp.protocol`, `smtp.transport` (an external specification, publisher ietf.org) |
| `org.ietf.webdav` | `org.ietf.webdav/src` | `kotobase.protocols.http`, `kotobase.protocols.webdav` (an external specification, publisher ietf.org) |
| `kotoba.kekkaiCli` | `kotoba.kekkaiCli/src` | `kekkai.cli.commands`, `kekkai.cli.config`, `kekkai.cli.desired`, `kekkai.cli.main` (Kotoba project library) |
| `kotoba.sdkPy` | `kotoba.sdkPy/src` | `etzhayyim-sdk.config`, `etzhayyim-sdk.errors`, `etzhayyim-sdk.llm`, `etzhayyim-sdk.metrics` (Kotoba project library) |
| `kotoba.kotobaDelta` | `kotoba.kotobaDelta/src` | `delta.anchor`, `delta.op`, `delta.store` (Kotoba project library) |
| `kotoba.svgraph` | `kotoba.svgraph/src` | `` (Kotoba project library) |
| `kotoba.lab` | `kotoba.lab/src` | `kotoba.lab.verification`, `kotoba.lab.verification-check` (Kotoba project library) |
| `kotoba.karakuri` | `kotoba.karakuri/src` | `karakuri.cells.adapter-invoke.state-machine`, `karakuri.cells.command-plan.state-machine`, `karakuri.cells.export-roundtrip.cell`, `karakuri.cells.export-roundtrip.state-machine` (Kotoba project library) |
| `kotoba.noren` | `kotoba.noren/src` | `noren.build`, `noren.diagnose`, `noren.discovery`, `noren.governor` (Kotoba project library) |
| `kotoba.loopOsStackObserve` | `kotoba.loopOsStackObserve/src` | `loop-os-stack-observe.core` (Kotoba project library) |
| `kotoba.shinkansen` | `kotoba.shinkansen/src` | `shinkansen.actions`, `shinkansen.adapter`, `shinkansen.audit`, `shinkansen.bridge` (Kotoba project library) |
| `kotoba.reader` | `kotoba.reader/src` | `kotoba.reader` (Kotoba project library) |
| `kotoba.prng` | `kotoba.prng/src` | `kotoba.prng` (Kotoba project library) |
| `kotoba.moyaiLedger` | `kotoba.moyaiLedger/src` | `moyai.ledger` (Kotoba project library) |
| `kotoba.math` | `kotoba.math/src` | `kotoba.math` (Kotoba project library) |
| `kotoba.kotobaseShardIndex` | `kotoba.kotobaseShardIndex/src` | `kotobase-shard-index.analyze`, `kotobase-shard-index.append`, `kotobase-shard-index.block`, `kotobase-shard-index.build` (Kotoba project library) |
| `kotoba.kotobaNet` | `kotoba.kotobaNet/src` | `kotoba.net.jvm-host` (Kotoba project library) |
| `kotoba.i64` | `kotoba.i64/src` | `kotoba.i64` (Kotoba project library) |
| `kotoba.hanmen` | `kotoba.hanmen/src` | `hanmen.page`, `hanmen.pdf`, `hanmen.svg` (Kotoba project library) |
| `kotoba.htmldom` | `kotoba.htmldom/src` | `htmldom.core` (Kotoba project library) |
| `kotoba.cssom` | `kotoba.cssom/src` | `cssom.core`, `cssom.layout` (Kotoba project library) |
| `kotoba.domGpu` | `kotoba.domGpu/src` | `kotoba.wasm.abi`, `kotoba.wasm.debug`, `kotoba.wasm.demo`, `kotoba.wasm.demo-document` (Kotoba project library) |
| `kotoba.codeGraph` | `kotoba.codeGraph/src` | `code-graph.async`, `code-graph.core`, `code-graph.evidence` (Kotoba project library) |
| `kotoba.yield` | `kotoba.yield/src` | `yield`, `yield.aging`, `yield.corner`, `yield.monte-carlo` (Kotoba project library) |
| `kotoba.watchlistScreen` | `kotoba.watchlistScreen/src` | `watchlist.adapters.aml-port`, `watchlist.adapters.edn-index`, `watchlist.adapters.eu-consolidated`, `watchlist.adapters.jp-mof` (Kotoba project library) |
| `kotoba.unspsc` | `kotoba.unspsc/src` | `kotoba.unspsc`, `kotoba.unspsc.embedded`, `kotoba.unspsc.product` (Kotoba project library) |
| `kotoba.uikit` | `kotoba.uikit/src` | `uikit.core` (Kotoba project library) |
| `kotoba.torch` | `kotoba.torch/src` | `torch.checkpoint`, `torch.continuous`, `torch.continuous-ollama`, `torch.core` (Kotoba project library) |
| `kotoba.tana` | `kotoba.tana/src` | `tana.aggregate`, `tana.member`, `tana.plan`, `tana.shard` (Kotoba project library) |
| `kotoba.saifu` | `kotoba.saifu/src` | `saifu.address`, `saifu.policy`, `saifu.sign`, `saifu.tx` (Kotoba project library) |
| `kotoba.wallet` | `kotoba.wallet/src` | `wallet.chain`, `wallet.chains`, `wallet.keystore`, `wallet.signer` (Kotoba project library) |
| `kotoba.route` | `kotoba.route/src` | `route.browser`, `route.core`, `route.reagent` (Kotoba project library) |
| `kotoba.release` | `kotoba.release/src` | `kotoba.release.admission`, `kotoba.release.cli`, `kotoba.release.tag` (Kotoba project library) |
| `kotoba.providerTransport` | `kotoba.providerTransport/src` | `provider.tls-channel`, `provider.transport` (Kotoba project library) |
| `kotoba.provider` | `kotoba.provider/src` | `provider.clock`, `provider.clock-transport`, `provider.conformance`, `provider.dataspace` (Kotoba project library) |
| `kotoba.pricingOracle` | `kotoba.pricingOracle/src` | `pricing-oracle.core` (Kotoba project library) |
| `kotoba.plm` | `kotoba.plm/src` | `kotoba.plm.app`, `kotoba.plm.core`, `kotoba.plm.cost`, `kotoba.plm.db` (Kotoba project library) |
| `kotoba.paging` | `kotoba.paging/src` | `paging.core` (Kotoba project library) |
| `kotoba.packageRegistryIpfs` | `kotoba.packageRegistryIpfs/src` | `kotoba.package-registry.ipfs` (Kotoba project library) |
| `kotoba.p2p` | `kotoba.p2p/src` | `kotoba.p2p.graphsync`, `kotoba.p2p.graphsync-checkpoint-store`, `kotoba.p2p.graphsync-extension`, `kotoba.p2p.graphsync-prolly` (Kotoba project library) |
| `kotoba.nostr` | `kotoba.nostr/src` | `nostr.blossom`, `nostr.crypto`, `nostr.event`, `nostr.http` (Kotoba project library) |
| `kotoba.mokurokuUi` | `kotoba.mokurokuUi/src` | `mokuroku-ui.core` (Kotoba project library) |
| `kotoba.traversal` | `kotoba.traversal/src` | `traversal.core` (Kotoba project library) |
| `kotoba.perfgate` | `kotoba.perfgate/src` | `perfgate.core` (Kotoba project library) |
| `kotoba.loopGameAutoplay` | `kotoba.loopGameAutoplay/src` | `loop-game-autoplay.env`, `loop-game-autoplay.policy`, `loop-game-autoplay.qualify`, `loop-game-autoplay.server` (Kotoba project library) |
| `kotoba.layout` | `kotoba.layout/src` | `layout.core` (Kotoba project library) |
| `kotoba.kuraNode` | `kotoba.kuraNode/src` | `kura.node.accounting`, `kura.node.async`, `kura.node.audit`, `kura.node.contract` (Kotoba project library) |
| `kotoba.kuraBugyo` | `kotoba.kuraBugyo/src` | `kura.bugyo.budget`, `kura.bugyo.collateral`, `kura.bugyo.epoch`, `kura.bugyo.plane` (Kotoba project library) |
| `kotoba.kura` | `kotoba.kura/src` | `kura.audit`, `kura.hash`, `kura.kotoba-oracle`, `kura.manifest` (Kotoba project library) |
| `kotoba.kotobaseProtocolCore` | `kotoba.kotobaseProtocolCore/src` | `kotobase.protocols.blocks`, `kotobase.protocols.cid`, `kotobase.protocols.hash`, `kotobase.protocols.http` (Kotoba project library) |
| `kotoba.kotobaseBrowserWorker` | `kotoba.kotobaseBrowserWorker/src` | `kotobase.browser-worker.browser`, `kotobase.browser-worker.idb` (Kotoba project library) |
| `kotoba.kotobaSelfhostContracts` | `kotoba.kotobaSelfhostContracts/src` | `kotoba.selfhost.analyzer`, `kotoba.selfhost.contracts`, `kotoba.selfhost.oracle` (Kotoba project library) |
| `kotoba.kotobaComponent` | `kotoba.kotobaComponent/src` | `kotoba.component.admission`, `kotoba.component.artifact`, `kotoba.component.composition`, `kotoba.component.core` (Kotoba project library) |
| `kotoba.kotobaWasm` | `kotoba.kotobaWasm/src` | `kotoba.wasm.canonical-abi`, `kotoba.wasm.core`, `kotoba.wasm.tools`, `kotoba.wasm.typed` (Kotoba project library) |
| `kotoba.kotobaAnnex` | `kotoba.kotobaAnnex/src` | `kotoba.annex.archive`, `kotoba.annex.cid`, `kotoba.annex.directory`, `kotoba.annex.grant` (Kotoba project library) |
| `kotoba.kamiSensorSim` | `kotoba.kamiSensorSim/src` | `sensor-sim`, `sensor-sim.camera`, `sensor-sim.contact`, `sensor-sim.imu` (Kotoba project library) |
| `kotoba.kamiSceneContracts` | `kotoba.kamiSceneContracts/src` | `kami.scene.authority-manifest`, `kami.scene.contracts`, `kami.scene.fixture-sync`, `kami.scene.mirror-check` (Kotoba project library) |
| `kotoba.kamiOngakuProject` | `kotoba.kamiOngakuProject/src` | `kami.ongaku.project` (Kotoba project library) |
| `kotoba.kamiMangakaExpression` | `kotoba.kamiMangakaExpression/src` | `kami.mangaka.expression` (Kotoba project library) |
| `kotoba.kamiEngineSdk` | `kotoba.kamiEngineSdk/src` | `kami.avatar`, `kami.backend.browser`, `kami.backend.host`, `kami.benchmark` (Kotoba project library) |
| `kotoba.kamiEngineCfd` | `kotoba.kamiEngineCfd/src` | `kami-cfd`, `kami-cfd.d3`, `kami-cfd.duct`, `kami-cfd.mesh` (Kotoba project library) |
| `kotoba.kamiContracts` | `kotoba.kamiContracts/src` | `kami.app-fixtures`, `kami.app-state-machines`, `kami.component`, `kami.contracts.gpu` (Kotoba project library) |
| `kotoba.kamiCadImport` | `kotoba.kamiCadImport/src` | `cad-import`, `cad-import.demos`, `cad-import.demos.roadster`, `cad-import.demos.synth-sedan` (Kotoba project library) |
| `kotoba.kamiAutodrive` | `kotoba.kamiAutodrive/src` | `autodrive`, `autodrive.autopilot`, `autodrive.classes`, `autodrive.control` (Kotoba project library) |
| `kotoba.kamiAppShibuya` | `kotoba.kamiAppShibuya/src` | `kotoba.shibuya` (Kotoba project library) |
| `kotoba.kamiAppIsekai` | `kotoba.kamiAppIsekai/src` | `kami-app-isekai`, `kami-app-isekai.heightmap-color`, `kami-app-isekai.omniverse`, `kami-app-isekai.pipelines` (Kotoba project library) |
| `kotoba.kamiAppFixtures` | `kotoba.kamiAppFixtures/src` | `kami.app-fixtures`, `kami.provider.contract` (Kotoba project library) |
| `kotoba.kagitaba` | `kotoba.kagitaba/src` | `kagitaba.capability`, `kagitaba.category`, `kagitaba.contract`, `kagitaba.field` (Kotoba project library) |
| `kotoba.kagami` | `kotoba.kagami/src` | `kagami.ci`, `kagami.db`, `kagami.did`, `kagami.governor-bridge` (Kotoba project library) |
| `kotoba.jpGoDigitalDesignSystem` | `kotoba.jpGoDigitalDesignSystem/src` | `jp-go-dds.behavior`, `jp-go-dds.core`, `jp-go-dds.css`, `jp-go-dds.dark` (Kotoba project library) |
| `kotoba.iso3166` | `kotoba.iso3166/src` | `kotoba.iso3166`, `kotoba.iso3166.embedded` (Kotoba project library) |
| `kotoba.ioplan` | `kotoba.ioplan/src` | `ioplan.core` (Kotoba project library) |
| `kotoba.ioFilecoinSigner` | `kotoba.ioFilecoinSigner/src` | `filecoin.signer`, `filecoin.signer.bls`, `filecoin.signer.eth` (Kotoba project library) |
| `kotoba.ioFilecoinNode` | `kotoba.ioFilecoinNode/src` | `filecoin.node.actors`, `filecoin.node.basefee`, `filecoin.node.block`, `filecoin.node.mpool` (Kotoba project library) |
| `kotoba.industry` | `kotoba.industry/src` | `kotoba.industry`, `kotoba.industry.embedded`, `kotoba.industry.wave` (Kotoba project library) |
| `kotoba.ieFlow` | `kotoba.ieFlow/src` | `etzhayyim.ie-flow.boundary`, `etzhayyim.ie-flow.colony`, `etzhayyim.ie-flow.control`, `etzhayyim.ie-flow.coscientist` (Kotoba project library) |
| `kotoba.i18nCid` | `kotoba.i18nCid/src` | `i18n-cid.core`, `i18n-cid.pack`, `i18n-cid.pin`, `i18n-cid.seam` (Kotoba project library) |
| `kotoba.i18n` | `kotoba.i18n/src` | `i18n.core`, `i18n.messages`, `i18n.plural`, `i18n.re-frame` (Kotoba project library) |
| `kotoba.hls` | `kotoba.hls/src` | `kotoba.hls`, `kotoba.hls.player`, `kotoba.hls.view` (Kotoba project library) |
| `kotoba.erasure` | `kotoba.erasure/src` | `erasure.codec`, `erasure.gf`, `erasure.kotoba-oracle`, `erasure.lrc` (Kotoba project library) |
| `kotoba.ekycNativeProvider` | `kotoba.ekycNativeProvider/src` | `ekyc-native-provider.core`, `ekyc-native-provider.ports` (Kotoba project library) |
| `kotoba.mrz` | `kotoba.mrz/src` | `mrz.adapters.template-ocr`, `mrz.checksum`, `mrz.core`, `mrz.glyph` (Kotoba project library) |
| `kotoba.dtn` | `kotoba.dtn/src` | `kotoba.dtn`, `kotoba.dtn.auth`, `kotoba.dtn.discovery`, `kotoba.dtn.discovery.presence` (Kotoba project library) |
| `kotoba.ioLibp2p` | `kotoba.ioLibp2p/src` | `goog.crypt.Sha256`, `kotoba.net.bitswap`, `kotoba.net.gossip`, `kotoba.net.ipns-router` (Kotoba project library) |
| `kotoba.noise` | `kotoba.noise/src` | `noise.blake2s`, `noise.cipher-state`, `noise.core`, `noise.handshake-state` (Kotoba project library) |
| `kotoba.domainBilling` | `kotoba.domainBilling/src` | `domain-billing.core` (Kotoba project library) |
| `kotoba.docs` | `kotoba.docs/src` | `docs.docx`, `docs.html`, `docs.markdown`, `docs.model` (Kotoba project library) |
| `kotoba.custody` | `kotoba.custody/src` | `custody.model`, `custody.seal`, `custody.shamir` (Kotoba project library) |
| `kotoba.crowdfunding` | `kotoba.crowdfunding/src` | `crowdfunding.campaign`, `crowdfunding.collection`, `crowdfunding.discovery`, `crowdfunding.fee` (Kotoba project library) |
| `kotoba.chobo` | `kotoba.chobo/src` | `chobo.events`, `chobo.invoice`, `chobo.ledger`, `chobo.ssr` (Kotoba project library) |
| `kotoba.appkit` | `kotoba.appkit/src` | `appkit.core` (Kotoba project library) |
| `kotoba.kotobaUi` | `kotoba.kotobaUi/src` | `kotoba-ui.core`, `kotoba-ui.product`, `kotoba-ui.shell`, `kotoba-ui.shell.style` (Kotoba project library) |
| `kotoba.liquidGlassUi` | `kotoba.liquidGlassUi/src` | `liquid-glass.components`, `liquid-glass.demo`, `liquid-glass.style`, `liquid-glass.tokens` (Kotoba project library) |
| `kotoba.marketplace` | `kotoba.marketplace/src` | `marketplace.acceptance`, `marketplace.buyer`, `marketplace.catalog`, `marketplace.crossborder` (Kotoba project library) |
| `kotoba.kamiNvCompat` | `kotoba.kamiNvCompat/src` | `kotoba.lang.kami-nv-compat.actions.action-term`, `kotoba.lang.kami-nv-compat.actions.articulated-env`, `kotoba.lang.kami-nv-compat.actions.task-space-actions`, `kotoba.lang.kami-nv-compat.alpamayo` (Kotoba project library) |
| `kotoba.ioAlembic` | `kotoba.ioAlembic/src` | `alembic.objects`, `alembic.properties`, `ogawa.core` (Kotoba project library) |
| `kotoba.arxiv` | `kotoba.arxiv/src` | `arxiv-kotoba.dialogue`, `arxiv-kotoba.manifest`, `arxiv-kotoba.ops`, `arxiv-kotoba.policy` (Kotoba project library) |
| `kotoba.comWise` | `kotoba.comWise/src` | `wise.balances`, `wise.client`, `wise.profiles`, `wise.quotes` (Kotoba project library) |
| `kotoba.comNvidiaIsaacLab` | `kotoba.comNvidiaIsaacLab/src` | `shugyo`, `shugyo.cartpole`, `shugyo.dr`, `shugyo.ee-reach` (Kotoba project library) |
| `kotoba.comGmail` | `kotoba.comGmail/src` | `gmail.async-client`, `gmail.async-history`, `gmail.async-threads`, `gmail.attachments` (Kotoba project library) |
| `kotoba.kotobaseClient` | `kotoba.kotobaseClient/src` | `kotobase.attenuate`, `kotobase.authn`, `kotobase.blocks`, `kotobase.cacao` (Kotoba project library) |
| `kotoba.ekyc` | `kotoba.ekyc/src` | `ekyc.adapters.edn-provider`, `ekyc.adapters.identity-bridge`, `ekyc.adapters.kagi-custody`, `ekyc.adapters.production-provider` (Kotoba project library) |
| `kotoba.contentAddress` | `kotoba.contentAddress/src` | `content-address.app-schema`, `content-address.archive`, `content-address.core`, `content-address.digest` (Kotoba project library) |
| `kotoba.character` | `kotoba.character/src` | `character`, `character.anim-blueprint`, `character.base-mesh`, `character.bin` (Kotoba project library) |
| `kotoba.machine` | `kotoba.machine/src` | `machine.core` (Kotoba project library) |
| `kotoba.security` | `kotoba.security/src` | `kotoba.security.abac`, `kotoba.security.adoption`, `kotoba.security.aead`, `kotoba.security.alert-adapters` (Kotoba project library) |
| `kotoba.journal` | `kotoba.journal/src` | `journal.core`, `journal.fs` (Kotoba project library) |
| `kotoba.shitsuke` | `kotoba.shitsuke/src` | `kotoba.editor`, `shitsuke.components`, `shitsuke.hiccup`, `shitsuke.hig` (Kotoba project library) |
| `kotoba.calendar` | `kotoba.calendar/src` | `calendar.kotoba-oracle`, `calendar.model`, `calendar.validate` (Kotoba project library) |
| `kotoba.rtc` | `kotoba.rtc/src` | `rtc`, `rtc.media`, `rtc.peer`, `rtc.room` (Kotoba project library) |
| `kotoba.property` | `kotoba.property/src` | `kotoba.property`, `kotoba.property.audit-runtime`, `kotoba.property.bulk-csv`, `kotoba.property.collector` (Kotoba project library) |
| `kotoba.paillier` | `kotoba.paillier/src` | `paillier.core` (Kotoba project library) |
| `kotoba.omise` | `kotoba.omise/src` | `kotoba.omise`, `kotoba.omise.export`, `kotoba.omise.ui` (Kotoba project library) |
| `kotoba.mst` | `kotoba.mst/src` | `mst.core` (Kotoba project library) |
| `kotoba.mangaViewer` | `kotoba.mangaViewer/src` | `manga-viewer.model`, `manga-viewer.pagination`, `manga-viewer.render`, `manga-viewer.style` (Kotoba project library) |
| `kotoba.live` | `kotoba.live/src` | `kotoba.live`, `kotoba.live.audio`, `kotoba.live.avatar`, `kotoba.live.beat` (Kotoba project library) |
| `kotoba.kotobaActors` | `kotoba.kotobaActors/src` | `kotoba-actors.asobi`, `kotoba-actors.config`, `kotoba-actors.datomic`, `kotoba-actors.hokorobi` (Kotoba project library) |
| `kotoba.katex` | `kotoba.katex/src` | `kotoba.lang.katex.mathml`, `kotoba.lang.katex.parse` (Kotoba project library) |
| `kotoba.kamiOngakuNotation` | `kotoba.kamiOngakuNotation/src` | `kami.ongaku.notation`, `kami.ongaku.notation.duration`, `kami.ongaku.notation.musicxml`, `kami.ongaku.notation.pitch` (Kotoba project library) |
| `kotoba.sdf` | `kotoba.sdf/src` | `sdf` (Kotoba project library) |
| `kotoba.kamiEngineCad` | `kotoba.kamiEngineCad/src` | `kami.cad` (Kotoba project library) |
| `kotoba.kamiEngineAppSdk` | `kotoba.kamiEngineAppSdk/src` | `kami-ui-sdk`, `kami-ui-sdk.effect`, `kami-ui-sdk.engine-audio`, `kami-ui-sdk.motion` (Kotoba project library) |
| `kotoba.kamiAppTatekata` | `kotoba.kamiAppTatekata/src` | `kotoba.tatekata`, `kotoba.tatekata.deposit-field`, `kotoba.tatekata.process`, `kotoba.tatekata.thermal` (Kotoba project library) |
| `kotoba.kamiAppSarutahikoFactory` | `kotoba.kamiAppSarutahikoFactory/src` | `kotoba.sarutahiko-factory`, `kotoba.sarutahiko-factory.clashes`, `kotoba.sarutahiko-factory.construction-order`, `kotoba.sarutahiko-factory.factory` (Kotoba project library) |
| `kotoba.ioStorj` | `kotoba.ioStorj/src` | `storj.core`, `storj.gateway`, `storj.linkshare`, `storj.protocols` (Kotoba project library) |
| `kotoba.kotobaDatom` | `kotoba.kotobaDatom/src` | `kotoba.datom` (Kotoba project library) |
| `kotoba.glyph` | `kotoba.glyph/src` | `kotoba.glyph`, `kotoba.glyph.atlas`, `kotoba.glyph.constants`, `kotoba.glyph.dynamic` (Kotoba project library) |
| `kotoba.game` | `kotoba.game/src` | `game`, `game.addons`, `game.analytics`, `game.animation` (Kotoba project library) |
| `kotoba.drive` | `kotoba.drive/src` | `drive.model`, `drive.object`, `drive.store.fs`, `drive.store.memory` (Kotoba project library) |
| `kotoba.srs` | `kotoba.srs/src` | `srs.core`, `srs.host`, `srs.lifecycle`, `srs.status` (Kotoba project library) |
| `kotoba.okaimono` | `kotoba.okaimono/src` | `kotoba.okaimono`, `kotoba.okaimono.export`, `kotoba.okaimono.ui` (Kotoba project library) |
| `kotoba.comSonyDualsense` | `kotoba.comSonyDualsense/src` | `kotoba.dualsense.crc32`, `kotoba.dualsense.input`, `kotoba.dualsense.output` (Kotoba project library) |
| `kotoba.chIec61850` | `kotoba.chIec61850/src` | `iec61850.appdu`, `iec61850.data`, `iec61850.goose`, `iec61850.utctime` (Kotoba project library) |
| `kotoba.oidc` | `kotoba.oidc/src` | `oidc.adapters.discovery`, `oidc.adapters.identity-bridge`, `oidc.adapters.jwks`, `oidc.adapters.jwt-claims` (Kotoba project library) |
| `kotoba.codebase` | `kotoba.codebase/src` | `kotoba.codebase.actor`, `kotoba.codebase.authoring`, `kotoba.codebase.backend`, `kotoba.codebase.backend.kotobase` (Kotoba project library) |
| `kotoba.arrangement` | `kotoba.arrangement/src` | `arrangement.core`, `arrangement.datalog`, `arrangement.partitioned`, `arrangement.query` (Kotoba project library) |
| `kotoba.prollyTree` | `kotoba.prollyTree/src` | `prolly-tree.adl`, `prolly-tree.core`, `prolly-tree.diff`, `prolly-tree.ordered-map` (Kotoba project library) |
| `kotoba.image` | `kotoba.image/src` | `kotoba.image`, `kotoba.image.gray` (Kotoba project library) |
| `kotoba.atprotocol` | `kotoba.atprotocol/src` | `atprotocol.app-record`, `atprotocol.boundary`, `atprotocol.profile`, `atprotocol.projection` (Kotoba project library) |
| `kotoba.artifact` | `kotoba.artifact/src` | `kotoba.artifact.content-identity`, `kotoba.artifact.core`, `kotoba.artifact.descriptor-table`, `kotoba.artifact.execution` (Kotoba project library) |
| `kotoba.productParty` | `kotoba.productParty/src` | `kotoba.product-party` (Kotoba project library) |
| `kotoba.pay` | `kotoba.pay/src` | `pay.core`, `pay.eip3009`, `pay.facilitator`, `pay.rail.base-l2` (Kotoba project library) |
| `kotoba.num` | `kotoba.num/src` | `num.array`, `num.autograd`, `num.core`, `num.cpu` (Kotoba project library) |
| `kotoba.ioFilecoin` | `kotoba.ioFilecoin/src` | `filecoin.address`, `filecoin.bigint`, `filecoin.cid`, `filecoin.message` (Kotoba project library) |
| `kotoba.hil` | `kotoba.hil/src` | `hil.core` (Kotoba project library) |
| `kotoba.cron` | `kotoba.cron/src` | `cron.execute`, `cron.model`, `cron.validate` (Kotoba project library) |
| `kotoba.crm` | `kotoba.crm/src` | `kotoba.crm.funnel`, `kotoba.crm.leadscore`, `kotoba.crm.pipeline`, `kotoba.crm.revrec` (Kotoba project library) |
| `kotoba.crdt` | `kotoba.crdt/src` | `kotoba.crdt.clock`, `kotoba.crdt.doc`, `kotoba.crdt.kotoba-oracle`, `kotoba.crdt.orset` (Kotoba project library) |
| `kotoba.contacts` | `kotoba.contacts/src` | `contacts.model`, `contacts.validate` (Kotoba project library) |
| `kotoba.consumability` | `kotoba.consumability/src` | `consumability.core` (Kotoba project library) |
| `kotoba.composer` | `kotoba.composer/src` | `kotoba.composer`, `kotoba.composer.generation`, `kotoba.composer.pipeline`, `kotoba.composer.stem` (Kotoba project library) |
| `kotoba.comTeamsBot` | `kotoba.comTeamsBot/src` | `teams.client`, `teams.events`, `teams.jwt`, `teams.jwt-verify` (Kotoba project library) |
| `kotoba.comProlificApp` | `kotoba.comProlificApp/src` | `prolific.browser`, `prolific.channel`, `prolific.client`, `prolific.core` (Kotoba project library) |
| `kotoba.comProfibusProfinet` | `kotoba.comProfibusProfinet/src` | `profinet.dcp`, `profinet.ethernet`, `profinet.rt` (Kotoba project library) |
| `kotoba.comNvidiaIsaacSim` | `kotoba.comNvidiaIsaacSim/src` | `genesis`, `genesis.articulation3d`, `genesis.batched`, `genesis.cartpole` (Kotoba project library) |
| `kotoba.comMetaWebhook` | `kotoba.comMetaWebhook/src` | `meta-webhook.async-signature`, `meta-webhook.handshake`, `meta-webhook.instagram-client`, `meta-webhook.instagram-events` (Kotoba project library) |
| `kotoba.comMattermost` | `kotoba.comMattermost/src` | `mattermost.client` (Kotoba project library) |
| `kotoba.comMatrix` | `kotoba.comMatrix/src` | `matrix.client` (Kotoba project library) |
| `kotoba.comMapillaryGraphApi` | `kotoba.comMapillaryGraphApi/src` | `com-mapillary-graph-api.core`, `com-mapillary-graph-api.fetch` (Kotoba project library) |
| `kotoba.comLinkedin` | `kotoba.comLinkedin/src` | `linkedin.client` (Kotoba project library) |
| `kotoba.comLineMessaging` | `kotoba.comLineMessaging/src` | `line-messaging.async-signature`, `line-messaging.client`, `line-messaging.events`, `line-messaging.signature` (Kotoba project library) |
| `kotoba.comInstagram` | `kotoba.comInstagram/src` | `instagram.client` (Kotoba project library) |
| `kotoba.comAviationIaArinc664` | `kotoba.comAviationIaArinc664/src` | `afdx.bag`, `afdx.bytes`, `afdx.ethernet`, `afdx.frame` (Kotoba project library) |
| `kotoba.comAviationIaArinc429` | `kotoba.comAviationIaArinc429/src` | `arinc429.bcd`, `arinc429.bits`, `arinc429.bnr`, `arinc429.label` (Kotoba project library) |
| `kotoba.comAppleTouchid` | `kotoba.comAppleTouchid/src` | `touchid.biometric` (Kotoba project library) |
| `kotoba.comAppleFileprovider` | `kotoba.comAppleFileprovider/src` | `fileprovider.model` (Kotoba project library) |
| `kotoba.comAppleFaceid` | `kotoba.comAppleFaceid/src` | `faceid.biometric` (Kotoba project library) |
| `kotoba.comAdobeCmap` | `kotoba.comAdobeCmap/src` | `adobe.cmap.core` (Kotoba project library) |
| `kotoba.cncToolpath` | `kotoba.cncToolpath/src` | `cnc-toolpath`, `cnc-toolpath.gcode`, `cnc-toolpath.stock`, `cnc-toolpath.tool` (Kotoba project library) |
| `kotoba.cloudMurakumoGeneration` | `kotoba.cloudMurakumoGeneration/src` | `murakumo.generation`, `murakumo.generation.client`, `murakumo.generation.digest`, `murakumo.generation.image` (Kotoba project library) |
| `kotoba.cljHost` | `kotoba.cljHost/src` | `kotoba.clj-host`, `kotoba.clj-host.frame` (Kotoba project library) |
| `kotoba.ci` | `kotoba.ci/src` | `ci.execute`, `ci.model`, `ci.run`, `ci.validate` (Kotoba project library) |
| `kotoba.chainObserver` | `kotoba.chainObserver/src` | `chain.observer`, `chain.observer.contract`, `chain.observer.cosmos`, `chain.observer.evm` (Kotoba project library) |
| `kotoba.chain` | `kotoba.chain/src` | `chain.authorized`, `chain.core` (Kotoba project library) |
| `kotoba.chIec608705104` | `kotoba.chIec608705104/src` | `iec60870.apci`, `iec60870.asdu`, `iec60870.float32`, `iec60870.frame` (Kotoba project library) |
| `kotoba.kotobaseStorage` | `kotoba.kotobaseStorage/src` | `kotobase.storage.async-contract`, `kotobase.storage.contract`, `kotobase.storage.core`, `kotobase.storage.memory` (Kotoba project library) |
| `kotoba.cofog` | `kotoba.cofog/src` | `kotoba.cofog`, `kotoba.cofog.embedded` (Kotoba project library) |
| `kotoba.technology` | `kotoba.technology/src` | `kotoba.technology`, `kotoba.technology.embedded` (Kotoba project library) |
| `kotoba.torrentApp` | `kotoba.torrentApp/src` | `kotoba.torrent-app`, `kotoba.torrent-app.download` (Kotoba project library) |
| `kotoba.techIpfsSpecsHttpGateway` | `kotoba.techIpfsSpecsHttpGateway/src` | `gateway.cache`, `gateway.request`, `gateway.resolve` (Kotoba project library) |
| `kotoba.oauth` | `kotoba.oauth/src` | `oauth.adapters.client-auth`, `oauth.adapters.discovery`, `oauth.adapters.http`, `oauth.adapters.java-http` (Kotoba project library) |
| `kotoba.kotobaIssue` | `kotoba.kotobaIssue/src` | `kotoba.issue.bcf`, `kotoba.issue.bcf.xml`, `kotoba.issue.gate`, `kotoba.issue.opencde` (Kotoba project library) |
| `kotoba.ioStripeIssuing` | `kotoba.ioStripeIssuing/src` | `io.stripe.issuing.core`, `io.stripe.issuing.exercise`, `io.stripe.issuing.state` (Kotoba project library) |
| `kotoba.ctf` | `kotoba.ctf/src` | `ctf.adapters.auth-client`, `ctf.adapters.etzhayyim`, `ctf.adapters.evidence-ledger`, `ctf.adapters.retry` (Kotoba project library) |
| `kotoba.atprotoClient` | `kotoba.atprotoClient/src` | `kotoba.lang.atproto-client.atproto`, `kotoba.lang.atproto-client.http-jdk`, `kotoba.lang.atproto-client.pds` (Kotoba project library) |
| `kotoba.aml` | `kotoba.aml/src` | `aml.adapters.auth-client`, `aml.adapters.etzhayyim`, `aml.adapters.evidence-ledger`, `aml.adapters.retry` (Kotoba project library) |
| `kotoba.zone` | `kotoba.zone/src` | `zone.model`, `zone.validate`, `zone.zone` (Kotoba project library) |
| `kotoba.yakuwariView` | `kotoba.yakuwariView/src` | `yakuwari-view.hiccup`, `yakuwari-view.model` (Kotoba project library) |
| `kotoba.yakuwari` | `kotoba.yakuwari/src` | `yakuwari.policy`, `yakuwari.reconcile`, `yakuwari.spec` (Kotoba project library) |
| `kotoba.xyzUcan` | `kotoba.xyzUcan/src` | `ucan.core` (Kotoba project library) |
| `kotoba.x402Directory` | `kotoba.x402Directory/src` | `x402.directory` (Kotoba project library) |
| `kotoba.worklaw` | `kotoba.worklaw/src` | `kotoba.worklaw` (Kotoba project library) |
| `kotoba.windowSessionState` | `kotoba.windowSessionState/src` | `window-session-state`, `window-session-state.compositor`, `window-session-state.file-explorer`, `window-session-state.input-router` (Kotoba project library) |
| `kotoba.wici` | `kotoba.wici/src` | `wici.device`, `wici.place`, `wici.protocol`, `wici.remote` (Kotoba project library) |
| `kotoba.webrtc` | `kotoba.webrtc/src` | `kotoba.webrtc`, `kotoba.webrtc.export`, `kotoba.webrtc.room`, `kotoba.webrtc.session` (Kotoba project library) |
| `kotoba.webModelb` | `kotoba.webModelb/src` | `kotoba.web-modelb`, `kotoba.web-modelb.config` (Kotoba project library) |
| `kotoba.voxel` | `kotoba.voxel/src` | `voxel`, `voxel.nvdb`, `voxel.vdb`, `voxel.vdb-file` (Kotoba project library) |
| `kotoba.vllm` | `kotoba.vllm/src` | `vllm.accelerator`, `vllm.core`, `vllm.generate`, `vllm.gguf` (Kotoba project library) |
| `kotoba.userTest` | `kotoba.userTest/src` | `kotoba.user-test`, `kotoba.user-test.cli`, `kotoba.user-test.io`, `kotoba.user-test.mcp` (Kotoba project library) |
| `kotoba.uptime` | `kotoba.uptime/src` | `uptime.core` (Kotoba project library) |
| `kotoba.triage` | `kotoba.triage/src` | `triage.classify`, `triage.eval`, `triage.metrics` (Kotoba project library) |
| `kotoba.toshokanPatents` | `kotoba.toshokanPatents/src` | `toshokan-patents.quad`, `toshokan-patents.quad.fs`, `toshokan-patents.sources.google-patents` (Kotoba project library) |
| `kotoba.torihikiChart` | `kotoba.torihikiChart/src` | `torihiki-chart.axis`, `torihiki-chart.candle`, `torihiki-chart.depth`, `torihiki-chart.view` (Kotoba project library) |
| `kotoba.tilemap` | `kotoba.tilemap/src` | `tilemap` (Kotoba project library) |
| `kotoba.tex` | `kotoba.tex/src` | `kotoba.lang.tex.core` (Kotoba project library) |
| `kotoba.terrain` | `kotoba.terrain/src` | `terrain`, `terrain.biome`, `terrain.chunk`, `terrain.heightmap` (Kotoba project library) |
| `kotoba.tedai` | `kotoba.tedai/src` | `tedai.cells.actuate-invoke.state-machine`, `tedai.cells.app-resolve.state-machine`, `tedai.cells.evidence-audit.state-machine`, `tedai.cells.intent-plan.state-machine` (Kotoba project library) |
| `kotoba.taxlaw` | `kotoba.taxlaw/src` | `kotoba.taxlaw` (Kotoba project library) |
| `kotoba.swift` | `kotoba.swift/src` | `kotoba.swift`, `kotoba.swift.export`, `kotoba.swift.iso20022`, `kotoba.swift.ui` (Kotoba project library) |
| `kotoba.treasury` | `kotoba.treasury/src` | `treasury.core` (Kotoba project library) |
| `kotoba.states` | `kotoba.states/src` | `states.execute`, `states.json`, `states.model`, `states.ports` (Kotoba project library) |
| `kotoba.statechart` | `kotoba.statechart/src` | `statechart.execute`, `statechart.model`, `statechart.ports`, `statechart.validate` (Kotoba project library) |
| `kotoba.standardModel` | `kotoba.standardModel/src` | `kotoba.sm.complex`, `kotoba.sm.gauge`, `kotoba.sm.gtg`, `kotoba.sm.spinor` (Kotoba project library) |
| `kotoba.socialPublication` | `kotoba.socialPublication/src` | `etzhayyim.social.publication` (Kotoba project library) |
| `kotoba.skeleton` | `kotoba.skeleton/src` | `skeleton`, `skeleton.math` (Kotoba project library) |
| `kotoba.simulatedUser` | `kotoba.simulatedUser/src` | `simulated-user.eval`, `simulated-user.interaction`, `simulated-user.model`, `simulated-user.murakumo` (Kotoba project library) |
| `kotoba.sigma` | `kotoba.sigma/src` | `sigma.execute`, `sigma.model`, `sigma.ports`, `sigma.validate` (Kotoba project library) |
| `kotoba.si` | `kotoba.si/src` | `kotoba.si`, `kotoba.si.constants`, `kotoba.si.crosstalk`, `kotoba.si.eye-diagram` (Kotoba project library) |
| `kotoba.shousetsu` | `kotoba.shousetsu/src` | `shousetsu.serialization` (Kotoba project library) |
| `kotoba.shomen` | `kotoba.shomen/src` | `shomen.catalog`, `shomen.classify`, `shomen.coverage`, `shomen.requirement` (Kotoba project library) |
| `kotoba.shokyaku` | `kotoba.shokyaku/src` | `kotoba.shokyaku`, `kotoba.shokyaku.embedded` (Kotoba project library) |
| `kotoba.shift` | `kotoba.shift/src` | `kotoba.shift` (Kotoba project library) |
| `kotoba.sheets` | `kotoba.sheets/src` | `sheets.chart`, `sheets.csv`, `sheets.edit`, `sheets.formula` (Kotoba project library) |
| `kotoba.session` | `kotoba.session/src` | `session.adapters.datomic-kotoba`, `session.adapters.datomic-kotoba-cluster`, `session.adapters.edn-file`, `session.adapters.store` (Kotoba project library) |
| `kotoba.senkyo` | `kotoba.senkyo/src` | `senkyo.authority`, `senkyo.datoms`, `senkyo.facts`, `senkyo.medium` (Kotoba project library) |
| `kotoba.tetsuzuki` | `kotoba.tetsuzuki/src` | `tetsuzuki.catalog`, `tetsuzuki.coverage`, `tetsuzuki.deadline`, `tetsuzuki.ooyake` (Kotoba project library) |
| `kotoba.sekisho` | `kotoba.sekisho/src` | `sekisho.account`, `sekisho.assurance`, `sekisho.browser`, `sekisho.didkey` (Kotoba project library) |
| `kotoba.secretResolve` | `kotoba.secretResolve/src` | `secret-resolve.core`, `secret-resolve.exec`, `secret-resolve.resolver`, `secret-resolve.sources` (Kotoba project library) |
| `kotoba.sceneGraph` | `kotoba.sceneGraph/src` | `scene-graph` (Kotoba project library) |
| `kotoba.scene` | `kotoba.scene/src` | `scene` (Kotoba project library) |
| `kotoba.rtxNative` | `kotoba.rtxNative/src` | `kotoba.rtx-native` (Kotoba project library) |
| `kotoba.retail` | `kotoba.retail/src` | `kotoba.retail`, `kotoba.retail.export`, `kotoba.retail.ui` (Kotoba project library) |
| `kotoba.reservation` | `kotoba.reservation/src` | `kotoba.reservation`, `kotoba.reservation.export`, `kotoba.reservation.ui` (Kotoba project library) |
| `kotoba.replicator` | `kotoba.replicator/src` | `kotoba.replicator` (Kotoba project library) |
| `kotoba.remocon` | `kotoba.remocon/src` | `remocon.match`, `remocon.nec`, `remocon.pronto`, `remocon.raw` (Kotoba project library) |
| `kotoba.reji` | `kotoba.reji/src` | `kotoba.reji.core`, `kotoba.reji.currency` (Kotoba project library) |
| `kotoba.rdfCanon` | `kotoba.rdfCanon/src` | `rdf-canon.core` (Kotoba project library) |
| `kotoba.rcs` | `kotoba.rcs/src` | `kotoba.rcs`, `kotoba.rcs.export`, `kotoba.rcs.ui` (Kotoba project library) |
| `kotoba.raytrace` | `kotoba.raytrace/src` | `kotoba.raytrace`, `kotoba.raytrace.bvh`, `kotoba.raytrace.config`, `kotoba.raytrace.denoise` (Kotoba project library) |
| `kotoba.quickjs` | `kotoba.quickjs/src` | `quickjs.binary` (Kotoba project library) |
| `kotoba.quarantine` | `kotoba.quarantine/src` | `quarantine.core`, `quarantine.host` (Kotoba project library) |
| `kotoba.psa` | `kotoba.psa/src` | `kotoba.psa` (Kotoba project library) |
| `kotoba.providerPostgres` | `kotoba.providerPostgres/src` | `provider.postgres.pool` (Kotoba project library) |
| `kotoba.providerIncidence` | `kotoba.providerIncidence/src` | `provider.incidence` (Kotoba project library) |
| `kotoba.presentationml` | `kotoba.presentationml/src` | `presentationml.core`, `presentationml.parse` (Kotoba project library) |
| `kotoba.power` | `kotoba.power/src` | `power`, `power.em`, `power.estimation`, `power.ir-drop` (Kotoba project library) |
| `kotoba.postfx` | `kotoba.postfx/src` | `postfx` (Kotoba project library) |
| `kotoba.policy` | `kotoba.policy/src` | `policy.execute`, `policy.model`, `policy.ports`, `policy.validate` (Kotoba project library) |
| `kotoba.wsValuefloVocabulary` | `kotoba.wsValuefloVocabulary/src` | `valueflows.commitment`, `valueflows.conform`, `valueflows.data`, `valueflows.datom` (Kotoba project library) |
| `kotoba.pkg` | `kotoba.pkg/src` | `kotoba.pkg`, `kotoba.pkg.bonding`, `kotoba.pkg.package`, `kotoba.pkg.registry` (Kotoba project library) |
| `kotoba.persona` | `kotoba.persona/src` | `persona.core`, `persona.relay` (Kotoba project library) |
| `kotoba.wordId` | `kotoba.wordId/src` | `word-id.core`, `word-id.english`, `word-id.vocabulary` (Kotoba project library) |
| `kotoba.pedigree` | `kotoba.pedigree/src` | `kotoba.pedigree` (Kotoba project library) |
| `kotoba.pcb` | `kotoba.pcb/src` | `pcb`, `pcb.erc`, `pcb.layout`, `pcb.netlist` (Kotoba project library) |
| `kotoba.pbrt` | `kotoba.pbrt/src` | `kotoba.pbrt` (Kotoba project library) |
| `kotoba.pattern` | `kotoba.pattern/src` | `pattern.compile` (Kotoba project library) |
| `kotoba.pathfind` | `kotoba.pathfind/src` | `pathfind` (Kotoba project library) |
| `kotoba.otio` | `kotoba.otio/src` | `kotoba.otio`, `otio.core` (Kotoba project library) |
| `kotoba.osActor` | `kotoba.osActor/src` | `os.murakumo` (Kotoba project library) |
| `kotoba.optimalTransport` | `kotoba.optimalTransport/src` | `optimal-transport.mesh-morph`, `optimal-transport.sinkhorn` (Kotoba project library) |
| `kotoba.openapi` | `kotoba.openapi/src` | `openapi.execute`, `openapi.json`, `openapi.model`, `openapi.ports` (Kotoba project library) |
| `kotoba.ooyake` | `kotoba.ooyake/src` | `ooyake.cells.reconcile.cell`, `ooyake.cells.reconcile.state-machine`, `ooyake.cells.social-post.state-machine`, `ooyake.cells.world-model.cell` (Kotoba project library) |
| `kotoba.ontology` | `kotoba.ontology/src` | `kotoba.ontology`, `kotoba.ontology.connector` (Kotoba project library) |
| `kotoba.ongaku` | `kotoba.ongaku/src` | `ongaku.catalog`, `ongaku.commission`, `ongaku.compose`, `ongaku.holdings` (Kotoba project library) |
| `kotoba.oneTimeLink` | `kotoba.oneTimeLink/src` | `one-time-link.core` (Kotoba project library) |
| `kotoba.ocio` | `kotoba.ocio/src` | `kotoba.ocio`, `ocio.core`, `ocio.transform` (Kotoba project library) |
| `kotoba.yaml` | `kotoba.yaml/src` | `kotoba.yaml` (Kotoba project library) |
| `kotoba.oak` | `kotoba.oak/src` | `oak.semantic` (Kotoba project library) |
| `kotoba.nuno` | `kotoba.nuno/src` | `nuno.core` (Kotoba project library) |
| `kotoba.nio` | `kotoba.nio/src` | `kotoba.nio.bytebuffer` (Kotoba project library) |
| `kotoba.netcap` | `kotoba.netcap/src` | `kotoba.lang.netcap`, `kotoba.netcap`, `kotoba.netcap.call`, `kotoba.netcap.denied` (Kotoba project library) |
| `kotoba.nerf` | `kotoba.nerf/src` | `nerf` (Kotoba project library) |
| `kotoba.musicxml` | `kotoba.musicxml/src` | `kotoba.musicxml`, `musicxml.core` (Kotoba project library) |
| `kotoba.mstProjector` | `kotoba.mstProjector/src` | `kotoba.lang.mst-projector.cli`, `kotoba.lang.mst-projector.indexer`, `kotoba.lang.mst-projector.mem-index`, `kotoba.lang.mst-projector.query-api` (Kotoba project library) |
| `kotoba.mokuroku` | `kotoba.mokuroku/src` | `mokuroku.catalog`, `mokuroku.command`, `mokuroku.inspector`, `mokuroku.item` (Kotoba project library) |
| `kotoba.modelChecking` | `kotoba.modelChecking/src` | `model-checking`, `model-checking.assertion`, `model-checking.coverage`, `model-checking.equivalence` (Kotoba project library) |
| `kotoba.miningPool` | `kotoba.miningPool/src` | `mining-pool.ledger`, `mining-pool.protocol`, `mining-pool.share`, `mining-pool.vardiff` (Kotoba project library) |
| `kotoba.minePds` | `kotoba.minePds/src` | `mine-pds` (Kotoba project library) |
| `kotoba.mineAi` | `kotoba.mineAi/src` | `mine-ai` (Kotoba project library) |
| `kotoba.mfa` | `kotoba.mfa/src` | `mfa.adapters.live-risk`, `mfa.adapters.orchestrator`, `mfa.adapters.planner`, `mfa.adapters.risk-planner` (Kotoba project library) |
| `kotoba.mathml` | `kotoba.mathml/src` | `kotoba.mathml`, `mathml.core` (Kotoba project library) |
| `kotoba.manimaniExperienceUi` | `kotoba.manimaniExperienceUi/src` | `manimani.build`, `manimani.ui` (Kotoba project library) |
| `kotoba.manifestReality` | `kotoba.manifestReality/src` | `manifest-reality.checks`, `manifest-reality.parse` (Kotoba project library) |
| `kotoba.mailer` | `kotoba.mailer/src` | `mailer.core` (Kotoba project library) |
| `kotoba.mailA2a` | `kotoba.mailA2a/src` | `mail-a2a.core` (Kotoba project library) |
| `kotoba.mail` | `kotoba.mail/src` | `mail.draft`, `mail.inbound`, `mail.mailbox`, `mail.message` (Kotoba project library) |
| `kotoba.macosInventory` | `kotoba.macosInventory/src` | `macos-inventory.cli`, `macos-inventory.core`, `macos-inventory.host` (Kotoba project library) |
| `kotoba.loopUxKaizen` | `kotoba.loopUxKaizen/src` | `loop.ux-kaizen` (Kotoba project library) |
| `kotoba.loopMaturityAudit` | `kotoba.loopMaturityAudit/src` | `loop-maturity-audit.core` (Kotoba project library) |
| `kotoba.loopLeiCatalog` | `kotoba.loopLeiCatalog/src` | `loop-lei-catalog.core` (Kotoba project library) |
| `kotoba.loopKaProduction` | `kotoba.loopKaProduction/src` | `loop-ka.decide`, `loop-ka.evaluate`, `loop-ka.ledger`, `loop-ka.observe` (Kotoba project library) |
| `kotoba.shinka` | `kotoba.shinka/src` | `shinka.evolve`, `shinka.genome`, `shinka.rng`, `shinka.variation` (Kotoba project library) |
| `kotoba.logistics` | `kotoba.logistics/src` | `kotoba.logistics`, `kotoba.logistics.export`, `kotoba.logistics.ui` (Kotoba project library) |
| `kotoba.labor` | `kotoba.labor/src` | `kotoba.labor`, `kotoba.labor.export`, `kotoba.labor.ui` (Kotoba project library) |
| `kotoba.kyoninka` | `kotoba.kyoninka/src` | `kyoninka.deu-abfall-transport`, `kyoninka.dossier`, `kyoninka.errand`, `kyoninka.gbr-scrap-metal` (Kotoba project library) |
| `kotoba.merkleSum` | `kotoba.merkleSum/src` | `merkle-sum.core` (Kotoba project library) |
| `kotoba.kowane` | `kotoba.kowane/src` | `kowane.lpc` (Kotoba project library) |
| `kotoba.kototamaComponent` | `kotoba.kototamaComponent/src` | `tender.component` (Kotoba project library) |
| `kotoba.kotobaseProjection` | `kotoba.kotobaseProjection/src` | `kotobase.projection`, `kotobase.projection.datalog`, `kotobase.projection.publication`, `kotobase.projection.statistics` (Kotoba project library) |
| `kotoba.merkleLsm` | `kotoba.merkleLsm/src` | `merkle-lsm.compaction`, `merkle-lsm.core` (Kotoba project library) |
| `kotoba.kotobaseMaintenance` | `kotoba.kotobaseMaintenance/src` | `kotobase.maintenance.restore`, `kotobase.maintenance.resumable`, `kotobase.maintenance.retention` (Kotoba project library) |
| `kotoba.kotobaseFederation` | `kotoba.kotobaseFederation/src` | `kotobase.federation` (Kotoba project library) |
| `kotoba.kotobaseBlockCodec` | `kotoba.kotobaseBlockCodec/src` | `kotobase.blockcodec.core`, `kotobase.blockcodec.node`, `kotobase.blockcodec.statemix` (Kotoba project library) |
| `kotoba.kotobaseAnchorFevm` | `kotoba.kotobaseAnchorFevm/src` | `kotobase.anchor.checkpoint`, `kotobase.anchor.fevm`, `kotobase.anchor.fevm.queue` (Kotoba project library) |
| `kotoba.kotobaseEngineContract` | `kotoba.kotobaseEngineContract/src` | `kotobase.engine.archive`, `kotobase.engine.canonical`, `kotobase.engine.completion`, `kotobase.engine.conformance` (Kotoba project library) |
| `kotoba.kotobaProcedure` | `kotoba.kotobaProcedure/src` | `kotoba.procedure.gate`, `kotoba.procedure.store` (Kotoba project library) |
| `kotoba.kotobaObject` | `kotoba.kotobaObject/src` | `kotoba.object.elf64`, `kotoba.object.macho64`, `kotoba.object.pe32plus` (Kotoba project library) |
| `kotoba.kotobaLedger` | `kotoba.kotobaLedger/src` | `kotoba.ledger.core`, `kotoba.ledger.file-git`, `kotoba.ledger.kotobase` (Kotoba project library) |
| `kotoba.kotobaHir` | `kotoba.kotobaHir/src` | `kotoba.hir` (Kotoba project library) |
| `kotoba.kotobaFleet` | `kotoba.kotobaFleet/src` | `kotoba.fleet.agent`, `kotoba.fleet.core`, `kotoba.fleet.evolution`, `kotoba.fleet.governor` (Kotoba project library) |
| `kotoba.kotobaDocumentContracts` | `kotoba.kotobaDocumentContracts/src` | `kotoba.document.artifact-graph`, `kotoba.document.change`, `kotoba.document.collaboration`, `kotoba.document.dom` (Kotoba project library) |
| `kotoba.kotobaCodegen` | `kotoba.kotobaCodegen/src` | `kotoba.codegen.layout`, `kotoba.codegen.mc`, `kotoba.codegen.relocation` (Kotoba project library) |
| `kotoba.kotobaMir` | `kotoba.kotobaMir/src` | `kotoba.mir` (Kotoba project library) |
| `kotoba.kotobaGmir` | `kotoba.kotobaGmir/src` | `kotoba.gmir` (Kotoba project library) |
| `kotoba.kotobaClient` | `kotoba.kotobaClient/src` | `kotoba-client.core`, `kotoba-client.ipld-hydrate`, `kotoba-client.prolly-hydrate` (Kotoba project library) |
| `kotoba.kotobaCaptcha` | `kotoba.kotobaCaptcha/src` | `kotoba.captcha.api`, `kotoba.captcha.audit`, `kotoba.captcha.domain`, `kotoba.captcha.http` (Kotoba project library) |
| `kotoba.knp` | `kotoba.knp/src` | `knp`, `knp.channel`, `knp.packet`, `knp.session` (Kotoba project library) |
| `kotoba.kiss` | `kotoba.kiss/src` | `kiss.airtime`, `kiss.core` (Kotoba project library) |
| `kotoba.kip` | `kotoba.kip/src` | `kotoba.kip.core`, `kotoba.kip.quorum`, `kotoba.kip.registry` (Kotoba project library) |
| `kotoba.kgraph` | `kotoba.kgraph/src` | `kotoba.kgraph` (Kotoba project library) |
| `kotoba.kamiWebvr` | `kotoba.kamiWebvr/src` | `kami.webvr.cine-bridge`, `kami.webvr.engine`, `kami.webvr.incident-pregel`, `kami.webvr.types` (Kotoba project library) |
| `kotoba.kamiUsdNative` | `kotoba.kamiUsdNative/src` | `usd-native` (Kotoba project library) |
| `kotoba.kamiStudio` | `kotoba.kamiStudio/src` | `kami.studio.ui` (Kotoba project library) |
| `kotoba.kamiOngakuSampler` | `kotoba.kamiOngakuSampler/src` | `kami.ongaku.sampler` (Kotoba project library) |
| `kotoba.kamiOngakuSequencer` | `kotoba.kamiOngakuSequencer/src` | `kami.ongaku.sequencer`, `kami.ongaku.sequencer.smf` (Kotoba project library) |
| `kotoba.kamiOngakuPluginHost` | `kotoba.kamiOngakuPluginHost/src` | `kami.ongaku.plugin-host`, `kami.ongaku.plugin-host.graph` (Kotoba project library) |
| `kotoba.kamiMangakaText` | `kotoba.kamiMangakaText/src` | `kami.mangaka.hiccup`, `kami.mangaka.text` (Kotoba project library) |
| `kotoba.kamiMangakaSceneAuthor` | `kotoba.kamiMangakaSceneAuthor/src` | `kami.mangaka.scene` (Kotoba project library) |
| `kotoba.kamiMangakaScene` | `kotoba.kamiMangakaScene/src` | `mangaka-scene`, `mangaka-scene.camera`, `mangaka-scene.lexicon`, `mangaka-scene.pose` (Kotoba project library) |
| `kotoba.kamiMangakaRender` | `kotoba.kamiMangakaRender/src` | `kami.mangaka.render` (Kotoba project library) |
| `kotoba.kamiMangakaQa` | `kotoba.kamiMangakaQa/src` | `kami.mangaka.qa.axes`, `kami.mangaka.qa.geometry`, `kami.mangaka.qa.overlay`, `kami.mangaka.qa.perception` (Kotoba project library) |
| `kotoba.kamiIsekaiAssets` | `kotoba.kamiIsekaiAssets/src` | `kami.isekai.catalog`, `kami.isekai.chargen`, `kami.isekai.classes`, `kami.isekai.equipment` (Kotoba project library) |
| `kotoba.kamiGenSdfAgent` | `kotoba.kamiGenSdfAgent/src` | `kami.gen.sdf-agent`, `kami.gen.sdf-agent.critique`, `kami.gen.sdf-agent.propose`, `kami.gen.sdf-agent.render` (Kotoba project library) |
| `kotoba.scad` | `kotoba.scad/src` | `scad`, `scad.csg`, `scad.evaluator`, `scad.parser` (Kotoba project library) |
| `kotoba.vegetation` | `kotoba.vegetation/src` | `vegetation`, `vegetation.cull`, `vegetation.instance`, `vegetation.lod` (Kotoba project library) |
| `kotoba.mesher` | `kotoba.mesher/src` | `mesher`, `mesher.mc-tables` (Kotoba project library) |
| `kotoba.kamiEngineSculpt` | `kotoba.kamiEngineSculpt/src` | `kami.paint`, `kami.sculpt` (Kotoba project library) |
| `kotoba.kamiEngineInputMap` | `kotoba.kamiEngineInputMap/src` | `input-map` (Kotoba project library) |
| `kotoba.kamiEngineHudGpu` | `kotoba.kamiEngineHudGpu/src` | `ui_gpu` (Kotoba project library) |
| `kotoba.kamiEngineGuest` | `kotoba.kamiEngineGuest/src` | `kotoba.engine-clj`, `kotoba.engine-clj.ast`, `kotoba.engine-clj.codegen`, `kotoba.engine-clj.component` (Kotoba project library) |
| `kotoba.kamiEngWeb` | `kotoba.kamiEngWeb/src` | `eng-web`, `eng-web.cam`, `eng-web.coverage`, `eng-web.dft` (Kotoba project library) |
| `kotoba.kamiArticulated` | `kotoba.kamiArticulated/src` | `kami_articulated`, `kami_articulated.urdf` (Kotoba project library) |
| `kotoba.kamiAppQuarryWalk` | `kotoba.kamiAppQuarryWalk/src` | `kami-app-quarry-walk` (Kotoba project library) |
| `kotoba.nagare` | `kotoba.nagare/src` | `nagare.demo`, `nagare.diagnostics`, `nagare.field`, `nagare.fvm` (Kotoba project library) |
| `kotoba.kamiAppGiemonFactory` | `kotoba.kamiAppGiemonFactory/src` | `kami-app-giemon-factory`, `kami-app-giemon-factory.clashes`, `kami-app-giemon-factory.construction-order`, `kami-app-giemon-factory.factory` (Kotoba project library) |
| `kotoba.kamiAppGiemon` | `kotoba.kamiAppGiemon/src` | `kami-app-giemon`, `kami-app-giemon.armcrawler`, `kami-app-giemon.caterpillar`, `kami-app-giemon.geom` (Kotoba project library) |
| `kotoba.kamiAppCarSim` | `kotoba.kamiAppCarSim/src` | `kotoba.car-sim`, `kotoba.car-sim.color`, `kotoba.car-sim.controls`, `kotoba.car-sim.garage` (Kotoba project library) |
| `kotoba.kaiyu` | `kotoba.kaiyu/src` | `kaiyu.core`, `kaiyu.diagnose`, `kaiyu.session` (Kotoba project library) |
| `kotoba.kaisha` | `kotoba.kaisha/src` | `kaisha.model`, `kaisha.validate` (Kotoba project library) |
| `kotoba.jsonlogic` | `kotoba.jsonlogic/src` | `jsonlogic.core`, `jsonlogic.ports`, `jsonlogic.validate` (Kotoba project library) |
| `kotoba.jsonLd` | `kotoba.jsonLd/src` | `json-ld.core` (Kotoba project library) |
| `kotoba.jpHiroshibaVoicevox` | `kotoba.jpHiroshibaVoicevox/src` | `voicevox.client`, `voicevox.speakers`, `voicevox.synthesize` (Kotoba project library) |
| `kotoba.jiten` | `kotoba.jiten/src` | `jiten.core`, `jiten.link`, `jiten.revision`, `jiten.schema` (Kotoba project library) |
| `kotoba.itinerary` | `kotoba.itinerary/src` | `kotoba.itinerary` (Kotoba project library) |
| `kotoba.ipXact` | `kotoba.ipXact/src` | `ip-xact`, `ip-xact.bus-protocol`, `ip-xact.cdc`, `ip-xact.component` (Kotoba project library) |
| `kotoba.ip` | `kotoba.ip/src` | `kotoba.ip.bus-protocol`, `kotoba.ip.cdc`, `kotoba.ip.ip-xact`, `kotoba.ip.noc` (Kotoba project library) |
| `kotoba.sigv4` | `kotoba.sigv4/src` | `sigv4.core`, `sigv4.crypto`, `sigv4.protocols`, `sigv4.request` (Kotoba project library) |
| `kotoba.ioIpniSpecs` | `kotoba.ioIpniSpecs/src` | `ipni.ad`, `ipni.advertise`, `ipni.announce`, `ipni.find` (Kotoba project library) |
| `kotoba.ioIpfs` | `kotoba.ioIpfs/src` | `kotoba.lang.ipfs` (Kotoba project library) |
| `kotoba.intWhoIcd10` | `kotoba.intWhoIcd10/src` | `icd10.chapters`, `icd10.claml`, `icd10.code`, `icd10.compare` (Kotoba project library) |
| `kotoba.insurance` | `kotoba.insurance/src` | `kotoba.insurance`, `kotoba.insurance.eu`, `kotoba.insurance.export`, `kotoba.insurance.jp` (Kotoba project library) |
| `kotoba.input` | `kotoba.input/src` | `input` (Kotoba project library) |
| `kotoba.innen` | `kotoba.innen/src` | `innen.algo`, `innen.core`, `innen.schema`, `innen.time` (Kotoba project library) |
| `kotoba.identify` | `kotoba.identify/src` | `identify.adapters.edn-resolver`, `identify.adapters.production-resolvers`, `identify.adapters.resolver`, `identify.core` (Kotoba project library) |
| `kotoba.icPackaging` | `kotoba.icPackaging/src` | `ic-packaging`, `ic-packaging.bonding`, `ic-packaging.package`, `ic-packaging.thermal` (Kotoba project library) |
| `kotoba.kotobaseLake` | `kotoba.kotobaseLake/src` | `kotobase.lake.acquire`, `kotobase.lake.catalog`, `kotobase.lake.columnar`, `kotobase.lake.compact` (Kotoba project library) |
| `kotoba.ioIpldCar` | `kotoba.ioIpldCar/src` | `ipld.car`, `ipld.car.bytes`, `ipld.car.index`, `ipld.car.trustless` (Kotoba project library) |
| `kotoba.i18nActor` | `kotoba.i18nActor/src` | `i18n.murakumo` (Kotoba project library) |
| `kotoba.http` | `kotoba.http/src` | `kotoba.http`, `kotoba.http.decode-json-body`, `kotoba.http.fold-headers`, `kotoba.http.form-urlencoded` (Kotoba project library) |
| `kotoba.hinshitsu` | `kotoba.hinshitsu/src` | `hinshitsu.core`, `hinshitsu.mokushi` (Kotoba project library) |
| `kotoba.haishin` | `kotoba.haishin/src` | `haishin.adapt`, `haishin.artifact`, `haishin.constraints`, `haishin.core` (Kotoba project library) |
| `kotoba.groot` | `kotoba.groot/src` | `kotoba.groot`, `kotoba.groot.embodiment`, `kotoba.groot.episode`, `kotoba.groot.modality` (Kotoba project library) |
| `kotoba.graphql` | `kotoba.graphql/src` | `graphql.emit`, `graphql.execute`, `graphql.model`, `graphql.ports` (Kotoba project library) |
| `kotoba.graphml` | `kotoba.graphml/src` | `graphml.core`, `kotoba.graphml` (Kotoba project library) |
| `kotoba.graph` | `kotoba.graph/src` | `graph`, `graph.data`, `graph.layout` (Kotoba project library) |
| `kotoba.governor` | `kotoba.governor/src` | `governor.core` (Kotoba project library) |
| `kotoba.govDefenseMilStd1553` | `kotoba.govDefenseMilStd1553/src` | `mil1553.command`, `mil1553.data`, `mil1553.message`, `mil1553.mode` (Kotoba project library) |
| `kotoba.gitWorkspace` | `kotoba.gitWorkspace/src` | `kotoba.git-workspace` (Kotoba project library) |
| `kotoba.geojson` | `kotoba.geojson/src` | `geojson.core`, `kotoba.geojson` (Kotoba project library) |
| `kotoba.geo` | `kotoba.geo/src` | `kotoba.geo`, `kotoba.geo.billboard`, `kotoba.geo.constants`, `kotoba.geo.math` (Kotoba project library) |
| `kotoba.gameProduction` | `kotoba.gameProduction/src` | `game-production.audio`, `game-production.balance`, `game-production.knobs`, `game-production.spec` (Kotoba project library) |
| `kotoba.foundationIdentityDidwebvh` | `kotoba.foundationIdentityDidwebvh/src` | `didwebvh.did`, `didwebvh.entry`, `didwebvh.hash`, `didwebvh.log` (Kotoba project library) |
| `kotoba.forms` | `kotoba.forms/src` | `forms.model`, `forms.responses`, `forms.validate`, `forms.wire` (Kotoba project library) |
| `kotoba.transit` | `kotoba.transit/src` | `transit.core` (Kotoba project library) |
| `kotoba.force3d` | `kotoba.force3d/src` | `kotoba.lang.force3d.core` (Kotoba project library) |
| `kotoba.floorplanLab` | `kotoba.floorplanLab/src` | `floorplan-lab.ble`, `floorplan-lab.fusion`, `floorplan-lab.motion`, `floorplan-lab.sensing-bridge` (Kotoba project library) |
| `kotoba.filecoinCas` | `kotoba.filecoinCas/src` | `filecoin-cas.cid`, `filecoin-cas.engine`, `filecoin-cas.index`, `filecoin-cas.server` (Kotoba project library) |
| `kotoba.ffi` | `kotoba.ffi/src` | `kotoba.ffi` (Kotoba project library) |
| `kotoba.fea` | `kotoba.fea/src` | `kotoba.fea`, `kotoba.fea.boundary`, `kotoba.fea.convergence`, `kotoba.fea.fatigue` (Kotoba project library) |
| `kotoba.fare` | `kotoba.fare/src` | `kotoba.fare` (Kotoba project library) |
| `kotoba.expr` | `kotoba.expr/src` | `expr.core`, `kotoba.expr` (Kotoba project library) |
| `kotoba.examlaw` | `kotoba.examlaw/src` | `kotoba.examlaw` (Kotoba project library) |
| `kotoba.esim` | `kotoba.esim/src` | `kotoba.esim`, `kotoba.esim.export`, `kotoba.esim.lifecycle`, `kotoba.esim.ports` (Kotoba project library) |
| `kotoba.erc20` | `kotoba.erc20/src` | `erc20.core`, `erc20.permit` (Kotoba project library) |
| `kotoba.engineerRender` | `kotoba.engineerRender/src` | `engineer-render`, `engineer-render.color-map`, `engineer-render.draw-list`, `engineer-render.viewport` (Kotoba project library) |
| `kotoba.engineerIo` | `kotoba.engineerIo/src` | `engineer-io`, `engineer-io.format`, `engineer-io.gerber`, `engineer-io.step` (Kotoba project library) |
| `kotoba.engineer` | `kotoba.engineer/src` | `engineer`, `engineer.constraint`, `engineer.drc`, `engineer.grid` (Kotoba project library) |
| `kotoba.faceMatch` | `kotoba.faceMatch/src` | `face-match.core`, `face-match.model`, `face-match.ports` (Kotoba project library) |
| `kotoba.faceLiveness` | `kotoba.faceLiveness/src` | `face-liveness.core`, `face-liveness.datom`, `face-liveness.geometry`, `face-liveness.model` (Kotoba project library) |
| `kotoba.eduBerkeleySpice` | `kotoba.eduBerkeleySpice/src` | `spice`, `spice.analysis`, `spice.circuit`, `spice.model` (Kotoba project library) |
| `kotoba.editor` | `kotoba.editor/src` | `editor.core` (Kotoba project library) |
| `kotoba.phone` | `kotoba.phone/src` | `kotoba.phone`, `kotoba.phone.export`, `kotoba.phone.lifecycle`, `kotoba.phone.numbering` (Kotoba project library) |
| `kotoba.wire` | `kotoba.wire/src` | `kotoba.wire.edn`, `kotoba.wire.framing`, `kotoba.wire.tcp` (Kotoba project library) |
| `kotoba.techIpfsSpecsIpns` | `kotoba.techIpfsSpecsIpns/src` | `ipns.core`, `ipns.head`, `ipns.pubsub`, `ipns.record` (Kotoba project library) |
| `kotoba.ioLibp2pSpecsTransport` | `kotoba.ioLibp2pSpecsTransport/src` | `libp2p.multistream`, `libp2p.provider.node`, `libp2p.provider.node-muxed`, `libp2p.yamux` (Kotoba project library) |
| `kotoba.ioLibp2pSpecsKadDht` | `kotoba.ioLibp2pSpecsKadDht/src` | `kad.key`, `kad.lookup`, `kad.message`, `kad.routing` (Kotoba project library) |
| `kotoba.drawingml` | `kotoba.drawingml/src` | `drawingml.core`, `drawingml.parse` (Kotoba project library) |
| `kotoba.dot` | `kotoba.dot/src` | `dot.dot`, `dot.emit`, `dot.model`, `dot.validate` (Kotoba project library) |
| `kotoba.ooxml` | `kotoba.ooxml/src` | `ooxml.core` (Kotoba project library) |
| `kotoba.dns` | `kotoba.dns/src` | `kotoba-lang.dns.desktop`, `kotoba-lang.dns.state`, `kotoba-lang.dns.ui` (Kotoba project library) |
| `kotoba.dft` | `kotoba.dft/src` | `dft`, `dft.atpg`, `dft.bist`, `dft.jtag` (Kotoba project library) |
| `kotoba.devtools` | `kotoba.devtools/src` | `devtools`, `devtools.inspect` (Kotoba project library) |
| `kotoba.device` | `kotoba.device/src` | `kotoba.device`, `kotoba.device.call`, `kotoba.device.denied`, `kotoba.device.describe` (Kotoba project library) |
| `kotoba.wit` | `kotoba.wit/src` | `kotoba.lang.wit`, `kotoba.wit`, `kotoba.wit.allows`, `kotoba.wit.capabilities` (Kotoba project library) |
| `kotoba.designQuality` | `kotoba.designQuality/src` | `design-quality.audit`, `design-quality.cli`, `design-quality.persona` (Kotoba project library) |
| `kotoba.shamir` | `kotoba.shamir/src` | `shamir.core` (Kotoba project library) |
| `kotoba.denchu` | `kotoba.denchu/src` | `denchu.area`, `denchu.datoms`, `denchu.enrich`, `denchu.facts` (Kotoba project library) |
| `kotoba.okugai` | `kotoba.okugai/src` | `okugai.datoms`, `okugai.facts`, `okugai.medium`, `okugai.operator` (Kotoba project library) |
| `kotoba.dec` | `kotoba.dec/src` | `dec` (Kotoba project library) |
| `kotoba.ddl` | `kotoba.ddl/src` | `ddl.ddl`, `ddl.execute`, `ddl.model`, `ddl.validate` (Kotoba project library) |
| `kotoba.datomModel` | `kotoba.datomModel/src` | `datom-model.core`, `datom-model.statistics` (Kotoba project library) |
| `kotoba.datom` | `kotoba.datom/src` | `datom.core` (Kotoba project library) |
| `kotoba.daichou` | `kotoba.daichou/src` | `daichou.canonical`, `daichou.chain`, `daichou.hash`, `daichou.receipt` (Kotoba project library) |
| `kotoba.d3` | `kotoba.d3/src` | `kotoba.lang.d3.scale`, `kotoba.lang.d3.shape` (Kotoba project library) |
| `kotoba.search` | `kotoba.search/src` | `search.model`, `search.origin`, `search.postings`, `search.validate` (Kotoba project library) |
| `kotoba.robotics` | `kotoba.robotics/src` | `kotoba.robotics`, `kotoba.robotics.export`, `kotoba.robotics.process`, `kotoba.robotics.process.fluid` (Kotoba project library) |
| `kotoba.kudaki` | `kotoba.kudaki/src` | `kudaki.contact`, `kudaki.demo`, `kudaki.element`, `kudaki.integrate` (Kotoba project library) |
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

Official path and oracles: see [ORACLE.md](ORACLE.md).
