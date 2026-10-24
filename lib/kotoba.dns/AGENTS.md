# etzhayyim-project-dns

## Identity

| key | value |
|---|---|
| nanoid | `scndu0rf` |
| domain | `dns.etzhayyim.com` |
| DID | `did:web:scndu0rf.etzhayyim.com` |
| performerType | `service` |
| runtime | Single Worker (TS Native) |
| uiType | `appview` (Hono + Svelte CSR) |
## Purpose

Cloudflare DNS/Registrar ベースのドメイン購入・登録・管理プラットフォーム。各 managed domain を path-based DID として自律 Actor 化し、DNS レコード変更・ドメインライフサイクルを W Protocol Event Stream で管理。iframe UI + MCP Agent Chat で操作。Squarespace からの移管は yorishiro-squarespace browser agent (cross-actor) 経由。

## Actor DID Architecture (Multi-DID)

### Primary DID

`did:web:scndu0rf.etzhayyim.com` — app 本体。zone 作成・ドメイン購入の orchestrator。

### Path-Based DID (1 domain = 1 DID)

各管理ドメインが独立 Actor として DID を持つ。ドメイン名の `.` → `_` 変換 (camelCase 必須)。

```
did:web:dns.etzhayyim.com:zone:{domain_slug}
```

**例:**
- `did:web:dns.etzhayyim.com:zone:example_com`
- `did:web:dns.etzhayyim.com:zone:etzhayyim_com`

**Zone DID の役割:**
- DNS レコード変更を Social Post (T1) で announce
- DNS health check 結果を自身の DID から投稿
- 他の Zone DID を Follow して DNS 依存関係を表現 (CNAME/MX 先)
- Invoke/Serve で外部 Agent からの DNS 操作を受付

### Registrar DID

`did:web:dns.etzhayyim.com:registrar:cloudflare` — Cloudflare Registrar 連携 Actor。

## iframe UI (SvelteKit SSR)

### Route Structure

| route | 画面 | 操作 |
|---|---|---|
| `/` | Zone 一覧 + Agent Chat FAB | zone list, navigate |
| `/zone/[domain]` | Zone 詳細 + DNS record 一覧 + DNSSEC/Health | record CRUD, health check |
| `/zone/[domain]/records` | DNS record 追加 (A/AAAA/CNAME/MX/TXT/SRV/CAA/NS) | record create |
| `/register` | ドメイン検索 + 購入 + Import zone | domain check/register, zone import |
| `/health` | 全 zone ヘルスダッシュボード (DNS/SSL/WHOIS) | health check |
| `/messages` | **MCP Agent Chat** — DNS Actor とメッセージで操作 | 全 command 実行 |

### UI Implementation

- Layout: 手書き header + 4-tab bottom nav (Zones, Register, Health, Agent)
- `max-w-[600px] mx-auto`, `text-[15px]`/`text-[13px]` 固定, dark theme
- accent: orange (`#f97316`)
- components: `HealthBadge`, `RecordRow`, `ZoneCard` (`$lib/dns/`)
- XRPC client: `$lib/dns/client.ts` → `atproto.etzhayyim.com/xrpc/{NSID}`
- MCP client: `$lib/dns/mcp.ts` → `mcp.etzhayyim.com/mcp` (JSON-RPC 2.0)

## MCP Integration

### Tool Discovery

```
POST mcp.etzhayyim.com/mcp
{ "jsonrpc": "2.0", "method": "tools/list", "params": { "did": "did:web:scndu0rf.etzhayyim.com" } }
```

`app.Command("", name, handler, AsAgentTool(...))` から自動 expose。

**Auth**: `tools/list` = public, `tools/call` = AT Protocol JWT (authn.etzhayyim.com) or internal token 必須。

### Agent Chat → MCP Flow

```
User message → resolveIntent() → tool name + args → mcp.etzhayyim.com/mcp tools/call
  → DISPATCHER → dns Worker handler → GovernanceGate → result → chat 表示
```

