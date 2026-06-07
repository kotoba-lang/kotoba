# yorishiro_huggingface-inference

Pregel cell for the **huggingface-inference** yorishiro (kami: `api-inference.huggingface.co`).

Per **ADR-2605211900** (yorishiro external-actor bridge) +
**ADR-2605202200** (kotoba-kotodama cell.py runtime contract).

Generator: `@etzhayyim/yorishiro` v0.1.0
Transport: `openapi-v3`
Base URL : `https://api-inference.huggingface.co`
Charter purposes: `grant`

## Ops

| Op | HTTP | Summary |
|---|---|---|
| `extractFeatures` | `POST` `/pipeline/feature-extraction/{model_id}` | Run a feature-extraction (embedding) pipeline against a model |

## Lexicon SSoT

`00-contracts/lexicons/ai/etzhayyim/yorishiro/huggingface-inference/<op>.json`

## MCP exposure

`20-actors/kotoba-kotodama/mcp/yorishiro-huggingface-inference-mcp/` (stdio + Streamable HTTP)

## Regenerate

```bash
yorishiro regen huggingface-inference
```

Hand edits to `cell.py` are overwritten on regen — extend the kami
OpenAPI spec at `00-contracts/openapi/kami/huggingface-inference.openapi.json` instead.

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
    "etzhayyim-yorishiro-huggingface-inference": {
      "command": "node",
      "args": ["/ABSOLUTE/PATH/TO/repo/20-actors/kotoba-kotodama/mcp/yorishiro-huggingface-inference-mcp/src/cli.ts"],
      "env": { "YORISHIRO_HUGGINGFACE-INFERENCE_BASE_URL": "https://api-inference.huggingface.co" }
    }
  }
}
```

Use `tsx` rather than `node` if the host does not auto-resolve `.ts`.
