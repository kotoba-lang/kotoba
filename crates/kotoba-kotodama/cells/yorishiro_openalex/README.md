# yorishiro_openalex

Pregel cell for the **openalex** yorishiro (kami: `api.openalex.org`).

Per **ADR-2605211900** (yorishiro external-actor bridge) +
**ADR-2605202200** (kotoba-kotodama cell.py runtime contract).

Generator: `@etzhayyim/yorishiro` v0.1.0
Transport: `openapi-v3`
Base URL : `https://api.openalex.org`
Charter purposes: `grant, kisha`

## Ops

| Op | HTTP | Summary |
|---|---|---|
| `searchWorks` | `GET` `/works` | Search OpenAlex works (papers, preprints) |
| `searchAuthors` | `GET` `/authors` | Search OpenAlex authors |

## Lexicon SSoT

`00-contracts/lexicons/ai/etzhayyim/yorishiro/openalex/<op>.json`

## MCP exposure

`20-actors/kotoba-kotodama/mcp/yorishiro-openalex-mcp/` (stdio + Streamable HTTP)

## Regenerate

```bash
yorishiro regen openalex
```

Hand edits to `cell.py` are overwritten on regen — extend the kami
OpenAPI spec at `00-contracts/openapi/kami/openalex.openapi.json` instead.

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
    "etzhayyim-yorishiro-openalex": {
      "command": "node",
      "args": ["/ABSOLUTE/PATH/TO/repo/20-actors/kotoba-kotodama/mcp/yorishiro-openalex-mcp/src/cli.ts"],
      "env": { "YORISHIRO_OPENALEX_BASE_URL": "https://api.openalex.org" }
    }
  }
}
```

Use `tsx` rather than `node` if the host does not auto-resolve `.ts`.
