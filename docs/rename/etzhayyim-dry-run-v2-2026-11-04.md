# etzhayyim rename: dry-run report (read-only)

Scanned 4789 repositories (skipped 3); 71654 tracked text files contain the word. Source: `git grep` on each repository's local HEAD, so repositories whose checkout is behind their remote are counted at the older commit.

| rule | kind | status | tokens | distinct | repos |
|---|---|---|---:|---:|---:|
| did-web-entity | DID used as an entity identifier (did:web:etzhayyim.com:actor:..., :gov:...) | decide | 126494 | 33594 | 1465 |
| vanity-url | service URL on etzhayyim.com | apply | 98407 | 24018 | 619 |
| word | bare word (prose) | apply | 57920 | 4 | 916 |
| urn | URN identifier (urn:etzhayyim:...) | decide | 43867 | 2130 | 15 |
| nsid-generic | lexicon NSID (other) | apply | 38690 | 12394 | 610 |
| did-web-service | DID of a service (did:web:<host>) | mint | 23999 | 19234 | 600 |
| name-prefix | name etzhayyim-* | decide | 12869 | 5493 | 498 |
| unclassified | NOT CLAIMED BY ANY RULE | decide | 11740 | 5254 | 685 |
| nsid-apps | lexicon NSID (apps) | apply | 9116 | 550 | 8 |
| purl | package URL (pkg:etzhayyim/...) | apply | 8216 | 1031 | 1028 |
| wit | WIT package | apply | 7619 | 686 | 230 |
| host | bare host name | decide | 7570 | 885 | 670 |
| repo-path | repository path / URL | lookup | 6685 | 1778 | 1679 |
| npm-scope | npm scope | apply | 5016 | 439 | 356 |
| dotted-id | dotted id (etzhayyim.x/v1) | decide | 3557 | 503 | 502 |
| partial-host | host fragment (.etzhayyim.com, @x.etzhayyim.com, ...) | decide | 2848 | 709 | 374 |
| http-header | wire header (x-etzhayyim-*) | decide | 2716 | 29 | 1211 |
| name-com-prefix | name com-etzhayyim-* | apply | 2579 | 678 | 572 |
| other-domain | other etzhayyim domain (.co.jp, .ai, dnsaddr) | decide | 1772 | 379 | 153 |
| nsid-kotoba | lexicon NSID (kotoba) | apply | 1554 | 241 | 51 |
| code-symbol | code symbol (MockEtzhayyim, EtzhayyimConfig, ...) | apply | 1329 | 69 | 258 |
| jsonld-context | JSON-LD context / namespace URL | apply | 1325 | 21 | 417 |
| name-suffix | name *-etzhayyim (dns-etzhayyim, did-etzhayyim) | decide | 645 | 20 | 25 |
| env-var | environment variable / secret name | decide | 449 | 93 | 52 |
| did-method | DID (did:etzhayyim method) | decide | 160 | 23 | 11 |

Lexicon ids defined in the scanned repositories: 822; ids defined in more than one organisation: 0.

## Lexicon NSID tokens by owner (who defines the lexicon)

- nsid-generic: kotoba-lang (guess: using repo): 16212, cloud-itonami (guess: using repo): 15139, cloud-itonami: 4913, network-awai (guess: using repo): 1604, network-awai: 503, kotoba-lang: 319
- nsid-apps: kotoba-lang (guess: using repo): 9116
- nsid-kotoba: kotoba-lang: 1215, kotoba-lang (guess: using repo): 302, network-awai (guess: using repo): 23, cloud-itonami (guess: using repo): 14

## Examples (token → preview of the rewritten token)

### did-web-entity (decide)
- `did:web:gov-jpn.etzhayyim.com:law:local-autonomy-act` ×73
- `did:web:gov-usa.etzhayyim.com:law:state-municipal-charter` ×52
- `did:web:etzhayyim.com:member:abel` ×51
- `did:web:etzhayyim.com:hikari` ×35
- `did:web:etzhayyim.com:actor:` ×34
- `did:web:etzhayyim.com:member:seth` ×31

