# etzhayyim-project-x — X (Twitter) Intelligence Platform

## App Identity

| Key | Value |
|---|---|
| **nanoid** | `xw1tt3r1` |
| **domain** | `x.etzhayyim.com` |
| **AT bot DID** | `did:web:x.etzhayyim.com` |
| **Runtime** | **Single Worker** (TS Native, appview mode) |
| **Data store** | **W Protocol Event Stream** — Write: `ComAtprotoRepoCreateRecord()` + `DIDCreate()` + `DIDWrite()`. Read: `G()` SQL |
| **UI mode** | `appview` (Protocol Canvas card, zero frontend) |
| **Capabilities** | x-sync, profile-collection, follower-graph, tweet-collection, timeline-analysis |

## Architecture

**X account OAuth connect -> profile/tweet/follower sync -> DID per X user -> yoro social bridge.**

### Data Flow

```
[OAuth2 Connect]
  User -> yoro profile -> MCP tool "connect_account" -> OAuth2 flow -> account_binding record

[Sync]
  User -> MCP tool "sync_profile" -> collection_job record
  -> PDS pipeline -> X API v2 incremental sync -> x_entity records
  -> handleComAtprotoSyncSubscribeReposCommit: processNewProfile
    -> DIDCreate("user:{username}") per X user
    -> AppBskyFeedPost(userDID, bio + stats)  <- appears in yoro
    -> Murakumo AI timeline analysis -> x_report record

[Profile Collection]
  X API -> sync -> x_entity (profile) -> user DID posts in yoro

[Follower Graph]
  X API -> sync -> x_entity (follower/following) -> graph edges
  -> (:XProfile)-[:FOLLOWS]->(:XProfile) in yata

[Tweet Collection]
  X API -> sync -> x_entity (tweet) -> tweet records
  -> AppBskyFeedPost(userDID, tweet_text) for high-engagement tweets
```

### Design E 3-Tier Write

| Tier | Usage |
|---|---|
| **T1 Social** | `AppBskyFeedPost(userDID, ...)` — notable tweets as user DID posts. `AppBskyFeedPost(...)` — sync events, analysis alerts |
| **T2 Domain** | `ComAtprotoRepoCreateRecord()` — x_entity (profile/tweet/follower/list), x_event (sync jobs), x_report (analysis), account_binding |
| **T3 State** | `Preferences()` — sync interval, filter rules |

### Multi-DID Architecture

```
did:web:x.etzhayyim.com                              <- primary (controller)
  +- did:web:x.etzhayyim.com:user:elonmusk           <- X user DID
  +- did:web:x.etzhayyim.com:user:jack               <- X user DID
  +- did:web:x.etzhayyim.com:user:...                <- N users
```

Each X account = path-based DID -> appears as actor in yoro -> viewable profile.

### Governance

- `HandleFollowRequest`: auto-approve all followers (onboarding entry point)
- `processFollow`: welcome post with connect instructions on follow
- `app.Handle("", "sync_profile", ..., RequireCallerRole("member"))`: only followers can trigger sync

## UX Flow (yoro.etzhayyim.com/profile/did:web:x.etzhayyim.com?app=1)

```
Step 1: Follow
  [Follow] -> auto-approve -> welcome post
  "Welcome to X Intelligence! Connect your X account to..."

Step 2: X account connect (MCP tool "connect_account")
  -> account_binding (pending_oauth) -> OAuth2 redirect -> X auth
  -> account_binding (active) -> processAccountBinding:
    "X connected: @username — Syncing profile..."
  -> auto-trigger sync_profile (full sync)

Step 3: Sync -> user DID auto-creation
  collection_job -> PDS pipeline -> X API v2 -> x_entity records
  -> DIDCreate("user:{username}") per X user
  -> AppBskyFeedPost(userDID, bio + stats)
  -> follower/following graph edges created

Step 4: Timeline analysis
  x_entity (tweets) -> Murakumo AI analysis -> x_report
  -> AppBskyFeedPost("Timeline analysis for @username: ...")
```

## Commands (MCP Tools on yoro profile)

| Command | Description |
|---|---|
| `connect_account` | OAuth2 flow -> X account binding |
| `disconnect_account` | Remove X account |
| `sync_profile` | Collection Job for profile + tweets + followers sync |
| `list_followers` | List followers for connected X account |
| `list_following` | List following for connected X account |
| `get_user` | Get X user profile by username |
| `search_users` | Search X users |
| `list_tweets` | List tweets for user |
| `get_tweet` | Get tweet by ID |
| `list_lists` | List X Lists for user |
| `get_timeline` | Get home timeline |
| `get_profile` | Get X profile summary |

## Build & Deploy

```bash
cd 60-apps/etzhayyim-project-x/wasm/etzhayyim-wasm-x-xw1tt3r1
GOROOT=$(/opt/homebrew/opt/go@1.25/bin/go env GOROOT) PATH="/opt/homebrew/opt/go@1.25/bin:$PATH" etzhayyim build
etzhayyim deploy
```
