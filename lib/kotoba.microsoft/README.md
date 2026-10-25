# etzhayyim-project-microsoft

Microsoft Graph / Microsoft 365 を Matrix protocol に正規化し、etzhayyim の App 群で扱うための設計メモ。正規入口は `Command=Matrix protocol`, `Query=XRPC` に揃える。

## Goal

- Microsoft 365 の Teams / Outlook / SharePoint / OneDrive / Entra ID を Matrix に正規化する
- Microsoft 固有 API を business app から隔離し、bridge で吸収する
- etzhayyim の agent / human / app 間通信を Matrix に一本化する
- Microsoft 側の監査・保持・権限制約を Matrix projection に反映する

## Non-Goals

- Microsoft 各 UI をそのまま再実装しない
- business app が Graph API を直接叩かない
- Query を Matrix event で実装しない
- day 1 で Microsoft 365 全 surface を完全移植しない

## Scope

### Day 1

- Teams import and bridge
- Entra ID identity mapping
- SharePoint / OneDrive file metadata import
- Outlook mailbox and calendar projection

### Later

- delegated send / reply / edit
- meeting transcript / recording workflows
- eDiscovery / legal hold export
- planner / task / copilot signal integration

## High-Level Architecture

```text
Microsoft Graph / Microsoft 365
  ├─ Teams
  ├─ Outlook
  ├─ SharePoint / OneDrive
  ├─ Entra ID
  └─ Webhook / Change Notification / Delta API
          ↓
microsoft-bridge-appservice (native Go first)
  ├─ OAuth / token rotation / tenant consent
  ├─ delta sync / webhook ingest / backfill
  ├─ compliance gate (retention/DLP/legal hold)
  ├─ canonical mapping to Matrix
  └─ raw ingest + cursor persistence
          ↓
Matrix homeserver / appservice
  ├─ Matrix users
  ├─ Spaces / rooms / threads
  └─ org.etzhayyim.command.microsoft-* events
          ↓
microsoft-gateway App
  ├─ Matrix command handlers
  ├─ domain projection updater
  ├─ policy / mapping resolution
  └─ Cypher Graph-backed QueryService
          ↓
Cypher graph projection + blob store
          ↓
microsoft miniapp UI (Matrix widget)
  ├─ command via Matrix client-server API
  └─ query via XRPC QueryService
```

## Component Split

### 1. `microsoft-bridge-appservice`

責務:
- Graph webhook / change notification 受信
- delta sync, backfill, cursor 管理
- domain payload を Matrix canonical event に変換
- tenant/user/group/channel/chat/mail/file/meeting を Matrix ID に写像
- DLP / retention / legal hold / permission 制約で event を accept/reject

実装形:
- 初期は native Go service 推奨
- 理由: Graph auth, webhook validation, token refresh, retry, crypto, large file handling が重い

### 2. `microsoft-gateway` App

責務:
- Matrix command event を domain command に変換
- import projection を query しやすい形に整備
- room/thread/member/mailbox/file mapping を返す QueryService
- policy conflict を UI 向けに返す

実装形:
- App (WASM)
- Matrix command handler + Cypher graph-backed QueryService を一体で持つ

### 3. `microsoft-static` miniapp

責務:
- Matrix widget として埋め込まれる運用 UI
- tenant health, sync backlog, room mapping, mailbox/file/calendar projection, compliance warning 表示
- command 操作は Matrix event 発行
- list/search/detail は Connect QueryService 参照

## Domain Model

| Domain | Microsoft Source | Matrix Target | Projection |
|---|---|---|---|
| `teams` | team/channel/chat/message/meeting | space/room/thread/event | `ms_teams_*` |
| `mail` | mailbox/message/folder | room/thread/message task view | `ms_mail_*` |
| `calendar` | calendar/event | room state + event projection | `ms_calendar_*` |
| `files` | drive/site/item/permission | blob + room attachment ref | `ms_files_*` |
| `identity` | user/group/app/sp | matrix user/member/actor | `ms_identity_*` |
| `tenant` | org/subscription/policy | space root + policy state | `ms_tenants` |

## Canonical Mapping

### Teams

| Microsoft Teams | Matrix |
|---|---|
| tenant | space root |
| team | space or room group |
| standard channel | room |
| private/shared channel | separate room |
| chat | DM room / small room |
| root message | event |
| reply chain | thread relation |
| meeting chat | dedicated room/thread |

### Outlook

