# yorishiro_arxiv

Pregel cell for the **arxiv** yorishiro (kami: `arxiv.org`).

Per **ADR-2605211900** (yorishiro external-actor bridge) +
**ADR-2605202200** (kotoba-kotodama cell.py runtime contract).

Generator: `@etzhayyim/yorishiro` v0.1.0
Transport: `openapi-v3`
Base URL : `http://export.arxiv.org/api`
Charter purposes: `grant`

## Ops

| Op | HTTP | Summary |
|---|---|---|
| `searchPapers` | `GET` `/query` | Search arXiv papers |

## Lexicon SSoT

`00-contracts/lexicons/ai/etzhayyim/yorishiro/arxiv/<op>.json`

## MCP exposure

`20-actors/kotoba-kotodama/mcp/yorishiro-arxiv-mcp/` (stdio + Streamable HTTP)

## Regenerate

```bash
yorishiro regen arxiv
```

Hand edits to `cell.py` are overwritten on regen — extend the kami
OpenAPI spec at `00-contracts/openapi/kami/arxiv.openapi.json` instead.

## Cell-runner registration

The cells.toml fragment `cells.toml.fragment` in this directory is the
authoritative entry for the Murakumo cell-runner. Append it to
`50-infra/cluster/murakumo/cell-runner/cells.toml` once the cell-runner
supports `20-actors/kotoba-kotodama/cells/yorishiro_*/cell.py` discovery
(ADR-2605202200 wiring).

## Claude Desktop / Codex CLI

```json
{
  "mcpServers": {
    "etzhayyim-yorishiro-arxiv": {
      "command": "node",
      "args": ["/ABSOLUTE/PATH/TO/repo/20-actors/kotoba-kotodama/mcp/yorishiro-arxiv-mcp/src/cli.ts"],
      "env": { "YORISHIRO_ARXIV_BASE_URL": "http://export.arxiv.org/api" }
    }
  }
}
```

Use `tsx` rather than `node` if the host does not auto-resolve `.ts`.
