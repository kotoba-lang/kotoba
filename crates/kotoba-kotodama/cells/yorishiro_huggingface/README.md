# yorishiro_huggingface

Pregel cell for the **huggingface** yorishiro (kami: `huggingface.co`).

Per **ADR-2605211900** (yorishiro external-actor bridge) +
**ADR-2605202200** (kotoba-kotodama cell.py runtime contract).

Generator: `@etzhayyim/yorishiro` v0.1.0
Transport: `openapi-v3`
Base URL : `https://huggingface.co`
Charter purposes: `grant`

## Ops

| Op | HTTP | Summary |
|---|---|---|
| `searchModels` | `GET` `/api/models` | Search HuggingFace Hub models |
| `searchDatasets` | `GET` `/api/datasets` | Search HuggingFace Hub datasets |

## Lexicon SSoT

`00-contracts/lexicons/ai/etzhayyim/yorishiro/huggingface/<op>.json`

## MCP exposure

`20-actors/kotoba-kotodama/mcp/yorishiro-huggingface-mcp/` (stdio + Streamable HTTP)

## Regenerate

```bash
yorishiro regen huggingface
```

Hand edits to `cell.py` are overwritten on regen — extend the kami
OpenAPI spec at `00-contracts/openapi/kami/huggingface.openapi.json` instead.

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
    "etzhayyim-yorishiro-huggingface": {
      "command": "node",
      "args": ["/ABSOLUTE/PATH/TO/repo/20-actors/kotoba-kotodama/mcp/yorishiro-huggingface-mcp/src/cli.ts"],
      "env": { "YORISHIRO_HUGGINGFACE_BASE_URL": "https://huggingface.co" }
    }
  }
}
```

Use `tsx` rather than `node` if the host does not auto-resolve `.ts`.