| Outlook | Matrix |
|---|---|
| mailbox | app-scoped room set |
| mail thread | thread room |
| message | event |
| calendar | room state namespace |
| calendar event | event projection |

### Files

| SharePoint / OneDrive | Matrix |
|---|---|
| site / drive | workspace binding |
| drive item | blob ref + metadata event |
| permission | room/member policy projection |

### Identity

| Entra ID | Matrix |
|---|---|
| user | matrix user |
| guest | external matrix user attribute |
| group | room membership source |
| app / service principal | app actor |

## Command / Query Contract

### Matrix Commands

正規入口 event type:
- `org.etzhayyim.command.microsoft-tenant.connect`
- `org.etzhayyim.command.microsoft-sync.run`
- `org.etzhayyim.command.microsoft-teams.link-room`
- `org.etzhayyim.command.microsoft-mail.import`
- `org.etzhayyim.command.microsoft-calendar.import`
- `org.etzhayyim.command.microsoft-file.import`
- `org.etzhayyim.command.microsoft-message.send`
- `org.etzhayyim.command.microsoft-message.redact`
- `org.etzhayyim.command.microsoft-membership.sync`
- `org.etzhayyim.command.microsoft-policy.reconcile`

共通 envelope:

```json
{
  "commandId": "cmd_xxx",
  "tenantId": "tenant-guid",
  "domain": "teams",
  "workspaceId": "team-or-mailbox-id",
  "roomId": "!room:matrix.etzhayyim.com",
  "actorId": "user_or_agent",
  "requestedBy": "@user:matrix.etzhayyim.com",
  "payload": {}
}
```

### Connect QueryService

QueryService の read backend はすべて Cypher graph に揃える。

正規 read:
- `MicrosoftQueryService/ListTenants`
- `MicrosoftQueryService/ListWorkspaces`
- `MicrosoftQueryService/ListRooms`
- `MicrosoftQueryService/GetRoomMapping`
- `MicrosoftQueryService/ListMessages`
- `MicrosoftQueryService/ListFiles`
- `MicrosoftQueryService/ListCalendarEvents`
- `MicrosoftQueryService/ListIdentitySubjects`
- `MicrosoftQueryService/GetSyncStatus`
- `MicrosoftQueryService/ListPolicyFindings`

ルール:
- pagination は `offset`, `limit`, `total`
- mutation 系は QueryService に置かない
- `natad` / `dataframe` を query backend に使わない
- hot path の list/read/search は Cypher graph query で表現する

## Projection Model

最低限必要な projection table:

| Table | Purpose |
|---|---|
| `ms_tenants` | tenant 接続状態、display name、policy mode |
| `ms_workspaces` | team / mailbox / site / drive の正規化 |
| `ms_rooms` | channel/chat/mail thread -> room mapping |
| `ms_messages` | teams/mail root/reply/tombstone/edit projection |
| `ms_memberships` | membership / role / guest / external |
| `ms_files` | attachment metadata, blob key, source link |
| `ms_calendar_events` | calendar event projection |
| `ms_identity_subjects` | user/group/app/service principal |
| `ms_sync_cursors` | delta token, last successful sync, retry state |
| `ms_policy_findings` | DLP / retention / legal hold の警告 |

標準列:
- 全 table に `org_id`, `user_id`, `actor_id`
- source trace 用に `source_system`, `source_domain`, `source_id`, `source_version`, `last_seen_at`

## Arrow Schema Design

Microsoft import は projection-first で Arrow-compatible schema に落とす。raw JSON だけを read path に使わない。

### Read Path Rule

- read/query path はすべて Cypher graph
- app 内で `natad` / `dataframe` の独自 read helper を増やさない
- QueryService は Cypher graph query の facade として振る舞う
- projection nodes は Cypher MATCH で filter/sort が効く shape を優先する

### Common Column Contract

全 projection table の共通列:
- `org_id: utf8`
- `user_id: utf8`
- `actor_id: utf8`
- `tenant_id: utf8`
- `source_system: utf8` (`"microsoft-graph"`)
- `source_domain: utf8` (`"teams" | "mail" | "calendar" | "files" | "identity"`)
- `source_id: utf8`
- `source_version: utf8`
- `event_time: timestamp[ms, utc]`
- `ingested_at: timestamp[ms, utc]`
- `updated_at: timestamp[ms, utc]`
- `deleted_at: timestamp[ms, utc] nullable`
- `raw_json: utf8 nullable`

