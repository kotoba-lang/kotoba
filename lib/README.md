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