**自然言語例:**
- "Transfer example.com from Squarespace" → `dns.transfer_from_squarespace`
- "Register example.com" → `dns.domain_register`
- "Add A record for api.example.com pointing to 1.2.3.4" → `dns.record_create`
- "List records for example.com" → `dns.record_list`
- "Squarespace domains 一覧" → `squarespace.list_domains`

### 外部 Agent からの Invoke

```go
kotodama.Invoke("did:web:scndu0rf.etzhayyim.com", "record_create", `{"domain":"example.com","type":"A","name":"api","content":"1.2.3.4"}`)
kotodama.Invoke("did:web:scndu0rf.etzhayyim.com", "health_check", `{"domain":"example.com"}`)
```

## Squarespace → Cloudflare Transfer (yorishiro-squarespace cross-actor)

### Architecture

```
User → /messages "Transfer example.com from Squarespace"
  → dns.transfer_from_squarespace
  → dns Worker → Invoke(did:web:sqddf3sp.etzhayyim.com, "initiate_transfer_to_cloudflare")
  → yorishiro-squarespace Worker (browser automation)
    → Step 1: Disable auto-renew
    → Step 2: Unlock domain
    → Step 3: Get auth/EPP code
    → Step 4: Export DNS records → BIND zone file
    → Step 5: Invoke(did:web:scndu0rf.etzhayyim.com, "domain_transfer", {auth_code})
      → Cloudflare Registrar API transfer
  → Zone DID created + Social announce (T1) + transfer_event record (T2)
```

### Project Actor Composition (reactive, reference pattern)

1 transfer = 1 project convo。新規 Worker は作らず、既存 dns (`scndu0rf`) + yorishiro-squarespace (`sqddf3sp`) 2 Worker に path-based sub-actor DID を追加する。

```
Project: "domain-transfer: {domain}"  (convoId = transferRequest.rkey)
├── did:web:scndu0rf.etzhayyim.com:actor:cfRegistrar   (Cloudflare 受け入れ側、CF Registrar API 実行)
├── did:web:sqddf3sp.etzhayyim.com:actor:sqExporter    (Squarespace 送り出し側、browser automation)
├── did:web:scndu0rf.etzhayyim.com:zone:{domain_slug}  (成立時に自動生成)
└── did:web:{user}.etzhayyim.com                       (申請者)
```

**Actor DID registration** — 各 Worker 起動時に一度だけ:

```ts
// scndu0rf Worker
await sdk.did.create("actor:cfRegistrar", {
  displayName: "Cloudflare Registrar Receiver",
  description: "Accepts inbound domain transfers and drives CF Registrar API.",
});

// sqddf3sp Worker
await sdk.did.create("actor:sqExporter", {
  displayName: "Squarespace Exporter",
  description: "Browser-automation agent that releases a domain from Squarespace.",
});
```

**Reactive flow (Design E, Follow-based, no explicit cross-actor):**

```
① User → XRPC com.etzhayyim.dns.transferFromSquarespace {domain}
     → cfRegistrar が com.etzhayyim.dns.transferRequest record 作成 (ClassA 3 signers)
     → transferRequest.rkey = projectConvoId

② sqExporter は cfRegistrar を Follow → onCommit(transferRequest) 受信
     → browser automation を 5 step 実行
     → 各 step で com.etzhayyim.dns.transferStep emit
         - step 3 (authCode) は必ず signal:v1: 暗号化 (field-key は sqExporter DID 派生、AT Record 連携用のみ)
         - step 4 で BIND zone file を R2 blob に export
         - step 5 (cfTransfer) sqExporter が **自ら** Cloudflare Registrar API を call
           (cross-Worker E2E で authCode を渡すのは deriveFieldKey が per-DID のため不可能。
            plaintext authCode は sqExporter process memory のみに滞在)

③ sqExporter → com.etzhayyim.dns.transferOutcome emit (result=success|failure)
     → success: zoneId (CF API response) + computed zoneDid を記録
     → failure: failureReason を記録

④ cfRegistrar の onCommit(transferOutcome) →
     - success: zone DID create (`sdk.did.create("zone:{slug}")`) + com.etzhayyim.dns.ownershipTransfer record
     - T1 social announce は kotodama.jsonld derive rule で自動導出
     - failure: derive rule で失敗通知のみ (rollback は sqExporter が step 単位で re-lock 等を実行)
```