### vanity-url (apply) — blocked by: New names need DNS and certificates before the cut-over; redirects from the old names are optional.
- `https://news.etzhayyim.com` ×43650 → `https://news.kotoba-lang.org`
- `https://yabai.etzhayyim.com/ontology/context.jsonld` ×1425 → `https://yabai.kotoba-lang.org/ontology/context.jsonld`
- `https://etzhayyim.com` ×578 → `https://kotoba-lang.org`
- `https://pds.etzhayyim.com` ×496 → `https://pds.kotoba-lang.org`
- `https://news.etzhayyim.com/en/articles/gow-ragnarok-guide-hub-2026` ×362 → `https://news.kotoba-lang.org/en/articles/gow-ragnarok-guide-hub-2026`
- `https://news.etzhayyim.com/ja/articles/fo76-beginner-guide-hub-2026` ×308 → `https://news.kotoba-lang.org/ja/articles/fo76-beginner-guide-hub-2026`

### word (apply)
- `Etzhayyim` ×49618
- `etzhayyim` ×7833
- `ETZHAYYIM` ×435
- `:etzhayyim` ×34

### urn (decide)
- `urn:etzhayyim:news:chainsaw-man-series-essay-07-2026` ×40
- `urn:etzhayyim:news:chainsaw-man-series-essay-08-2026` ×40
- `urn:etzhayyim:news:chainsaw-man-series-essay-09-2026` ×40
- `urn:etzhayyim:news:chainsaw-man-series-essay-10-2026` ×40
- `urn:etzhayyim:news:chainsaw-man-series-essay-11-2026` ×40
- `urn:etzhayyim:news:chainsaw-man-series-essay-12-2026` ×40

### nsid-generic (apply)
- `com.etzhayyim.apps.kouhou.publicBriefing` ×1064 → `network.awai.apps.kouhou.publicBriefing`
- `https://mcp.etzhayyim.com/xrpc/com.etzhayyim.mcp.message` ×530 → `https://mcp.etzhayyim.com/xrpc/org.kotoba-lang.mcp.message`
- `com.etzhayyim.toritsugi.procedure` ×322 → `network.awai.toritsugi.procedure`
- `com.etzhayyim.encrypted.` ×263 → `org.kotoba-lang.encrypted.`
- `com.etzhayyim.apps.site.wat` ×217 → `org.kotoba-lang.apps.site.wat`
- `com.etzhayyim.apps.site.wet` ×215 → `org.kotoba-lang.apps.site.wet`

### did-web-service (mint)
- `did:web:etzhayyim.com` ×748
- `did:web:cofog.etzhayyim.com` ×609
- `did:web:maps.etzhayyim.com` ×140
- `did:web:site.etzhayyim.com:` ×80
- `did:web:akashi.etzhayyim.com` ×80
- `did:web:kyber.etzhayyim.com` ×70

### name-prefix (decide)
- `etzhayyim-gov-general` ×1301
- `etzhayyim-gov-district` ×811
- `etzhayyim-sdk` ×417
- `etzhayyim-gov-economic` ×238
- `etzhayyim-gov-public-order` ×233
- `:etzhayyim-adherent-loop` ×189

### unclassified (decide)
- `etzhayyim.` ×203
- `.etzhayyim` ×83
- `com.etzhayyim.` ×53
- `etzhayyim:` ×52
- `https://github.com/kotoba-lang/did-etzhayyim` ×51
- `com-etzhayyim-` ×44

### nsid-apps (apply)
- `app.etzhayyim.apps.cofog.govFunction` ×1212 → `org.kotoba-lang.apps.cofog.govFunction`
- `app.etzhayyim.apps.cofog.budgetItem` ×1212 → `org.kotoba-lang.apps.cofog.budgetItem`
- `app.etzhayyim.apps.cofog.program` ×1212 → `org.kotoba-lang.apps.cofog.program`
- `app.etzhayyim.apps.cofog.policyUpdate` ×1212 → `org.kotoba-lang.apps.cofog.policyUpdate`
- `app.etzhayyim.apps.kyber_qzzg06nh.kyber_qzzg06nh_entity` ×84 → `org.kotoba-lang.apps.kyber_qzzg06nh.kyber_qzzg06nh_entity`
- `app.etzhayyim.apps.kyber_qzzg06nh.kyber_qzzg06nh_event` ×84 → `org.kotoba-lang.apps.kyber_qzzg06nh.kyber_qzzg06nh_event`

