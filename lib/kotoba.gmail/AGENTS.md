# etzhayyim-project-gmail — Gmail Intelligence Platform

## App Identity

| Key | Value |
|---|---|
| **nanoid** | `gm4il0x1` |
| **domain** | `gmail.etzhayyim.com` |
| **AT bot DID** | `did:web:gmail.etzhayyim.com` |
| **Runtime** | **Single Worker** (TS Native, appview mode) |
| **Data store** | **Design E 3-Tier Write** — T2 Domain (`sdk.pds.createRecord`, collection `com.etzhayyim.apps.gmail.{email,thread,contact,syncJob,outboundEmail,accountBinding,account,phishingAlert}`) → RisingWave `vertex_gmail_*`. T1 Social (`app.bsky.feed.post`) for sync/connect events |
| **OAuth token custody** | **D1 `GMAIL_DB` + KEK envelope** (ADR-0010 Stage 1 pattern) — `vertex_gmail_oauth_token` (refresh_token AES-256-GCM with per-row data key, data key AES-256-GCM wrap by `SS_GMAIL_TOKEN_KEK`). Server-side only, never leaves worker |
| **UI mode** | `appview` (Protocol Canvas card, zero frontend) |
| **Capabilities** | gmail-sync, email-triage, contact-did-creation, messenger-email-bridge, phishing-detection |

## Implementation Status (2026-04-17)

**Phase 1+2 live** (`src/app.ts` rewrite + `20260417130000_vertex_gmail_tables.ts` migration):

| Piece | Status |
|---|---|
| OAuth2 connect flow (`GET /oauth/callback` Hono route + `connectAccount` XRPC) | ✅ Live |
| KEK envelope D1 token store (refresh_token never plaintext at rest) | ✅ Live |
| `syncInbox` XRPC — messages.list → messages.get metadata → `vertex_gmail_email` rows + phishing score inline | ✅ Live |
| `sendEmail` / `replyToThread` XRPC — RFC 2822 MIME → `/users/me/messages/send` | ✅ Live |
| `listAccounts`, `getThread`, `disconnectAccount` XRPC | ✅ Live |
| Cron scheduled handler `*/15 * * * *` — `users.history.list` delta sync per active account, `historyId` cursor in `vertex_gmail_oauth_token.history_id` | ✅ Live |
| `listThreads` / `searchEmails` read path against RisingWave | ⏳ Stub — returns `[]` until Kysely wired against `vertex_gmail_thread`/`vertex_gmail_email` |
| `triage` — phishing score for already-ingested rows | ⏳ Stub — inline scoring happens in `syncInbox`; this XRPC returns `[]` pending graph-read wiring |
| Contact path DID creation per sender (`did:web:gmail.etzhayyim.com:contact:*`) | ✅ Live (2026-04-22, ADR-0049 Phase B1) — `upsertContactViaUdf()` after every `vertex_gmail_email` insert delegates to `gmail_upsert_contact` external Python UDF on the mitama-udf pool. Materializes `vertex_gmail_contact` + `edge_gmail_email_from_contact` with `WHERE NOT EXISTS` idempotency. PDS `did.create` registration deferred to a promotion job that filters by activity threshold |
| `send_message` cross-actor handler (yoro messenger bridge) | ⏳ Not yet — `sendEmail` is the direct path for now |
| Appview UI (`/embed`) | ⏳ Zero-UI, uses Protocol Canvas card via `appview` mode |

### Key lexicons (in `00-contracts/lexicons/com/etzhayyim/apps/gmail/`)

`connectAccount`, `oauthCallback`, `syncInbox`, `sendEmail`, `replyToThread`, `disconnectAccount`, `listAccounts`, `getThread`, `listThreads`, `searchEmails`, `triage`.

### Secret bindings (wrangler.jsonc, Secrets Store)

| Binding | Purpose |
|---|---|
| `SS_GMAIL_TOKEN_KEK` | AES-256 KEK (base64url, 32 bytes) wrapping per-row data keys (shared across **all** Google Workspace ingest apps per 90-docs/260417-google-workspace-ingest-runbook.md) |
| `SS_GOOGLE_OAUTH_CLIENT_ID` | Google Cloud OAuth2 Web client id (shared, GCP project `etzhayyim-ws-ingest`, owner `jun@etzhayyim.com`) |
| `SS_GOOGLE_OAUTH_CLIENT_SECRET` | same, client secret |

All 3 resolved via `resolveSecret(v)` helper at use time (Secrets Store bindings are `SecretBinding` objects with `.get()`, not plain strings — passing them into `URLSearchParams` or `fetch` body directly serializes as `[object Fetcher]`).

## Architecture

