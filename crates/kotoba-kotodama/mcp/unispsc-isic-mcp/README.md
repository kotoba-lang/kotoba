# @etzhayyim/unispsc-isic-mcp

MCP (Model Context Protocol) server exposing the UNSPSC + ISIC LangGraph
Pregel agent fleets as 9 tools, per **ADR-2605180900 Phase 8**.

Wraps the per-taxonomy actor wrappers from
`@etzhayyim/kotoba-kotodama-host-sdk/langserver-actor` (Phase 6) and re-emits them
through the official `@modelcontextprotocol/sdk`. The same tool surface
serves both stdio transport (desktop hosts like Claude Desktop / Codex
CLI / Cursor) and Streamable HTTP transport (in-cluster service mesh).

## Tools

| Tool                            | Purpose                                                                |
|---------------------------------|------------------------------------------------------------------------|
| `classify_unispsc`              | Free text → top-K UNSPSC commodity codes                               |
| `invoke_unispsc_agent`          | Invoke the LangGraph agent for a specific UNSPSC code                  |
| `list_unispsc_agents`           | Paged listing of UNSPSC registry                                       |
| `unispsc_health`                | UNSPSC langserver health probe                                         |
| `classify_isic`                 | Free text → top-K ISIC Rev. 4 classes                                  |
| `classify_isic_hierarchical`    | Section → division → group → class, stop at any level                  |
| `invoke_isic_agent`             | Invoke the LangGraph agent for a specific 4-digit ISIC class           |
| `list_isic_agents`              | Paged listing of ISIC registry                                         |
| `isic_health`                   | ISIC langserver health probe                                           |

All tool input schemas are zod 4 schemas that mirror the lexicons under
`00-contracts/lexicons/com/etzhayyim/apps/{unispsc,isic}/` — so XRPC, MCP, and
in-process actor callers share identical input/output shapes.

## Stdio (desktop)

After `pnpm install` + build, the package exposes a `unispsc-isic-mcp`
binary that speaks MCP over stdio. Example Claude Desktop config:

```json
{
  "mcpServers": {
    "etzhayyim-unispsc-isic": {
      "command": "node",
      "args": ["/path/to/repo/20-actors/kotoba-kotodama/mcp/unispsc-isic-mcp/src/cli.ts"],
      "env": {
        "LG_UNISPSC_ENDPOINT": "https://lg-open-unispsc.etzhayyim.com",
        "LG_ISIC_ENDPOINT": "https://lg-open-isic.etzhayyim.com"
      }
    }
  }
}
```

If `LG_UNISPSC_ENDPOINT` / `LG_ISIC_ENDPOINT` are unset, the CLI falls
back to the in-cluster Service DNS used by the Kotodama actor wrapper
(`http://lg-open-{unispsc,isic}.lg-open-{unispsc,isic}.svc:80`). Useful
only when the MCP host is itself running inside the cluster.

## Programmatic (in-cluster HTTP transport)

```ts
import {
  createUnispscIsicMcpServer,
} from "@etzhayyim/unispsc-isic-mcp";
import {
  createIsicActor,
  createUnispscActor,
} from "@etzhayyim/kotoba-kotodama-host-sdk";
import { StreamableHTTPServerTransport } from "@modelcontextprotocol/sdk/server/streamableHttp.js";

const unispsc = createUnispscActor({ endpoint: process.env.LG_UNISPSC_ENDPOINT! });
const isic = createIsicActor({ endpoint: process.env.LG_ISIC_ENDPOINT! });

const server = createUnispscIsicMcpServer({ actors: { unispsc, isic } });
const transport = new StreamableHTTPServerTransport({ sessionIdGenerator: () => crypto.randomUUID() });
await server.connect(transport);

// then route HTTP POST /mcp -> transport.handleRequest(req, res)
```

## Tests

```
$ vitest run 20-actors/kotoba-kotodama/mcp/unispsc-isic-mcp/test/
Test Files  2 passed (2)
     Tests  25 passed (25)
```

`tsc --strict -p tsconfig.json` runs clean.

## See also

- `00-contracts/lexicons/com/etzhayyim/apps/unispsc/*.json` — Lexicon contracts (Phase 1)
- `00-contracts/lexicons/com/etzhayyim/apps/isic/*.json` — Lexicon contracts (Phase 1)
- `50-infra/k8s/lg-open-unispsc/` — UNSPSC langserver pod (Phase 4)
- `50-infra/k8s/lg-open-isic/` — ISIC langserver pod (Phase 5)
- `20-actors/kotoba-kotodama/sdk/kotoba-kotodama-host-sdk/src/langserver-actor.ts` — Kotodama actor wrapper (Phase 6)
- ADR-2605180900 (`90-docs/adr/`) — full architecture

## Substrate rules honored

- **RW-free** (ADR-2605172000): no centralized DB; MCP server is stateless
  beyond the per-process actor connection.
- **Lexicon-first**: the 9 tool input schemas match the 9 lexicons authored
  in Phase 1.
- **Legacy NSID retention** (ADR-2605172900): protocol identifiers under
  the legacy `com.etzhayyim.*` namespace preserved.
