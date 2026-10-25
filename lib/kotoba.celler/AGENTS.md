# Celler — DID-Addressed Encrypted Telephony over Starlink Mesh

Design: `docs/260327-celler-did-telephony-starlink-mesh-design.edn`

## Provenance, and why 30 `etzhayyim` strings are still here on purpose

This repository lives at **`kotoba-lang/celler`** and its identity is
**`celler.kotoba-lang.org`** / `did:web:celler.kotoba-lang.org`. The identity was
rewritten from `celler.etzhayyim.com` on 2026-08-30 (owner instruction), together
with the lexicon namespace (`com.etzhayyim.apps.celler.*` →
`org.kotoba-lang.apps.celler.*`) and the npm package name (`@etzhayyim/celler-kotoba`
→ `@kotoba-lang/celler`). Neither host has ever resolved, so nothing was live to
break.

What was deliberately **not** rewritten, because it is etzhayyim's and not
celler's — renaming it would have pointed the repo at things that do not exist:

| kept | why |
|---|---|
| `@etzhayyim/sdk`, `@etzhayyim/sdk-mock` | real git dependencies on `github.com/etzhayyim/com-etzhayyim-sdk{,-mock}` |
| `https://etzhayyim.com/ns/kotodama/v1` | the JSON-LD `@context`, defined by etzhayyim |
| `did:web:etzhayyim.com`, `did:web:alice.*` | the platform DID and user-fixture DIDs, not this service's |
| `llm.etzhayyim.com` / `com.etzhayyim.apps.llm.verify_celler_ai` | an etzhayyim service this one calls |
| `com.etzhayyim.rtc.*`, `com.etzhayyim.signal.*` | NSIDs owned and defined elsewhere, reused here |
| `NOTICE` (Apache-2.0 + Charter Rider v3.1) | a licence obligation, not a name |
| `migration.edn` | the historical record of the `etzhayyim/root` split. Its `:destination` names the repo as it was then; the repo has since moved here. The record is left intact rather than backdated |
| `README.edn` `:schema "etzhayyim.repository/v1"` | a workspace-wide metadata schema — repos across gftdcojp and others declare it too |
| `appview/etzhayyim-wasm-celler-oilt0wta/` | a build artifact directory (it holds an 8.4 MB compiled Mach-O) emitted by `etzhayyim deploy`. Renaming it by hand would desync the artifact from its builder |

Two things this repository is out of step with, recorded rather than silently
carried: it is **TypeScript**, where the workspace rule is portable `.cljc`
(ADR-2608201300 and the runtime-priority rule), and it commits an **8.4 MB
binary** into git history, where the rule is DataLad + B2 (skill
`large-binary-datalad`). Neither was in scope for the identity rewrite.

## Runtime

| key | value |
|---|---|
| domain | celler.kotoba-lang.org |
| nanoid | oilt0wta |
| performerType | service |
| DID | `did:web:celler.kotoba-lang.org` |
| Language | TypeScript (TS Native) |
| Build | `etzhayyim deploy` |
| UI mode | iframe |
| Architecture | Reactive Pipeline (Design E) |
| Data store | yata (SQL) via PDS |

## What This Is

Starlink backhaul + WiFi Direct mesh + Telnyx SIP trunk による自前電話網。従来キャリア不要。

- **Identity**: DID (primary) + E.164 番号 (PSTN bridge)
- **Transport**: WiFi Direct mesh (local) + Starlink/eSIM (WAN)
- **Voice**: WebRTC (Opus) + Signal Protocol E2E
- **Numbers**: Telnyx API で全世界 70+ 国の番号を自動プロビジョニング
- **Data**: Telnyx Wireless eSIM (180+ 国 LTE/5G)
- **AI**: Murakumo real-time translation, voicemail-to-text, spam detection

## Provider: Telnyx 一本化

Telnyx 単一 API で eSIM + SIP trunk + 番号プロビジョニング + WebRTC gateway を統合。

```
[PSTN] ←SIP→ [Telnyx] ←WebRTC→ [FreeSWITCH on CF Container] ←WebRTC→ [Device]
                 │
          eSIM provisioning
                 │
              [Device data connectivity: 180+ 国 LTE/5G]
```

## Network Stack

### Layer 0: Discovery
- **BLE Beacon**: DID hash (8 bytes)、2s active / 8s passive
- **WiFi Aware (NAN)**: Android 8+ サービス発見
- **mDNS**: `_etzhayyim-celler._tcp.local.` (同一 LAN)