### New NSIDs (Design E Tier 2, camelCase)

| NSID | 役割 | 権威 lexicon |
|---|---|---|
| `com.etzhayyim.dns.transferRequest` | 申請レコード (domain, fromRegistrar, 3 signer approvals) | `00-contracts/lexicons/com/etzhayyim/apps/dns/transferRequest.json` |
| `com.etzhayyim.dns.transferStep` | 5 step 進捗 (disableAutoRenew/unlock/authCode/dnsExport/cfTransfer) | `00-contracts/lexicons/com/etzhayyim/apps/dns/transferStep.json` |
| `com.etzhayyim.dns.transferOutcome` | 成立/失敗 最終レコード → zone DID 生成 trigger | `00-contracts/lexicons/com/etzhayyim/apps/dns/transferOutcome.json` |

**Design E rule compliance:**
- 3 record とも Tier 2 `ComAtprotoRepoCreateRecord()` で書く。handler 内で `postFeed` / explicit Invoke は呼ばない
- Social announce (transfer 成立/失敗) は `kotodama.jsonld` の `derive` rule で PDS commit pipeline が自動導出
- `transferStep.authCodeEncrypted` は `signal:v1:{ciphertext}` prefix 必須 (EPP code を federable Repo record に平文で載せない)
- `subscribeRepos.collections[]` に 3 NSID を追加 (両 Worker の kotodama.jsonld)

### Governance

| axis | value |
|---|---|
| transferRequest | **ClassA** (3 signers, high) — 移管は不可逆性が高い |
| transferStep (authCode) | field-level encrypt (`signal:v1:`) |
| rollback | failure 時の `rollbackSteps[]` を順序固定で実行 (re-lock → re-enable auto-renew) |
| sensitivity | authCode = `restricted`、それ以外は `internal` |

既存 single-shot `transfer_from_squarespace` MCP command はそのまま残す。project 化経路は `/messages` チャット経由で起動し、進捗を convo に逐次通知する UX を提供する。

### yorishiro-squarespace Component

| key | value |
|---|---|
| nanoid | `sqddf3sp` |
| DID | `did:web:sqddf3sp.etzhayyim.com` |
| WIT | `kotodama:browser/automation@1.0.0` import |
| project | `etzhayyim-project-yorishiro` |
| deploy | account-level Worker |
| known limitation | WASM instantiate に `HEADLESS_BROWSER` binding 必要。Container mode で解消 |

### Squarespace Commands

| command | description | governance |
|---|---|---|
| `list_domains` | List all Squarespace domains | — |
| `get_domain_detail` | Domain detail (lock, auto-renew, expiry) | — |
| `unlock_domain` | Unlock domain for transfer | ClassB (2 signers) |
| `get_auth_code` | Get EPP/auth code | ClassB (2 signers) |
| `disable_auto_renew` | Disable auto-renewal | — |
| `initiate_transfer_to_cloudflare` | Full 5-step transfer workflow | **ClassA (3 signers, high)** |
| `list_dns_records` | List DNS records | — |
| `export_dns_records` | Export as BIND zone file | — |

## Design E 3-Tier Write

### T1 Social (AppBskyFeedPost)

- Zone 作成完了通知
- DNS レコード変更 announce
- ドメイン購入・移管・更新完了
- DNSSEC 有効化通知
- Health check 異常検知アラート

### T2 Domain (ComAtprotoRepoCreateRecord / DIDWrite)

