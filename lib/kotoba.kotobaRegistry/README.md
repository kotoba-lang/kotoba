# Kotoba Registry

Installable skills and MCP definitions for Kotoba users, stored in the same
catalog format as [Hermes Registry](https://github.com/hermesonehq/hermes-registry).

`index.json` is the generated discovery catalog. Skills contain `SKILL.md`;
MCP entries contain `manifest.json`. Checksums use the Hermes algorithm:
SHA-256 over sorted relative file paths and bytes, each followed by a NUL byte.

Start with [llms.txt](llms.txt) for agent discovery, [llms-full.txt](llms-full.txt)
for the installation and verification contract, and
[ADR-0001](docs/adr/0001-kotoba-extension-registry.md) for ownership and publication.

## Registered entries

- `github-forest-maintenance`: preserve WIP and organize repositories,
  worktrees and agent workspaces through the guarded maintenance command.
- `github-forest`: the same command's nine stdio MCP tools.

The command implementation remains owned by
[`com-junkawasaki/west-manifest`](https://github.com/com-junkawasaki/west-manifest).
The MCP entry points to the installed `forest-maintenance` command. Its `server/`
directory preserves a source snapshot for inspection; it is not an independent
installation of the complete west-manifest repository.

## Install on the existing GitHub forest

First ensure the owning repository and its documented dependencies are installed.
The CLI is available at `github/com-junkawasaki/west-manifest/bin/forest-maintenance`.
Put this executable on PATH, or use its absolute path as the MCP command.
Verify `forest-maintenance help` before configuring the MCP.

Copy `skills/software-development/github-forest-maintenance/` into the client's
skill directory, including its `references/` and `agents/` directories.
For MCP clients, use:

```json
{
  "command": "forest-maintenance",
  "args": ["mcp"]
}
```

For Hermes this connection belongs under `mcp_servers.github-forest` in the
profile's existing config. Codex and Claude use their native MCP configuration.
The owning repository's `scripts/install-forest-clients.py` performs the local
installation with preservation of unrelated settings. Read the bundled command
reference before using apply, pin or register operations.

Public catalog endpoint:
`https://raw.githubusercontent.com/kotoba-lang/kotoba-registry/main/index.json`.
Existing applications require configuration or a consumer change to use this
catalog; publication alone does not change their Discover source.

## Maintain the catalog

```sh
node scripts/build-index.mjs
node scripts/build-index.mjs --check
```

Add skills under `skills/<category>/<id>/SKILL.md` and MCP entries under
`mcp/<id>/manifest.json`, then regenerate the catalog. Do not add application
credentials, profile configuration, session databases or machine audit reports.
`provenance.json` records the immutable source commit and snapshot digests.
Skill frontmatter supplies `metadata` as one JSON flow-map line, with
`hermes.version`, `hermes.author`, `hermes.source` and `hermes.compatibility`.
This is valid YAML and matches Hermes's metadata namespace. The generator
requires these fields instead of inventing source or release information.

This is an extension discovery registry. The signed, CID-pinned Kotoba language
package registry remains a separate contract; these Node/CLI entries do not
claim Kotoba Wasm execution, package admission or distributed availability.

No additional license grant is made for the copied implementation. Retain the
source repository's provenance and applicable permissions when redistributing.