### Layer 1: Transport
- **Local**: WiFi Direct (50-250 Mbps, ~70m)
- **WAN**: Starlink (25-60ms) / Telnyx eSIM (180国)
- **NAT traversal**: STUN + TURN (Cloudflare Container)

### Layer 2: Mesh Routing
- B.A.T.M.A.N. 簡易版 (application-layer)
- `Map<DID, NextHopDID, HopCount, RTT, LastSeen>`
- Max 5 hops (音声品質は 3 hops まで)

### Layer 3: Voice/Video
- Codec: Opus 24kHz 16kbps VBR / 8kHz 6kbps (mesh)
- Video: VP9 (preferred), H.264 (fallback)
- Transport: WebRTC (SRTP/DTLS)
- E2E: Signal Protocol (X3DH + Double Ratchet) + insertable streams

### Layer 4: Telephony
- DID → E.164 binding (yata graph)
- SIP ↔ WebRTC gateway (FreeSWITCH on CF Container)
- Telnyx SIP trunk → PSTN interconnect
- Call routing: mesh direct → LAN → Starlink P2P → TURN → **Local Breakout** → PSTN international

### Layer 4.5: Smart Routing — Local Breakout Cost Optimization

**国際通話を各国のローカル SIP trunk 経由で接続し、国際通話料を 80-95% 削減する。**

```
[発信者 JP]
    │ 国内通話 (050-XXXX, ~$0.02/min)
    ▼
[Telnyx JP SIP Trunk]
    │ Telnyx 内部 IP 転送 (無料)
    ▼
[Telnyx US SIP Trunk]
    │ 国内通話 (+1-XXX, ~$0.01/min)
    ▼
[着信者 US]
```

**Total: $0.03/min vs $0.15/min (国際直通) = 80% savings**

#### Routing Priority (拡張)

```
1. mesh direct    → WebRTC P2P (無料、同一 mesh 内)
2. LAN            → WiFi Direct (無料、近距離)
3. Starlink P2P   → STUN 直接 (無料、Starlink 間)
4. TURN           → relay (低コスト)
5. Local Breakout → 両国ローカル SIP → Telnyx 内部転送 (国内料金のみ)
6. PSTN intl      → Telnyx 国際通話 (最終手段)
```

#### 対応国 (12 リージョン)

| 国 | ローカル料金/分 | 国際料金/分 | 削減率 |
|---|---|---|---|
| JP | $0.020 | $0.15 | 87% |
| US/CA | $0.010 | $0.15 | 93% |
| GB | $0.015 | $0.15 | 90% |
| DE | $0.020 | $0.15 | 87% |
| FR | $0.020 | $0.15 | 87% |
| AU | $0.020 | $0.15 | 87% |
| KR | $0.020 | $0.15 | 87% |
| CN | $0.015 | $0.15 | 90% |
| IN | $0.008 | $0.15 | 95% |
| BR | $0.025 | $0.15 | 83% |
| SG | $0.015 | $0.15 | 90% |

#### Telnyx 機能活用

- **Multi-Region SIP Trunking**: 各国にリージョナル SIP endpoint
- **SIP-to-SIP 内部転送**: 同一 Telnyx アカウント内は無料
- **Call Control API**: プログラマティックに通話をブリッジ
- **Number Provisioning**: 70+ 国で VoIP 番号自動取得

## 国別番号体系

| 国 | VoIP 番号 | 取得方法 |
|---|---|---|
| 🇯🇵 JP | 050-XXXX-XXXX | Telnyx API (届出必要) |
| 🇺🇸 US | +1-XXX-XXX-XXXX (VoIP/local 区別なし) | Telnyx API (即日) |
| 🇬🇧 UK | +44-56-XXXX (VoIP) | Telnyx API |
| 🇩🇪 DE | +49-32-XXXX (VoIP) | Telnyx API (KYC) |
| 🇫🇷 FR | +33-09-XXXX (VoIP) | Telnyx API (KYC) |
| 🇦🇺 AU | +61-0550-XXXX (VoIP) | Telnyx API |

## Entity Model (SQL)

### Nodes