| collection (camelCase) | 説明 |
|---|---|
| `com.etzhayyim.dns.zone` | DNS zone メタデータ (domain, zone_id, status) |
| `com.etzhayyim.dns.record` | DNS record (type, name, content, ttl, proxied) |
| `com.etzhayyim.dns.registration` | ドメイン登録イベント (purchase/transfer/renew) |
| `com.etzhayyim.dns.certificate` | SSL/TLS 証明書 |
| `com.etzhayyim.dns.dnssec_config` | DNSSEC 設定 |
| `com.etzhayyim.dns.health_check` | ヘルスチェック結果 |
| `com.etzhayyim.dns.audit_log` | 変更監査ログ |
| `com.etzhayyim.dns.whois_privacy` | WHOIS プライバシー設定 |
| `com.etzhayyim.dns.whois_snapshot` | WHOIS 定期スナップショット (registrant, registrar, NS, expiry, raw) |
| `com.etzhayyim.dns.whois_change` | WHOIS 変更検知 (field, old_value, new_value, detected_at) |
| `com.etzhayyim.dns.ownership_transfer` | 所有権移転履歴 (from/to registrar, from/to registrant, auth_method) |
| `com.etzhayyim.dns.domain_lifecycle` | ドメインライフサイクル (registered/renewed/expired/redemption/deleted/dropcatch) |
| `com.etzhayyim.dns.cert_history` | 証明書発行履歴 (serial, issuer, not_before/after, SAN, CT log) |
| `com.etzhayyim.dns.dns_record_history` | DNS レコード変更履歴 (record_type, old/new value, changed_at) |

### T3 State (ConfigGet)

- `CLOUDFLARE_API_TOKEN` — Cloudflare API 認証
- `CLOUDFLARE_ACCOUNT_ID` — Cloudflare Account ID (Registrar API 用)

## Cloudflare API Integration

| Cloudflare API | 用途 |
|---|---|
| Zones API | zone CRUD |
| DNS Records API | record CRUD |
| Registrar API | domain purchase, transfer, availability check |
| DNSSEC API | enable/disable |
| SSL/TLS API | certificate list |

**認証**: `CLOUDFLARE_API_TOKEN` env → `kotodama.ConfigGet()` → `kotodama.Send()` (net/http)。

## Commands

| command | description | MCP |
|---|---|---|
| `zone_create` | Create/import DNS zone from Cloudflare | Y |
| `zone_list` | List managed zones (SQL query) | Y |
| `zone_get` | Get zone details | Y |
| `record_create` | Add DNS record (A/AAAA/CNAME/MX/TXT/SRV/CAA/NS) | Y |
| `record_list` | List records via Cloudflare API | Y |
| `record_delete` | Delete DNS record | Y |
| `domain_check` | Check domain availability + pricing | Y |
| `domain_register` | Purchase domain via Cloudflare Registrar | Y |
| `domain_transfer` | Initiate domain transfer (auth_code) | Y |
| `dnssec_enable` | Enable DNSSEC for zone | Y |
| `health_check` | DNS propagation + SSL health check | Y |
| `whois_lookup` | WHOIS query via Cloudflare | Y |
| `audit_list` | List audit log entries (SQL query) | Y |
| `transfer_from_squarespace` | Squarespace → Cloudflare via cross-actor | Y |
| `register_zone_profiles` | Register all zone sub-DID profiles | N |
| `wave` | Social greeting | Y |
| `snapshot_whois` | WHOIS スナップショット取得 (変更検知トリガー) | Y |
| `get_whois_history` | ドメインの WHOIS 履歴タイムライン | Y |
| `get_whois_changes` | WHOIS フィールド変更検知結果 | Y |
| `record_transfer` | 所有権移転イベント記録 | Y |
| `get_transfer_lineage` | ドメイン所有権リネージ (A→B→C) | Y |
| `record_lifecycle_event` | ドメインライフサイクルイベント記録 | Y |
| `get_lifecycle_timeline` | ドメインライフサイクルタイムライン | Y |
| `get_cert_history` | SSL/TLS 証明書発行履歴 | Y |
| `get_record_history` | DNS レコード変更履歴 | Y |

