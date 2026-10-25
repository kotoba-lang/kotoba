# etzhayyim-project-cloudflare-browser-render — CF Browser Rendering backend

`did:web:cloudflare-browser-render.etzhayyim.com` / nanoid `cfbr0w53`.
`com.etzhayyim.apps.playwright` の `target=cf-browser` 実体。CF Workers
`browser` binding + `@cloudflare/playwright` で serverless Playwright。

## Scope

- playwright actor の substrate (直接 caller にしない、playwright 経由推奨)
- Durable Object で session affinity (同一 sessionId が同 DO に届くよう routing)
- credential は receive しない — playwright が解決済 value を渡す
- 1 session = 1 DO instance、TTL 5 分 (CF cost 最小化)

## XRPC (4 methods)

| method | 内容 |
|---|---|
| `createSession` | `{options}` → `{sessionId, durableObjectId}` |
| `closeSession` | `{sessionId}` |
| `renderPage` | `{url, output: 'html'\|'png'\|'pdf'}` → `{artifactCid}` (session 不要の 1-shot) |
| `dispatchOp` | `{sessionId, op, args}` → playwright op と同形 (goto/fill/click/scrape/...) |

## Binding (wrangler)

```jsonc
"browser": { "binding": "BROWSER" }
```

Durable Object: `BrowserSessionDO` が chromium instance を保持。

## Cost

- CF Browser Rendering 分課金。1 session max 5 min、ops 100 回上限で hard close。
- `target=local` の方が安いので、shiharai 等は local 優先。cf-browser は CI / Mac 不在時用。

## Phase

- **Phase 1**: `createSession` / `closeSession` / `dispatchOp` stub (1-shot emulation)
- **Phase 2**: Durable Object 実装で真の session affinity
- **Phase 3**: `@cloudflare/playwright` API 網羅