```
:Device       { device_id, did, device_type, os, ble_uuid, wifi_direct_mac, battery_pct, lat, lon }
:Gateway      { gateway_id, did, starlink_dish_id, uplink_mbps, downlink_mbps, latency_ms, status }
:Cell         { cell_id, did, name, center_lat, center_lon, radius_m, device_count, status }
:Call             { call_id, caller_did, callee_did, state, transport, codec, quality_mos, duration_ms, ai_session, language, trust_score, transcript_summary }
:Channel          { channel_id, did, name, max_participants, encryption }
:PhoneNumber      { e164, did, provider, sip_uri, status }
:ESimProfile      { iccid, phone_number, provider, coverage, data_remaining_mb, status }
:CallTranscript   { call_id, full_text, segments, language, duration_ms }
:CallRecording    { call_id, r2_key, duration_ms, size_bytes }
:AIResponsePolicy { did, mode, greeting, system_prompt, block_threshold }
:RegionalTrunk    { trunk_id, country_code, e164, sip_uri, rate_per_min_usd, status, connection_name, provisioned_at }
```

### Edges

```
(:Device)-[:MESH_LINK { rssi, throughput_mbps, latency_ms, hop_count }]->(:Device)
(:Device)-[:UPLINKS_TO]->(:Gateway)
(:Device)-[:MEMBER_OF]->(:Cell)
(:Device)-[:HAS_NUMBER]->(:PhoneNumber)
(:Device)-[:HAS_ESIM]->(:ESimProfile)
(:Gateway)-[:SERVES]->(:Cell)
(:Device)-[:PARTICIPATES_IN { role }]->(:Call)
(:Call)-[:ROUTES_THROUGH]->(:Gateway)
(:Call)-[:HAS_TRANSCRIPT]->(:CallTranscript)
(:Call)-[:HAS_RECORDING]->(:CallRecording)
(:Device)-[:JOINED { role }]->(:Channel)
(:Device)-[:AI_POLICY]->(:AIResponsePolicy)
(:Call)-[:ROUTED_VIA]->(:RegionalTrunk)
(:RegionalTrunk)-[:SERVES_COUNTRY { country_code }]->(:PhoneNumber)
```

## NSID Namespace

`org.kotoba-lang.apps.celler.*`

| interface | key operations |
|---|---|
| call | initiate_call, answer_call, reject_call, hold_call, end_call |
| mesh | register_device, discover_peers, report_link, get_topology, find_route |
| gateway | register_gateway, report_metrics, list_gateways |
| phone_number | provision_number, release_number, bind_number_to_did, lookup |
| sip_gateway | handle_inbound_call, initiate_outbound_call |
| smart_routing | calculate_cheapest_route, list_regional_trunks, initiate_local_breakout_call, provision_regional_trunk, estimate_call_cost |
| voice_ai | transcribe_voicemail, classify_call, translate_stream, handle_inbound_ai, get_call_transcript, get_call_recording, set_ai_response_policy, get_ai_response_policy, list_ai_calls |
| esim | provision_esim, activate_esim, suspend_esim, get_esim_usage, get_esim_profile |

既存 NSID 再利用: `com.etzhayyim.rtc.*` (signaling), `com.etzhayyim.signal.*` (E2E), `chat.bsky.convo.*` (messaging)

## AI Inbound Call Handling

**着信を AI Agent が自動応答。** E.164 国番号から言語自動検出 → 10言語対応グリーティング → Workers AI STT (Whisper) → LLM 応答生成 → TTS → 録音 + 文字起こし + owner 通知。

### Flow

```
PSTN着信 → Telnyx webhook → handleInboundAi
  → caller DID lookup (yata :PhoneNumber graph)
  → trust score check → spam: block (threshold configurable)
  → E.164 → language detect (ja/en/zh/ko/es/fr/de/pt/ar/hi)
  → AI policy check (always_ai / absent_only / unknown_only / off)
  → Workers AI Whisper (STT) → Murakumo LLM (応答, lang-aware) → TTS
  → finalizeCall → R2 録音 + transcript + LLM 要約 + owner 通知
```

### 10-Language Support

| Lang | E.164 prefix | Greeting |
|---|---|---|
| ja | +81 | はい、お電話ありがとうございます。ただいま不在にしております。 |
| en | +1, default | Hello, thank you for calling. I'm currently unavailable. |
| zh | +86 | 您好，感谢您的来电。我目前不在。 |
| ko | +82 | 안녕하세요, 전화 감사합니다. 현재 부재중입니다. |
| es | +34, +52, +54, +57 | Hola, gracias por llamar. No estoy disponible. |
| fr | +33 | Bonjour, merci de votre appel. Je suis indisponible. |
| de | +49 | Hallo, vielen Dank für Ihren Anruf. |
| pt | +55, +351 | Olá, obrigado por ligar. |
| ar | +966, +971, +20, +212 | مرحباً، شكراً لاتصالك. |
| hi | +91 | नमस्ते, कॉल करने के लिए धन्यवाद। |

