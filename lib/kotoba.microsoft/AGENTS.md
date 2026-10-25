# etzhayyim-project-microsoft

Microsoft Graph / Microsoft 365 を Matrix protocol に正規化して取り込む project。共通ルールは `60-apps/AGENTS.md` を参照し、このファイルには Microsoft 統合固有の実装方針だけを書く。

## Components

| Component | Folder | Domain | Role |
|---|---|---|---|
| **microsoft-send** (m1cr5nd5) | `appview/etzhayyim-wasm-microsoft-m1cr5nd5` | `microsoft.etzhayyim.com` | T3 TS Native write facade — `com.etzhayyim.apps.microsoft.{sendMail,sendDraft,listDrafts}` XRPC + MCP. Policy-routed: all-internal recipients direct Mail.Send, any external → auto-draft. Teams channel posting = channel email address as recipient |

### microsoft-send (write facade)

**Policy** (SSoT: `deps.toml [etzhayyim_agent.auth]`):

- `email_send_internal = "direct"` → `INTERNAL_EMAIL_DOMAINS` (`etzhayyim.com,etzhayyim.com,etzhayyim.works,etzhayyim.com`) + `INTERNAL_EMAIL_SUFFIXES` (`.onmicrosoft.com` — Teams channel email) の全宛先一致時は即時 `Mail.Send`
- `email_send_external = "draft_only"` → 1 つでも外部宛先を含む場合は Outlook Drafts に格納し `{status:"drafted", draftId, webLink}` を返す → 人間が Outlook で承認 → caller が `sendDraft` を呼ぶ
- `teams_send_method = "channel_email_via_mail_send"` → Teams 投稿は channel email を recipient に渡して `sendMail` で直送 (delegated `ChannelMessage.Send` は使わない)

**Host wiring**: host-sdk `createHostSDK` が `M365_TENANT_ID` / `M365_CLIENT_ID` / `M365_CLIENT_SECRET` env var の全揃い時に `createM365Capability` を自動構築し host dispatcher に inject。secret 不在時は NSID 呼出し時点で明確にエラー (lazy failure)。

**Deploy pre-reqs**:

1. Secrets Store (`1824561668fe47cc9127d493961885af`) に `m365_tenant_id` / `m365_client_id` / `m365_client_secret` を登録 (Keychain `etzhayyim.m365` からコピー)
2. DNS: `microsoft.etzhayyim.com` CNAME (`etzhayyim dns-sync` が自動)
3. `etzhayyim deploy` を `appview/etzhayyim-wasm-microsoft-m1cr5nd5/` で実行
4. PDS MCP adapter が `/mcp` の `tools/list` で 3 tool (`com.etzhayyim.apps.microsoft.sendMail`, `sendDraft`, `listDrafts`) を自動公開 (ADR-0042)

**Read-only peer**: `m365-ingest` (T1, `m3650xin.etzhayyim.com`) — `Application.Mail.Read` のみ。書き込みは全て microsoft-send 経由。

### MCP tool registration (one-shot seed)

新規 Worker deploy 後、MCP `tools/list` (`mcp.etzhayyim.com/xrpc/com.etzhayyim.mcp.message`) が per-actor tool を返すには `vertex_capability` に `com.etzhayyim.tool.tool` record を事前投入する必要がある。**Worker 側の自動登録は行わない** — INSERT 1 行あたり ~11s (RisingWave back-pressure) で、3 行 awaited すると 25s XRPC handler timeout を超える。

正攻法は `com.etzhayyim.tool.registerBatch` XRPC だが、2026-04-23 時点で PDS handler が Kysely `onConflict` を使っており RisingWave parser が `ON CONFLICT` を拒否 (`expected end of statement, found: on`)。これが直るまでは `com.etzhayyim.kagami.sql` 直叩きで seed する。

```bash
AT_TOKEN=$(etzhayyim agent-token --lxm com.etzhayyim.kagami.sql --ttl 180)
for ENTRY in \
  'microsoft.sendMail|3lmcrsdml01|{"type":"object",...schema...}|...description...' \
  'microsoft.sendDraft|3lmcrsddr01|...' \
  'microsoft.listDrafts|3lmcrsdls01|...' ; do
  IFS='|' read -r NAME RKEY SCHEMA DESC <<< "$ENTRY"
  # INSERT INTO vertex_capability (vertex_id, rkey, repo, did, label, name,
  # description, collection='com.etzhayyim.tool.tool', status='active', input_schema_json,
  # tags, capability_worker='m1cr5nd5') VALUES (...)
  # ~11s per INSERT — run serially.
done
```

Current canonical rkeys (2026-04-23 seed): `3lmcrsdml01` (sendMail) / `3lmcrsddr01` (sendDraft) / `3lmcrsdls01` (listDrafts) — all `repo='did:web:m1cr5nd5.etzhayyim.com'`, `capability_worker='m1cr5nd5'`.

**Verify**: `curl -sS https://mcp.etzhayyim.com/xrpc/com.etzhayyim.mcp.message -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'` の result.tools に `microsoft.sendMail/sendDraft/listDrafts` が含まれれば登録済み。Claude.ai org connector は tool list を短時間キャッシュするため、新規 tool 追加後は connector 側で再接続が必要な場合がある。

**Follow-up**: PDS `com.etzhayyim.tool.register*` ハンドラーを Kysely `.onConflict` から RisingWave 互換の DELETE+INSERT パターンに書き換えれば自動登録が再び可能になる ([`50-infra/cloudflare/workers/atproto/src/actor/tools.ts`](../../50-infra/cloudflare/workers/atproto/src/actor/tools.ts))。

## CRITICAL: Microsoft Import Boundary

→ `etzhayyim dodaf tv1 query --id etzhayyim-project-microsoft-microsoft-import-boundary` / MCP `etzhayyim.dodaf.tv1.query`

## Domain Split

- `teams`: channel/chat/message/meeting/call
- `outlook`: mail/calendar/contact/task
- `files`: SharePoint/OneDrive/drive item/file permission
- `identity`: Entra ID user/group/app/service principal

各 domain は projection を分けるが、tenant / auth / policy / cursor は共通化する。

## Data Policy

- raw payload は監査用途の最小保持に留め、query/read path は projection-first で作る。
- 標準 projection は `tenant`, `workspace`, `channel`, `thread`, `message`, `mailbox`, `calendar_event`, `file`, `identity_subject`, `membership`, `sync_cursor`, `policy_binding` の単位で分ける。
- binary は Blob API を使い、projection には metadata のみ置く。
- read/query path は SQL graph を正規とし、project 固有の dataframe read path を作らない。

## Identity Mapping

- Microsoft user / guest / bot / app は Matrix user または app actor に写像する。
- 1 tenant = 1 Matrix space root を基本とし、Teams/Outlook/files の各 domain は配下 room / thread / state に正規化する。
- shared/private/external の境界は Matrix 側に属性として保持し、membership を過剰に単純化しない。

## Compliance Boundary

- retention, legal hold, eDiscovery, DLP, sensitivity label, conditional access 由来の制約は bridge 層で評価し、Matrix へ反映できない操作は command を reject する。
- Microsoft 側の削除/編集/権限変更イベントは Matrix 側で tombstone / redact / membership diff に変換し、silent drop しない。