### purl (apply) — blocked by: Rename together with the packages.
- `pkg:etzhayyim/kotoba` ×2054 → `pkg:@kotoba-lang/kotoba`
- `pkg:etzhayyim/kotodama-wasm` ×2002 → `pkg:@kotoba-lang/kotodama-wasm`
- `pkg:etzhayyim/datomic-client` ×2002 → `pkg:@kotoba-lang/datomic-client`
- `pkg:etzhayyim/kotodama-clj` ×52 → `pkg:@kotoba-lang/kotodama-clj`
- `pkg:etzhayyim/datomic-eavt` ×52 → `pkg:@kotoba-lang/datomic-eavt`
- `pkg:etzhayyim/unity_ads-compat` ×4 → `pkg:@kotoba-lang/unity_ads-compat`

### wit (apply)
- `etzhayyim:progress` ×495 → `kotoba:progress`
- `etzhayyim:mcpEndpoint` ×492 → `kotoba:mcpEndpoint`
- `etzhayyim:activities` ×492 → `kotoba:activities`
- `etzhayyim:nanoid` ×492 → `kotoba:nanoid`
- `etzhayyim:LegacyActorComponent` ×491 → `kotoba:LegacyActorComponent`
- `etzhayyim:componentType` ×491 → `kotoba:componentType`

### host (decide)
- `etzhayyim.com` ×1580
- `mcp.etzhayyim.com` ×439
- `dispatcher.etzhayyim.com` ×294
- `site.etzhayyim.com` ×198
- `maps.etzhayyim.com` ×188
- `legal-entity.etzhayyim.com` ×159

### repo-path (lookup)
- `etzhayyim/root` ×1888
- `git+https://github.com/etzhayyim/com-etzhayyim-sdk.git` ×254
- `etzhayyim/global-legislation-datoms.` ×223
- `git+https://github.com/etzhayyim/com-etzhayyim-sdk-mock.git` ×199
- `etzhayyim/kotoba` ×62
- `etzhayyim/root:20-actors/kami-engine-sdk/.` ×54

### npm-scope (apply) — blocked by: The target scope must exist and be owned. For network-awai / cloud-itonami no scope is decided yet: those tokens stay decide.
- `@etzhayyim/sdk` ×1530 → `@kotoba-lang/sdk`
- `@etzhayyim/sdk-mock` ×652 → `@kotoba-lang/sdk-mock`
- `@etzhayyim/kotodama-host-sdk` ×568 → `@kotoba-lang/kotodama-host-sdk`
- `@etzhayyim/design-system` ×134 → `@kotoba-lang/design-system`
- `@etzhayyim/sdk.` ×117 → `@kotoba-lang/sdk.`
- `@etzhayyim/etzhayyim-hrse` ×77 → `@kotoba-lang/etzhayyim-hrse`

### dotted-id (decide)
- `etzhayyim.repository/v1` ×421
- `etzhayyim.migration/v1` ×329
- `etzhayyim.json` ×232
- `etzhayyim.migration/extracted-v1` ×66
- `etzhayyim.repository/readme-v1` ×61
- `etzhayyim.migration/repository-v1` ×54

### partial-host (decide)
- `world/domain/etzhayyim.com` ×381
- `.etzhayyim.com` ×207
- `.etzhayyim.com/api/grpc` ×120
- `:etzhayyim.com` ×91
- `mangaka.etzhayyim.com.` ×63
- `@jinushi.etzhayyim.com` ×50

### http-header (decide)
- `x-etzhayyim-did` ×2052
- `x-etzhayyim-bff` ×281
- `x-etzhayyim-xrpc-method` ×219
- `X-etzhayyim-USER-ID` ×24
- `x-etzhayyim-actor-did` ×21
- `x-etzhayyim-org-id` ×17

### name-com-prefix (apply)
- `com-etzhayyim-ooyake` ×1237 → `ooyake`
- `com-etzhayyim-toritsugi` ×146 → `toritsugi`
- `com-etzhayyim-open-seiyaku` ×61 → `open-seiyaku`
- `com-etzhayyim-apps-standard-shinkaEvolution` ×46 → `apps-standard-shinkaEvolution`
- `com-etzhayyim-apps-standard-shinkaKnowledge` ×45 → `apps-standard-shinkaKnowledge`
- `com-etzhayyim-tomoshibi` ×16 → `tomoshibi`

### other-domain (decide)
- `etzhayyim.co.jp` ×324
- `https://etzhayyim.ai/bpmn/maps` ×238
- `/dnsaddr/etzhayyim.com/p2p/12D3KooWGRnHP5hHAxSnPQE5gopDqAzWkZ2NAFi2ZZ6o85FnAiEc` ×176
- `etzhayyim.ai` ×109
- `etzhayyimcojp` ×86
- `etzhayyimcojp/20-actors` ×60