設計原則:
- filter/sort に使う列は scalar 列に昇格し、`raw_json` nested filter に依存しない
- ID / status / type / time / room mapping は専用列に出す
- list API の hot path は projection table を直接叩ける shape にする
- attachment / transcript / html body は blob metadata と分離する

### Suggested Arrow Tables

#### `ms_tenants`

- `tenant_id: utf8`
- `display_name: utf8`
- `tenant_domain: utf8`
- `service_mode: utf8`
- `consent_status: utf8`
- `sync_status: utf8`
- `last_sync_at: timestamp[ms, utc] nullable`
- `policy_mode: utf8`
- `default_space_id: utf8 nullable`

#### `ms_workspaces`

- `workspace_id: utf8`
- `tenant_id: utf8`
- `workspace_type: utf8`
- `display_name: utf8`
- `matrix_space_id: utf8 nullable`
- `parent_workspace_id: utf8 nullable`
- `visibility: utf8`
- `external_sharing: bool`

#### `ms_rooms`

- `room_binding_id: utf8`
- `tenant_id: utf8`
- `workspace_id: utf8`
- `room_id: utf8`
- `matrix_room_id: utf8`
- `room_kind: utf8`
- `display_name: utf8`
- `topic: utf8 nullable`
- `is_private: bool`
- `is_shared: bool`
- `membership_count: int32`
- `last_message_at: timestamp[ms, utc] nullable`

#### `ms_messages`

- `message_binding_id: utf8`
- `tenant_id: utf8`
- `workspace_id: utf8`
- `room_id: utf8`
- `matrix_room_id: utf8`
- `matrix_event_id: utf8 nullable`
- `thread_root_id: utf8 nullable`
- `sender_subject_id: utf8`
- `message_kind: utf8`
- `delivery_status: utf8`
- `body_text: utf8 nullable`
- `body_blob_key: utf8 nullable`
- `reply_count: int32`
- `edited: bool`
- `redacted: bool`
- `has_attachments: bool`

#### `ms_files`

- `file_binding_id: utf8`
- `tenant_id: utf8`
- `workspace_id: utf8 nullable`
- `room_id: utf8 nullable`
- `drive_id: utf8`
- `site_id: utf8 nullable`
- `item_id: utf8`
- `blob_key: utf8 nullable`
- `filename: utf8`
- `mime_type: utf8`
- `size_bytes: int64`
- `content_etag: utf8 nullable`
- `download_status: utf8`
- `classification_label: utf8 nullable`

#### `ms_calendar_events`

- `calendar_binding_id: utf8`
- `tenant_id: utf8`
- `owner_subject_id: utf8`
- `calendar_id: utf8`
- `event_id: utf8`
- `matrix_room_id: utf8 nullable`
- `title: utf8`
- `start_at: timestamp[ms, utc]`
- `end_at: timestamp[ms, utc]`
- `is_online_meeting: bool`
- `meeting_room_binding_id: utf8 nullable`
- `response_status: utf8`

#### `ms_identity_subjects`

- `subject_binding_id: utf8`
- `tenant_id: utf8`
- `subject_id: utf8`
- `subject_type: utf8`
- `matrix_user_id: utf8 nullable`
- `display_name: utf8`
- `primary_email: utf8 nullable`
- `principal_name: utf8 nullable`
- `is_guest: bool`
- `is_service_principal: bool`
- `status: utf8`

#### `ms_sync_cursors`

- `cursor_id: utf8`
- `tenant_id: utf8`
- `source_domain: utf8`
- `resource_scope: utf8`
- `delta_token: utf8 nullable`
- `watermark: utf8 nullable`
- `sync_status: utf8`
- `retry_count: int32`
- `last_success_at: timestamp[ms, utc] nullable`
- `last_error: utf8 nullable`

### Arrow Type Rules

- ID はすべて `utf8`
- timestamp は `timestamp[ms, utc]`
- flags は `bool`
- 件数や page 集計は `int32`
- file size や byte count は `int64`
- JSON fallback 列は `utf8` にし、Arrow nested を read hot path の前提にしない

## Matrix Protocol Compatibility

Microsoft domain を Matrix に取り込むときは、Matrix の room/event/user semantics を壊さないことを優先する。

### Compatibility Principles

- command は必ず Matrix event として流す
- query は Matrix timeline から読まず、Connect QueryService で projection を返す
- source delete/edit/reaction/reply は Matrix の標準 relation/redaction/edit semantics に写像する
- source private/shared/external の境界は Matrix room 分離または state で保持し、1 room に混ぜて曖昧化しない

### Canonical Event Mapping

