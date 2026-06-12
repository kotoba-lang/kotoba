# yorishiro_fueleconomy

Pregel cell for the **fueleconomy** yorishiro (kami: `www.fueleconomy.gov`).

Per **ADR-2605211900** (yorishiro external-actor bridge) +
**ADR-2605202200** (kotoba-kotodama cell.py runtime contract).

Generator: `@etzhayyim/yorishiro` v0.1.0
Transport: `openapi-v3`
Base URL : `https://www.fueleconomy.gov`
Charter purposes: `grant`

## Ops

| Op | HTTP | Summary |
|---|---|---|
| `downloadVehiclesCsv` | `GET` `/feg/epadata/vehicles.csv` | Download the full EPA vehicles dataset as CSV |

## Lexicon SSoT

`00-contracts/lexicons/ai/etzhayyim/yorishiro/fueleconomy/<op>.json`

## MCP exposure

`20-actors/kotoba-kotodama/mcp/yorishiro-fueleconomy-mcp/` (stdio + Streamable HTTP)

## Regenerate

```bash
yorishiro regen fueleconomy
```

Hand edits to `cell.py` are overwritten on regen — extend the kami
OpenAPI spec at `00-contracts/openapi/kami/fueleconomy.openapi.json` instead.

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
    "etzhayyim-yorishiro-fueleconomy": {
      "command": "node",
      "args": ["/ABSOLUTE/PATH/TO/repo/20-actors/kotoba-kotodama/mcp/yorishiro-fueleconomy-mcp/src/cli.ts"],
      "env": { "YORISHIRO_FUELECONOMY_BASE_URL": "https://www.fueleconomy.gov" }
    }
  }
}
```

Use `tsx` rather than `node` if the host does not auto-resolve `.ts`.