### nsid-kotoba (apply)
- `/xrpc/com.etzhayyim.apps.kotoba.datomic.q` ×114 → `/xrpc/org.kotoba-lang.datomic.q`
- `/xrpc/com.etzhayyim.apps.kotoba.datomic.transact` ×63 → `/xrpc/org.kotoba-lang.datomic.transact`
- `com.etzhayyim.apps.kotoba.datomic.transact` ×47 → `org.kotoba-lang.datomic.transact`
- `/xrpc/com.etzhayyim.apps.kotoba.graph.sparql` ×44 → `/xrpc/org.kotoba-lang.graph.sparql`
- `com.etzhayyim.apps.kotoba.datomic.q` ×37 → `org.kotoba-lang.datomic.q`
- `/xrpc/com.etzhayyim.apps.kotoba.block.get` ×28 → `/xrpc/org.kotoba-lang.block.get`

### code-symbol (apply)
- `MockEtzhayyim` ×732
- `netzhayyim` ×140
- `createAuthedEtzhayyim` ×66
- `etzhayyimUIKit` ×57
- `EtzhayyimConfig` ×51
- `EtzhayyimWasmComponent` ×36

### jsonld-context (apply) — blocked by: The new URL must answer before the cut-over; the old one need not be served.
- `https://etzhayyim.com/ns/kotodama/v1` ×781 → `https://kotoba-lang.org/ns/kotodama/v1`
- `https://ghosthacker.etzhayyim.com/ns/` ×284 → `https://kotoba-lang.org/ns/`
- `https://etzhayyim.com/ns/actor/v1` ×81 → `https://kotoba-lang.org/ns/actor/v1`
- `https://etzhayyim.com/ns/actor-manifest` ×69 → `https://kotoba-lang.org/ns/actor-manifest`
- `https://etzhayyim.com/ns/actor` ×20 → `https://kotoba-lang.org/ns/actor`
- `https://etzhayyim.com/ns/kabuto/bpmn` ×20 → `https://kotoba-lang.org/ns/kabuto/bpmn`

### name-suffix (decide)
- `dns-etzhayyim` ×508
- `did-etzhayyim` ×61
- `org-etzhayyim` ×16
- `com-etzhayyim` ×11
- `comfyui-etzhayyim` ×8
- `alice-in-etzhayyim` ×8

### env-var (decide)
- `etzhayyim_TOKEN` ×58
- `etzhayyim_sdk` ×31
- `ETZHAYYIM_LLM_URL` ×26
- `ETZHAYYIM_SUBSTRATE_MODE` ×26
- `ETZHAYYIM_MST_PROJECTOR_URL` ×20
- `ETZHAYYIM_PDS_URL` ×15

### did-method (decide)
- `did:etzhayyim:` ×64
- `did:etzhayyim` ×55
- `did:etzhayyim.` ×8
- `did:etzhayyim/did:web` ×8
- `did:etzhayyim:abc` ×3
- `did:etzhayyim:bafkrei...site` ×2

## Repositories with the most tokens

- cloud-itonami/app-itonami-news: 89380
- cloud-itonami/app-news: 89380
- kotoba-lang/kotoba: 44255
- cloud-itonami/actor-ibuki: 36747
- kotoba-lang/kotodama-py: 24840
- kotoba-lang/kototama: 18392
- cloud-itonami/unspsc: 18367
- cloud-itonami/states: 9628
- cloud-itonami/itonami-registry: 9229
- kotoba-lang/ooyake: 7360
- kotoba-lang/lexicons-bundle: 7209
- cloud-itonami/org-un-isic: 5781
- kotoba-lang/kami-web: 5068
- cloud-itonami/yabai: 4082
- cloud-itonami/cofog: 3474
- cloud-itonami/app-itonami-maps: 1973
- cloud-itonami/app-maps: 1973
- kotoba-lang/kotoba-server: 1755
- kotoba-lang/kotodama-host: 1480
- network-awai/app-coverage: 1353
- network-awai/app-aozora: 1331
- kotoba-lang/distill: 1242
- network-awai/app-hyakka: 1235
- cloud-itonami/actor-ake: 1215
- kotoba-lang/kotoba-lang: 1213