**Gmail account sync → DID per email contact → yoro messenger bridge.**

### mailer.etzhayyim.com との違い

| | mailer | gmail |
|---|---|---|
| **方向** | Inbound SMTP → Signal DM | Gmail API OAuth2 ↔ yoro messenger |
| **DID** | email_binding (DID ↔ address mapping) | **contact DID** (各メール送信者が独自の DID) |
| **UI** | appview | appview (yoro profile ?app=1 で MCP tools 表示) |
| **受信** | CF Email Routing → inbound record | Gmail API sync → email record → contact DID が投稿 |
| **送信** | Resend SMTP | yoro messenger → `send_message` Handle → Gmail API |

### Data Flow

```
[OAuth2 Connect]
  User → yoro profile → MCP tool "connect_account" → OAuth2 flow → account_binding record

[Sync]
  User → MCP tool "sync_inbox" → sync_job record (Collection Job)
  → PDS pipeline → Gmail API incremental sync → email records
  → handleComAtprotoSyncSubscribeReposCommit: processNewEmail
    → DIDCreate("contact:{email_path}") per sender
    → AppBskyFeedPostAs(contactDID, subject + snippet)  ← appears in yoro messenger
    → Murakumo AI triage → triage_result record

[Receive (email → messenger)]
  Gmail inbox → sync → email record → contact DID posts in yoro
  → governance-connected users see contact posts in messenger

[Send (messenger → email)]
  User → yoro messenger → Invoke(gmail, "send_message", {contact_did, text})
  → handleSendMessage: resolve contact DID → email, resolve caller → Gmail account
  → outbound_email record → PDS pipeline → Gmail API send
```

### Design E 3-Tier Write

| Tier | Usage |
|---|---|
| **T1 Social** | `AppBskyFeedPostAs(contactDID, ...)` — incoming emails as contact DID posts。`AppBskyFeedPost(...)` — sync events, triage alerts |
| **T2 Domain** | `ComAtprotoRepoCreateRecord()` — email, thread, sync_job, triage_result, account_binding, contact_did, outbound_email, label_action |
| **T3 State** | `Preferences()` — triage rules, notification settings |

### Multi-DID Architecture

```
did:web:gmail.etzhayyim.com                           ← primary (controller)
  ├─ did:web:gmail.etzhayyim.com:contact:john_at_example_com  ← contact DID
  ├─ did:web:gmail.etzhayyim.com:contact:alice_at_corp_co     ← contact DID
  └─ did:web:gmail.etzhayyim.com:contact:...                   ← N contacts
```

Each email sender = path-based DID → appears as actor in yoro → messageable.

### Governance

- `HandleFollowRequest`: auto-approve all followers (onboarding entry point)
- `processFollow`: welcome post with connect instructions on follow
- `app.Handle("", "send_message", ..., RequireCallerRole("member"))`: only followers can send

## UX Flow (yoro.etzhayyim.com/profile/did:web:gmail.etzhayyim.com?app=1)

```
Step 1: フォロー
  [フォローする] → auto-approve → welcome post
  "Welcome to Gmail Intelligence! Connect your Gmail account to..."

Step 2: Gmail 接続 (MCP tool "connect_account")
  → account_binding (pending_oauth) → OAuth2 redirect → Google 認証
  → account_binding (active) → processAccountBinding:
    "Gmail connected: user@gmail.com — Syncing inbox..."
  → auto-trigger sync_job (full sync)

Step 3: 同期 → contact DID 自動作成
  sync_job → PDS pipeline → Gmail API → email records
  → DIDCreate("contact:{email_path}") per sender
  → AppBskyFeedPostAs(contactDID, subject + snippet)
  → Murakumo AI triage → triage_result

Step 4: メッセンジャーで受信・返信
  yoro メッセンジャー → contact DID の会話一覧
  → 返信入力 → Invoke(gmail, "send_message", {contact_did, text})
  → DID → email 解決 → outbound_email → Gmail API 送信
```

## XRPC Commands (camelCase NSIDs per AT Protocol)

| NSID | Type | Status |
|---|---|---|
| `com.etzhayyim.apps.gmail.connectAccount` | procedure | ✅ returns `oauthUrl` |
| `com.etzhayyim.apps.gmail.oauthCallback` | query | ✅ backend of Hono `GET /oauth/callback` (same logic) |
| `com.etzhayyim.apps.gmail.disconnectAccount` | procedure | ✅ marks token row disconnected |
| `com.etzhayyim.apps.gmail.syncInbox` | procedure | ✅ messages.list → get metadata → vertex_gmail_email |
| `com.etzhayyim.apps.gmail.sendEmail` | procedure | ✅ Gmail API `messages.send` |
| `com.etzhayyim.apps.gmail.replyToThread` | procedure | ✅ thread resolve + In-Reply-To/References |
| `com.etzhayyim.apps.gmail.listAccounts` | query | ✅ D1 `vertex_gmail_oauth_token` scan |
| `com.etzhayyim.apps.gmail.getThread` | query | ✅ live Gmail API fetch |
| `com.etzhayyim.apps.gmail.listThreads` | query | ⏳ stub (RisingWave wiring pending) |
| `com.etzhayyim.apps.gmail.searchEmails` | query | ⏳ stub (RisingWave wiring pending) |
| `com.etzhayyim.apps.gmail.triage` | procedure | ⏳ stub; inline scoring already runs in `syncInbox` |

