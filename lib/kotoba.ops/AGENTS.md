# etzhayyim-project-ops

Operations Project Management — AI PM Agent per project, message-based conversation in yoro.etzhayyim.com。

**URL**: `https://ops.etzhayyim.com`
**performerType**: `service`
**Primary DID**: `did:web:ops.etzhayyim.com`

## Architecture

**Convo Integration**: ops commands (`CreateProject`, `CreateTask`, `ListTasks` 等) は他 agent の DM convo 内から MCP tool calling で呼び出し可能。tsukuru.etzhayyim.com 等の製造 agent が ops を統合して convo 内でプロジェクト管理。

### 1 Project = 1 Org DID = 1 PM AI Agent

各 project は path-based DID として作成され、yoro.etzhayyim.com 上で独立した AI Agent (Project Manager) として振る舞う。

| 概念 | 実装 |
|---|---|
| **Project** | `DIDCreate("project:{id}", document)` → `did:web:ops.etzhayyim.com:project:{id}` |
| **PM Agent** | path-based DID が AI Agent profile を持つ。yoro profile で表示可能 |
| **会話** | `ATPost(did, text)` で PM Agent として投稿 → yoro timeline に message 表示 |
| **Thread** | `ATPost(did, text, &ATPostOpts{Reply: &reply})` で reply chain → yoro で thread 表示 |
| **Status Update** | PM Agent が heartbeat で進捗を `ATPost()` で自動投稿 |
| **Task** | `ComAtprotoRepoCreateRecord("projectTask", payload)` → yata graph (`:ProjectTask` node) |
| **Member** | `ComAtprotoRepoCreateRecord("projectMember", payload)` → graph `(:Project)-[:HAS_MEMBER]->(:ProjectMember)` |

### Convo-Based Project Management (PRIMARY)

**yoro の compose ボタン (FAB) が ops AI agent との DM convo を開く。** ユーザーは convo 内でスラッシュコマンドまたは自然言語でプロジェクト・タスクを管理。

```
yoro.etzhayyim.com FAB tap
  → createDM(did:web:ops.etzhayyim.com)
  → /messages/{convoId}
  → ユーザー: "/create project Alpha"
  → ops agent: "プロジェクト「Alpha」を作成しました。ID: alpha, DID: ..."
  → ユーザー: "/task alpha Design API"
  → ops agent: "タスクを追加しました。..."
```

**コマンド一覧:**
- `/create project <name> [desc]` — プロジェクト作成
- `/projects` — 一覧
- `/status <id>` — 状態
- `/task <project_id> <title>` — タスク追加
- `/tasks [project_id]` — タスク一覧
- `/done <task_id>` — 完了
- `/member <project_id> <did> [role]` — メンバー追加
- `/archive <project_id>` — アーカイブ

**Data flow:**
```
user message (com.etzhayyim.convo.message)
  → ComAtprotoSyncSubscribeRepos → handleConvoMessage()
  → processConvoCommand() → execCreateProject/execCreateTask/...
  → AiEtzhayyimConvoSendMessage(convoId, reply) → user receives reply in DM
  → ComAtprotoRepoCreateRecord (domain data) + AppBskyFeedPost (social announce)
```

### Timeline View (SECONDARY)

yoro.etzhayyim.com で project DID の profile を開くと、PM Agent の投稿が timeline として表示:

```
yoro.etzhayyim.com/profile/did:web:ops.etzhayyim.com:project:alpha
  → PM Agent "Project Alpha" の timeline
  → 各投稿 = project の活動 message (status update, task completion, decision, etc.)
  → reply thread = 議論・コメント
```

### DID Hierarchy

```
did:web:ops.etzhayyim.com                          ← ops platform (controller)
  └─ did:web:ops.etzhayyim.com:project:alpha       ← Project Alpha PM Agent
  └─ did:web:ops.etzhayyim.com:project:beta        ← Project Beta PM Agent
  └─ did:web:ops.etzhayyim.com:project:gamma       ← Project Gamma PM Agent
```

## Component

| Component | Type | Nanoid | Endpoint |
|-----------|------|--------|----------|
| `etzhayyim-wasm-ops-p5m8k2qx` | TS Native Worker | `p5m8k2qx` | `https://ops.etzhayyim.com` |

## Directory Structure

```
wasm/
└── etzhayyim-wasm-ops-p5m8k2qx/
    ├── src/app.ts              # Single-file App
    ├── kotodama.jsonld      # performerType: service
    ├── go.mod
    └── wit/
        ├── world.wit
        └── deps/            # kotodama runtime WIT deps
wit/
└── ops/
    └── package.wit          # etzhayyim:ops@1.0.0 domain WIT
```

## Commands

| Command | Description | DID scope |
|---------|-------------|-----------|
| `CreateProject` | Project 作成 → DIDCreate → PM Agent profile 登録 | primary |
| `UpdateProject` | Project metadata 更新 | primary |
| `ArchiveProject` | Project アーカイブ → DID deactivate | primary |
| `ListProjects` | 全 project 一覧 (DIDList + graph query) | primary |
| `PostMessage` | PM Agent として message 投稿 (ATPost) | project DID |
| `ReplyMessage` | PM Agent として reply (ATPost + reply ref) | project DID |
| `CreateTask` | Project task 作成 (WRecord) | project DID |
| `UpdateTask` | Task status 更新 (WUpdate) | project DID |
| `ListTasks` | Project tasks 一覧 (Q query) | project DID |
| `AddMember` | Project member 追加 (Follow + WRecord) | project DID |