## Unclaimed tokens (the map has a gap here)

- `etzhayyim.` ×203
- `.etzhayyim` ×83
- `com.etzhayyim.` ×53
- `etzhayyim:` ×52
- `https://github.com/kotoba-lang/did-etzhayyim` ×51
- `com-etzhayyim-` ×44
- `etzhayyim/` ×41
- `/x/etzhayyim/xrpc/1.0` ×39
- `border-etzhayyim-border` ×36
- `com.etzhayyim/social-publication` ×35
- `https://github.com/kotoba-lang/com-etzhayyim-open-seiyaku` ×34
- `50-infra/etzhayyim-tithe-router` ×34
- `orgs/etzhayyim/root` ×31
- `@etzhayyim` ×29
- `etzhayyim_organism.sensors.charter_rider.scan` ×29
- `aml.adapters.etzhayyim` ×28
- `/90-docs/adr/2605215000-etzhayyim-inference-murakumo-only-no-runpod.md` ×28
- `_etzhayyim_substrate` ×28
- `ETZHAYYIM_SUBSTRATE_MODE.` ×26
- `application/vnd.etzhayyim.card.rfp` ×26
- `@etzhayyim/` ×24
- `/90-docs/adr/2605192200-etzhayyim-ip-free-release-charter-rider.md` ×24
- `/90-docs/adr/2605192100-etzhayyim-mission-charter.md` ×24
- `jun@etzhayyim.group` ×23
- `_etzhayyim` ×23
- `_etzhayyim_substrate.py` ×23
- `/Users/junkawasaki/etzhayyim/etzhayyim-root/60-apps/etzhayyim-project-mangaka/data/ghosthacker` ×22
- `60-apps/etzhayyim-project-open-ot/SPEC.md` ×22
- `lib/kotoba.comEtzhayyimOpenSeiyaku` ×20
- `file_etzhayyim_maps_v1_maps` ×20
- `file_etzhayyim_maps_v1_maps_ui` ×20
- `ETZHAYYIM_SUBSTRATE_MODE=rw` ×20
- `com.etzhayyim/kotoba-datom` ×19
- `../../../90-docs/adr/2605172000-etzhayyim-kotoba-substrate.md` ×19
- `text-etzhayyim-muted` ×19
- `ghcr.io/etzhayyim/` ×19
- `ctf.adapters.etzhayyim` ×18
- `world/organization/etzhayyim-5f367aed` ×18
- `did:erc725:etzhayyim:260425:etzhayyim-japan` ×18
- `ETZHAYYIM_SUBSTRATE_MODE=mst` ×18
- `org.etzhayyim.xproject.assessment.result` ×18
- `voiceOf=etzhayyim` ×17
- `https://github.com/kotoba-lang/kotoba/tree/main/lib/kotoba.comEtzhayyimOpenSeiyaku` ×17
- `50-infra/etzhayyim-did-web/src/registry/infra-actors.ts` ×17
- `etzhayyim_TOKEN=` ×17
- `/90-docs/adr/2605192245-etzhayyim-global-land-sovereignty.md` ×17
- `../../etzhayyim-project-open-isco/kotoba/` ×16
- `node_modules/@etzhayyim/sdk-mock` ×16
- `60-apps/etzhayyim-project-demining/AGENTS.md.` ×14
- `etzhayyim_MM_768_SPACE_ID` ×14
- `text-etzhayyim-text` ×14
- `ghcr.io/etzhayyim/maps-bulk-ingest:1.2.0` ×14
- `ETZHAYYIM_SUBSTRATE_MODE=kotoba` ×14
- `orgs/etzhayyim/com-etzhayyim-tsukuru` ×14
- `/Users/junkawasaki/etzhayyim/etzhayyim-apps-etzhayyim/40-engine/kotoba/crates/kotoba-kotodama/sdk/kotodama-host-sdk/src/index.ts` ×13
- `/orgs/etzhayyim/com-etzhayyim-wadachi/README.md` ×13
- `00-contracts/lexicons/com/etzhayyim/iso20022/` ×12
- `jp.etzhayyim.med.uhl.institution.matchQuery` ×12
- `appview/etzhayyim-wasm-yotei-unyrsfan/cljs/public/js/cljs-runtime/module` ×12
- `path+file:///Users/junkawasaki/github/etzhayyim-root/packages/engine/kami-engine/kami-input` ×12
