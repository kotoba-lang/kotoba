# Registry maintenance

Use this repository as the canonical Kotoba extension discovery registry.
Read [llms.txt](llms.txt) and [ADR-0001](docs/adr/0001-kotoba-extension-registry.md)
before adding or consuming catalog entries. The public index is
https://raw.githubusercontent.com/kotoba-lang/kotoba-registry/main/index.json.

- Preserve the Hermes `index.json`, `SKILL.md` and MCP `manifest.json` formats.
- Generate `index.json` with `node scripts/build-index.mjs`; use `--check` before publishing.
- Preserve immutable upstream source references and verify snapshot digests.
- MCP entries declare connection configuration; credentials never belong here.
- Extension catalog publication is separate from Kotoba package admission and execution.
- Keep repositories under `github/<org>/<repo>`, worktrees under `github/wt/<agent>/<task>`, and scratch under `github/workspaces/<agent>/<task>`.