### Future: cross-actor messenger bridge

| Method | Handler | Governance |
|---|---|---|
| `send_message` | `handleSendMessage` (not yet implemented) | `RequireCallerRole("member")` — followers only |

## Build & Deploy

```bash
cd 60-apps/etzhayyim-project-gmail/appview/etzhayyim-wasm-gmail-gm4il0x1

# Direct wrangler deploy (recommended for now).
# ⚠️ `etzhayyim deploy` regenerates wrangler.jsonc from buildWranglerJSON() and strips
#    the d1_databases / triggers.crons / custom SS_* bindings that this app needs.
#    Until etzhayyim CLI learns those sections, use raw wrangler.
npx wrangler deploy
```

### Required infra (provision once)

```bash
# 1. D1 database for OAuth token custody
wrangler d1 create gmail-oauth-tokens
# → replace database_id in wrangler.jsonc

# 2. KEK (shared across all Workspace ingest apps)
openssl rand -base64 32 | tr '+/' '-_' | tr -d '=' | \
  wrangler secrets-store secret create <STORE_ID> \
    --name gmail_token_kek --scopes workers --remote --value -

# 3. Google OAuth client (Google Cloud Console)
#    - project: etzhayyim-ws-ingest (owner jun@etzhayyim.com)
#    - Web application, Authorized redirect URI: https://gmail.etzhayyim.com/oauth/callback
#    - Gmail API enabled
#    - OAuth consent screen → add Test users until sensitive-scope verification clears
wrangler secrets-store secret create <STORE_ID> --name google_oauth_client_id --scopes workers --remote
wrangler secrets-store secret create <STORE_ID> --name google_oauth_client_secret --scopes workers --remote

# 4. RisingWave schema (applied out-of-band per 30-graph/graph-schema drift procedure)
DATABASE_URL=postgresql://root@172.236.132.11:4566/dev pnpm -w run db:migrate
# or direct psql if kysely migrator is blocked by pre-existing drift
```

### Smoke test (after deploy)

```bash
curl -sS https://gmail.etzhayyim.com/health
# → {"status":"ok","app":"gm4il0x1"}

curl -sS -X POST https://gmail.etzhayyim.com/xrpc/com.etzhayyim.apps.gmail.connectAccount \
  -H 'content-type: application/json' \
  -d '{"email":"jun@etzhayyim.com","accountDid":"did:web:etzhayyim.com"}'
# → {"status":"pending_oauth","oauthUrl":"https://accounts.google.com/o/oauth2/v2/auth?..."}

# Open oauthUrl in browser → sign in → consent → redirect to /oauth/callback
# After callback success:
curl -sS https://gmail.etzhayyim.com/xrpc/com.etzhayyim.apps.gmail.listAccounts
# → {"accounts":[{"email":"jun@etzhayyim.com",...,"status":"active",...}],"total":1}

# Manual sync trigger (or wait for cron)
curl -sS -X POST https://gmail.etzhayyim.com/xrpc/com.etzhayyim.apps.gmail.syncInbox \
  -H 'content-type: application/json' -d '{"email":"jun@etzhayyim.com","maxResults":25}'

# Verify rows landed in RisingWave
psql "$ROOT_URL" -c 'SELECT from_addr, subject FROM vertex_gmail_email ORDER BY _seq DESC LIMIT 5'
```

## Related docs

- Root Workspace ingest plan: `90-docs/260417-google-workspace-ingest-runbook.md` (gmail is Phase 1 reference impl)
- OAuth token custody pattern: `60-apps/etzhayyim-project-auth/AGENTS.md` §KEK envelope (ADR-0010 Stage 1) — the exact `envelopeEncrypt`/`envelopeDecrypt` helpers are duplicated here, could be extracted to `kotodama-host-sdk` when a 2nd Workspace app lands
- RisingWave schema SSoT: `30-graph/graph-schema/migrations/20260417130000_vertex_gmail_tables.ts` + `20260417140000_vertex_google_workspace_tables.ts` (broader workspace)
