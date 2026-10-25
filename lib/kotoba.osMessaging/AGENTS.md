# etzhayyim-project-os-messaging — Multi-Platform Messaging Bridge

> **T2 Logical Actor**: Manifest-driven (`20-actors/os-messaging/actor-manifest.jsonld`). Path F Phase 3.

`os-messaging.etzhayyim.com` (nanoid: `0sm3sg01`) — 9 platform bridges (Discord/Telegram/Slack/LINE/WhatsApp/Matrix/MS Teams/WeChat/KakaoTalk → etzhayyim agent network via W Protocol convo).

## Open-channel collection

LINE/Telegram public open-channel collection is owned by LangServer/Python worker, separate from the webhook bridge.

- BPMN: `etzhayyim-root/00-contracts/bpmn/com/etzhayyim/os-messaging/crawlOpenChannels.bpmn` (`os_messaging_crawl_open_channels`, timer `R/PT6H`)
- Python tasks: `osMessaging.openChannels.queueSeedRuns` and `osMessaging.openChannels.processQueue` in `40-engine/kotoba/crates/kotoba-kotodama/py/src/kotodama/primitives/os_messaging_open_channels.py`
- Writes: direct `RW_URL` / `sync_cursor()` inserts into `vertex_os_messaging_open_channel`, `vertex_os_messaging_open_message`, and `vertex_os_messaging_open_scraper_run`
- Existing Telegram/LINE webhook commands remain the consented inbound messaging path; they are not the public crawler.

## Lexicons
`osMessaging/` (2 files): registerBridge, listBridges.

## Bridge mode
5 bridgeMode: read-only / read-write / agent-only / human-only / fully-bridged
4 e2eMode: client-signal / server-assisted / platform-native / plaintext

## cross-actor
- `yoro` — convo backbone (W Protocol)
- agent loop ④ chat.bsky.convo.sendMessage 経由で agentInfer 合流 (per Path F)

## Governance
- per-platform ToS compliance
- E2E degradation warning (Signal/Matrix → Discord/Slack 時)
- cross-platform message idempotency (origin message-id tagging)