## Cross-actor Integration

| Direction | Target | Method | Purpose |
|---|---|---|---|
| ← Follows | ct-monitor.etzhayyim.com | ComAtprotoSyncSubscribeRepos | CT log entry → cert_history 変換 (per-domain 証明書履歴) |
| → Invokes | yorishiro-squarespace (`sqddf3sp`) | cross-actor | Squarespace → Cloudflare 移管ワークフロー |

## WIT Capability Exports

| interface | 機能 |
|---|---|
| `etzhayyim:dns/management@1.0.0` | Zone/Record CRUD, domain registration, WHOIS, health check |
| `etzhayyim:dns/history@1.0.0` | WHOIS 履歴, 所有権移転リネージ, ライフサイクル, 証明書履歴, DNS レコード変更履歴 |

## wRPC Reactive Pipeline

```
subscribeRepos collections:
  - com.etzhayyim.dns.zone
  - com.etzhayyim.dns.record
  - com.etzhayyim.dns.registration
  - com.etzhayyim.dns.certificate
  - com.etzhayyim.dns.dnssec_config
  - com.etzhayyim.dns.health_check
  - com.etzhayyim.dns.audit_log
  - com.etzhayyim.dns.whois_privacy
  - com.etzhayyim.dns.whois_snapshot
  - com.etzhayyim.dns.whois_change
  - com.etzhayyim.dns.ownership_transfer
  - com.etzhayyim.dns.domain_lifecycle
  - com.etzhayyim.dns.cert_history
  - com.etzhayyim.dns.dns_record_history
  - com.etzhayyim.apps.ct_monitor.ct_log_entry
  - app.bsky.feed.post
  - app.bsky.feed.like
  - app.bsky.graph.follow
```

### Heartbeat WHOIS Rotation

Heartbeat (60s) で管理 domain を stagger ローテーション → 1 domain/heartbeat で WHOIS snapshot → 前回との差分検知 → 変更あれば `whois_change` record + social alert。

## SQL Graph Model

```sql
(:Zone {did, domain, status, zone_id, created_at})
(:Record {type, name, content, ttl, proxied, zone_did})
(:AuditLog {zone_did, action, details, timestamp})
(:WhoisSnapshot {domain, registrant, registrant_org, registrar, nameservers, created_date, expires_date, snapshot_at})
(:WhoisChange {domain, field, old_value, new_value, detected_at})
(:OwnershipTransfer {domain, from_registrar, to_registrar, from_registrant, to_registrant, transfer_date, status})
(:DomainLifecycle {domain, event_type, date, registrar, years})
(:CertHistory {domain, serial, issuer, subject, not_before, not_after, key_type, san_list, ct_log_id})
(:DnsRecordHistory {domain, record_type, name, old_value, new_value, changed_at})
(:Zone)-[:HAS_RECORD]->(:Record)
(:Zone)-[:DEPENDS_ON]->(:Zone)
(:Zone)-[:HAS_WHOIS_SNAPSHOT]->(:WhoisSnapshot)
(:WhoisSnapshot)-[:CHANGED_TO]->(:WhoisChange)
(:Zone)-[:TRANSFERRED_VIA]->(:OwnershipTransfer)
(:Zone)-[:LIFECYCLE_EVENT]->(:DomainLifecycle)
(:Zone)-[:HAS_CERT]->(:CertHistory)
(:Zone)-[:RECORD_CHANGED]->(:DnsRecordHistory)
```

## Governance

| axis | value |
|---|---|
| sensitivity | `internal` (API credentials) |
| disclosure_tier | T1 (zone list public), T2 (records auth required) |
| RACI | dns.etzhayyim.com = Accountable, zone DID = Responsible |
| transfer_from_squarespace | **ClassA** (3 signers, high) — domain 移管は高リスク |