| Microsoft Action | Matrix Form |
|---|---|
| new Teams/channel/chat message | `m.room.message` + app metadata |
| reply | `m.room.message` + `m.relates_to.m.in_reply_to` |
| edit/update | `m.replace` relation + projection update |
| delete | redaction + tombstone projection |
| reaction | `m.reaction` |
| membership change | `m.room.member` compatible state + projection diff |
| file attached | message event + blob metadata event |
| meeting started/ended | state event or typed app event in room |
| sync status update | app-specific state event, not public timeline spam |

### App-Specific Event Namespace

標準 Matrix event で表せない制御面は app-specific namespace に閉じる:
- `org.etzhayyim.command.microsoft-*`
- `org.etzhayyim.state.microsoft-*`
- `org.etzhayyim.policy.microsoft-*`

ルール:
- user-visible conversation はできるだけ `m.room.message` 系に寄せる
- operational state や sync cursor は app-specific state event へ分離する
- public contract に `org.etzhayyim.query.*` を追加しない

### Identity Compatibility

- Matrix primary ID を canonical user key とし、Microsoft object ID は external reference として保持する
- 1 Microsoft user が複数 mailbox / tenant を持つ場合も Matrix actor を無闇に複製しない
- guest / external / service principal は Matrix profile/state に role attribute を持たせる

### Room Compatibility

- 1 tenant = 1 root space
- 1 team/mailbox/site grouping = 1 workspace projection
- private channel/shared channel/external chat は別 room
- retention or legal hold の異なる source を同じ Matrix room にマージしない

### Timeline Compatibility

- source 側の edit/delete は順序保証のため idempotent event reconciliation を行う
- bridge 再送時は `source_id + source_version` を idempotency key にする
- large mailbox sync や backfill は Matrix timeline を埋め尽くさず、projection 優先 + summary state event に留める

## Event Flow

### Microsoft → Matrix

1. webhook / delta sync が変更を受信
2. bridge が domain object を canonical event に変換
3. compliance gate で hold / redact / reject 判定
4. Matrix AS transaction として room に投入
5. `microsoft-gateway` が projection 更新
6. miniapp は Cypher graph-backed QueryService で最新 read model を取得

### Matrix / etzhayyim → Microsoft

1. user/agent が Matrix room で `org.etzhayyim.command.microsoft-message.send` などを発行
2. `microsoft-gateway` が command validation
3. bridge が Graph API へ送信
4. Microsoft 側 object ID を取得
5. bridge が ack event を Matrix に返す
6. projection が external delivery status を更新

## Compliance / Security

- OAuth credential は bridge だけが保持し、business app に渡さない
- sensitivity label / retention label / legal hold / DLP は `ms_policy_findings` に明示
- external user / guest / shared artifact は Matrix membership/ACL に縮約しすぎず属性保持する
- file import は virus scan / content-type validation 後に Blob API 保存
- transcript / recording / mailbox content は PII redaction policy を bridge で適用

## Failure Handling

- webhook missed event は delta sync で補完
- Matrix 送信失敗時は retry queue + idempotency key
- room mapping 不整合は `microsoft-policy.reconcile` command で修復
- source delete 済み object は projection tombstone とし、silent resurrect しない

## Delivery Plan

### Phase 1

- tenant connect
- Teams team/channel/chat import
- Entra ID user/group mapping
- room mapping query
- basic widget UI

### Phase 2

- Outlook mail/calendar import
- SharePoint / OneDrive file metadata import
- send/reply/edit/delete bridge-back
- compliance findings UI

### Phase 3

- recording/transcript workflow
- eDiscovery export
- cross-app automation from Microsoft-origin events

## Suggested Folder Shape

```text
60-apps/etzhayyim-project-microsoft/
  AGENTS.md
  README.md
  OWNERS
  wasm/
    etzhayyim-wasm-microsoft-gateway-<nanoid>/
      main.go
      wit/world.wit
      App manifest
      kotodama.toml
      svelte/
    etzhayyim-wasm-microsoft-static-<nanoid>/
      kotodama.toml
      svelte/
  native/
    microsoft-bridge-appservice/
      main.go
      internal/
```

## Open Questions

- transcript / mailbox body を blob + searchable index のどちらまで扱うか
- tenant ごとの retention / sensitivity policy を Matrix state event に持つか projection 専用にするか
- Teams bot 送信と Outlook delegated send の権限境界をどこで切るか
- shared channel / external mailbox を org 跨ぎ Matrix federation に出すか、tenant 内限定 room に閉じるか