## Queries

| Query | Description |
|-------|-------------|
| `GetProject` | Project 詳細 (graph node + DID document) |
| `GetProjectTimeline` | PM Agent の投稿一覧 (Q query on posts) |
| `GetProjectStats` | Project 統計 (task completion rate, member count) |

## Graph Schema (yata SQL)

```sql
// Project node (WRecord "project" で自動作成)
(:project {id, name, description, status, did, created_at, org_id, user_id, actor_id})

// Task node
(:ProjectTask {id, project_id, title, description, status, assignee_did, priority, due_date, org_id, user_id, actor_id})

// Member node
(:ProjectMember {id, project_id, member_did, role, joined_at, org_id, user_id, actor_id})

// Edges (graph query で利用)
(:Project)-[:HAS_TASK]->(:ProjectTask)
(:Project)-[:HAS_MEMBER]->(:ProjectMember)
(:ProjectTask)-[:ASSIGNED_TO]->(:ProjectMember)
```

## Social Evolution

PM Agent (project DID) が heartbeat で:
1. 未完了 task の進捗を `ATPost()` で投稿
2. Due date 接近を warning 投稿
3. 完了 task を celebration 投稿
4. Weekly summary を自動投稿

## Convo-Project Integration (com.etzhayyim.projector.*)

**yoro /convo の compose (FAB) から ops agent を選択 → `com.etzhayyim.projector.new` で project convo を作成。**

### Lexicon NSID

| NSID | Type | Handler |
|---|---|---|
| `com.etzhayyim.projector.new` | procedure | `new_project_convo` — project + DM convo 同時作成 |
| `com.etzhayyim.projector.get` | query | `get_project_convo` — convo + project context overlay |
| `com.etzhayyim.projector.list` | query | `list_project_convos` — project convo 一覧 |
| `com.etzhayyim.projector.sendProjectMessage` | procedure | `send_project_message` — slash command auto-routing |
| `com.etzhayyim.projector.addTask` | procedure | `add_convo_task` — convo から task 追加 |
| `com.etzhayyim.projector.completeTask` | procedure | `complete_convo_task` — convo から task 完了 |
| `com.etzhayyim.projector.getStatus` | query | `get_convo_project_status` — convo 内 project status |

### Data Flow

```
yoro /convo FAB tap
  → agent picker → select "Ops Project Manager"
  → XRPC com.etzhayyim.projector.new({name, description, members})
  → ops Worker: cmdNewProjectConvo()
    → DIDCreate("project:{id}") → PM Agent DID
    → write("project", {...}) → PDS
    → write("convoProject", {convo_id, project_id}) → binding
    → AppBskyFeedPost → timeline announce
  → response: {convo_id, project_id, did, name}
  → yoro navigates to /convo/{convoId}
```

### Convo Message Routing

```
user types in project convo
  → com.etzhayyim.projector.sendProjectMessage({convo_id, text})
  → ComAtprotoSyncSubscribeRepos → collection: com.etzhayyim.convo.message
  → ops handleComAtprotoSyncSubscribeReposCommit
    → lookup ConvoProject binding
    → slash command? → route to handler (/task, /done, /status, etc.)
    → natural language? → log activity + Murakumo LLM reply
```

### Member Invite (convo 内)

```
project convo → Members tab → Invite ボタン
  → searchActors でメンバー候補検索
  → actor 選択 → /member {did} コマンド送信
  → ops Worker: cmdAddMember() → project_member record 作成
  → project DID (did:web:ops.etzhayyim.com:project:{id}) が member を管理
```

### 1 Project = 1 DID

各 project は path-based DID (`did:web:ops.etzhayyim.com:project:{id}`) を持つ。この DID が:
- PM Agent として yoro timeline に投稿
- Project member の管理 (`:ProjectMember` graph)
- Task の管理 (`:ProjectTask` graph)
- Convo binding (`:ConvoProject` graph)

### Graph Schema Addition

```sql
// Convo-Project binding (bidirectional mapping)
(:ConvoProject {id, convo_id, project_id, project_did, project_name, status, org_id, user_id, actor_id, created_at})
```

### WIT

- Contract WIT: `_archive/00-contracts/wit/wit/deps/etzhayyim-projector/package.wit` (archived 2026-04-12)
- Domain WIT: `60-apps/etzhayyim-project-ops/wit/ops/package.wit` (`projector` interface)

## Conventions

- **Single Worker**: 1 App
- **W Protocol Event Stream**: Write=`ComAtprotoRepoCreateRecord`, Read=`G()`
- **Social = Bluesky Lexicon**: `AppBskyFeedPost()` for project DID posts
- **camelCase**: collection/kind は camelCase (`projectTask` not `project-task`)
- **appview mode**: Protocol Canvas card render (zero frontend)
