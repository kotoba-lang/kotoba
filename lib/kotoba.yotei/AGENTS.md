> **DEPRECATED**: Actor migrated to `orgs/etzhayyim/com-etzhayyim-yotei/actor-manifest.jsonld` (T1 MCP-Compose). This project wasm/*/src/app.ts is retained as T3 fallback only.

# etzhayyim-project-yotei

Calendar scheduling & availability coordination — Calendly-like AI Agent。

**URL**: `https://yotei.etzhayyim.com`
**performerType**: `service`
**Primary DID**: `did:web:yotei.etzhayyim.com`

## Architecture

**Convo Integration**: yotei commands (`CreateEvent`, `SetAvailability`, `BookSlot` 等) は他 agent の DM convo 内から MCP tool calling で呼び出し可能。ops.etzhayyim.com 等の PM agent がスケジュール調整を yotei に委譲。

### 1 Calendar = 1 Path-Based DID

各カレンダーオーナー (人間 or AI Agent) は path-based DID としてカレンダーを持ち、yoro.etzhayyim.com 上で予約ページを公開。

| 概念 | 実装 |
|---|---|
| **Calendar** | `DIDCreate("calendar:{id}", document)` → `did:web:yotei.etzhayyim.com:calendar:{id}` |
| **Availability** | `ComAtprotoRepoCreateRecord("availability", payload)` → yata graph (`:Availability` node) |
| **Event** | `ComAtprotoRepoCreateRecord("event", payload)` → yata graph (`:Event` node) |
| **Booking** | `ComAtprotoRepoCreateRecord("booking", payload)` → graph `(:Calendar)-[:HAS_BOOKING]->(:Booking)` |
| **Social Announce** | `AppBskyFeedPost(did, text)` で予約確定・リマインダーを timeline に投稿 |

### Convo-Based Scheduling (PRIMARY)

**yoro の compose ボタンから yotei AI agent との DM convo を開く。** 自然言語またはスラッシュコマンドでスケジュール調整。

```
yoro.etzhayyim.com FAB tap
  → createDM(did:web:yotei.etzhayyim.com)
  → /messages/{convoId}
  → user: "/available mon-fri 10:00-17:00"
  → yotei agent: "Availability set: Mon-Fri 10:00-17:00 JST"
  → user: "/book @alice.etzhayyim.com 30min next week"
  → yotei agent: "Proposed slots: ..."
```

**Commands:**
- `/available <schedule>` — set availability windows
- `/book <peer> <duration> [preference]` — propose meeting
- `/events [date-range]` — list upcoming events
- `/cancel <event_id>` — cancel event
- `/reschedule <event_id> <new_time>` — reschedule
- `/link` — get public booking page URL

## UI Architecture (Hono + Svelte CSR)

**uiType: appview** — `unyrsfan.etzhayyim.com` / `yotei.etzhayyim.com` で独自 UI を持つ。

| Layer | Tech | Path |
|---|---|---|
| **Host** | Hono (`@etzhayyim/kotodama-host-sdk`) | `src/app.ts` — XRPC + `/embed` route |
| **Client** | Svelte 5 + Vite 6 + Tailwind | `svelte/` — CSR SPA |
| **Layout** | `SuperAppLayout` (mobile-first 600px) | 5-tab SuperApp shell |
| **Design** | `@etzhayyim/design-system` | UIKit components |

### Pages

| Route (client) | Component | Description |
|---|---|---|
| Calendar | `CalendarView.svelte` | Weekly grid: availability slots + events overlay |
| Bookings | `BookingPage.svelte` | Public booking form + booking list with status |
| Events | `EventList.svelte` | Upcoming events list with cancel action |

### Embed

`/embed` Hono route → yoro profile iframe embed。`postMessage({type:'etzhayyim:embed:ready', nanoid:'unyrsfan'})` で完了通知。

### Booking Flow

```
Requester → Invoke("did:web:yotei.etzhayyim.com", "proposeBooking", params)
  → yotei checks availability (G("Availability").Match(...).Query())
  → available slots returned
  → Requester confirms slot
  → ComAtprotoRepoCreateRecord("booking", payload) (Tier 2: domain)
  → AppBskyFeedPost(calendarDID, "Meeting confirmed: ...") (Tier 1: social)
  → WprotoConvoCreateDm(peerDID, "booking-confirmation", payload) (notification)
```

### Graph Schema

```sql
(:Calendar {id, owner_did, timezone, org_id, user_id, actor_id, created_at})
(:Availability {id, calendar_id, day_of_week, start_time, end_time, recurring, org_id, user_id, actor_id, created_at})
(:Event {id, calendar_id, title, start_at, end_at, location, description, status, org_id, user_id, actor_id, created_at})
(:Booking {id, event_id, requester_did, responder_did, duration_min, status, proposed_slots, confirmed_slot, org_id, user_id, actor_id, created_at})

(:Calendar)-[:HAS_AVAILABILITY]->(:Availability)
(:Calendar)-[:HAS_EVENT]->(:Event)
(:Calendar)-[:HAS_BOOKING]->(:Booking)
(:Booking)-[:FOR_EVENT]->(:Event)
```

## Cross-App Integration

| App | Integration |
|---|---|
| **ops** | PM agent が yotei を Invoke してミーティング設定 |
| **shinka** | heartbeat でリマインダー投稿 |
| **society6** | constituent availability → governance meeting scheduling |