### AI Response Policy (yoro SIM tab)

| mode | 動作 |
|---|---|
| `always_ai` | 全着信を AI が応答 |
| `absent_only` | owner 不在時のみ AI |
| `unknown_only` | 未知番号のみ AI |
| `off` | AI 応答なし |

### Verification

`llm.etzhayyim.com` の `verify_celler_ai` コマンドで 10言語 E2E テスト:

```bash
curl -X POST https://llm.etzhayyim.com/xrpc/com.etzhayyim.apps.llm.verify_celler_ai -d '{}'
```

## AI Agent Integration

| 機能 | Provider |
|---|---|
| Real-time translation | Workers AI gemma-3-12b (multilingual) |
| Voicemail-to-text | Workers AI @cf/openai/whisper-large-v3-turbo |
| Spam detection | DID trust score + LLM classifier |
| AI inbound response | Workers AI → LLM response → TTS → Telnyx playback |
| Call summarization | Workers AI llama-3.1-8b |
| Routing optimization | Traffic pattern prediction |
| Per-cell AI agent | Network health monitoring |

## Hardware

| 必須 | オプション |
|---|---|
| Starlink Dish + Router ($299-599) | GL.iNet travel router ($70) — mesh relay |
| Android スマホ (WiFi Direct 対応) | Raspberry Pi ($50-80) — dedicated mesh node |
| Telnyx account | iOS (WebRTC only、mesh 不可) |

## Regulatory

- **免許不要**: WiFi (ISM帯) + BLE (ISM帯) + Starlink (SpaceX licensed)
- **JP 050**: 電気通信事業届出 (登録ではなく届出、簡易)
- **JP 080**: MVNE 契約必要 (Phase 3)
- **Emergency**: native dialer にハンドオフ (SIM なし時は PSTN bridge + GPS)
- **Intercept**: Signal E2E のためサーバー側復号不可。metadata (CDR) は legal order で提出可能

## Phased Implementation

### Phase 1: MVP — WebRTC Calls + Telnyx (8 weeks)
- App + WIT + kotodama.jsonld
- Telnyx SIP trunk + 番号プロビジョニング API
- FreeSWITCH on CF Container (SIP ↔ WebRTC)
- Telnyx eSIM API 連携
- Signal Protocol E2E on signaling
- STUN/TURN (CF Container)
- Call UI (iframe)
- CDR → yata graph

### Phase 2: Local Mesh (8 weeks)
- Android native companion (WiFi Direct + BLE)
- BLE discovery → WiFi Direct negotiation
- Local signaling over WiFi Direct data channel
- Mesh routing (2-3 hops)
- Gateway registration + Cell formation

### Phase 3: Full Network + AI (8 weeks)
- Per-cell AI agent (Murakumo)
- Real-time translation
- Voicemail-to-text, spam detection
- PSTN bridge (Telnyx SIP)
- Multi-cell handoff
- 080 番号 (MVNE 契約)
- iOS companion (WebRTC only)

## Cost (1,000 users)

| 項目 | 月額 (国際直通) | 月額 (Local Breakout) |
|---|---|---|
| Telnyx 番号 1,000本 | ~$2,000 | ~$2,000 |
| Telnyx 通話 | ~$1,500 | **~$300** (80% 削減) |
| Telnyx eSIM 1,000枚 | ~$2,000 | ~$2,000 |
| Cloudflare (Calls + Container) | ~$700 | ~$700 |
| **合計** | **~$6,200/月** | **~$5,000/月 (~¥750/user)** |

**Local Breakout 通話コスト内訳**: 国際通話の 80% が Local Breakout 対象 → $0.03/min (JP↔US) vs $0.15/min = 年間 ~$14,400 削減

## Related Projects

| project | relationship |
|---|---|
| etzhayyim-project-phone | PSTN bridge (AWS Connect, legacy path) |
| etzhayyim-project-network-mobile | mesh infra sibling |
| etzhayyim-project-murakumo | AI inference (STT/TTS/translation) |
| etzhayyim-project-maps | mesh topology visualization |
| etzhayyim-project-trust | DID trust score for spam detection |

## Constraints

- **iOS**: WiFi Direct API 非公開 → mesh 不可、WebRTC only
- **Starlink CGNAT**: TURN 必須 (direct P2P は STUN で一部成功)
- **050 → 080 移行**: MVNE 契約 + 電気通信事業登録 (Phase 3)
- **eSIM**: Telnyx Wireless (180国) だが一部キャリアで制限あり
