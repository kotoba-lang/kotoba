# ADR-0001: Kotoba extension discovery registry

Status: accepted — 2026-10-07

## Context

Forest maintenance has a shared CLI, MCP and skill used by Hermes, Claude and
Codex. Their discoverable definitions need a public home and a common reference
that does not depend on one machine's agent settings. The owner requested the
Hermes Registry storage format and authorized a public repository.

## Decision

[`kotoba-lang/kotoba-registry`](https://github.com/kotoba-lang/kotoba-registry)
owns the public extension catalog. Its generated
[`index.json`](https://raw.githubusercontent.com/kotoba-lang/kotoba-registry/main/index.json)
indexes `skills/<category>/<id>/SKILL.md` and `mcp/<id>/manifest.json` using the
Hermes Registry schema and checksum convention. `llms.txt` is the short agent
entry point; `llms-full.txt` provides the complete consumption contract.

Consumers fetch one immutable registry commit, validate every selected folder
checksum over those same bytes, then inspect the skill or MCP configuration.
A mutable `main/index.json` is discovery, not an immutable execution identity.
MCP connection definitions refer to installed runtime commands; a definition's
presence never grants permissions or installs missing dependencies.

Ownership remains explicit:

| Surface | Authority |
|---|---|
| extension catalog, published skills and MCP definitions | `kotoba-lang/kotoba-registry` |
| forest command implementation and local installation | `com-junkawasaki/west-manifest` |
| repository registration, checkout paths, pins and signed genpon | `com-junkawasaki/west-manifest` |
| signed CID-pinned language package admission | Kotoba's language package contract and registry |
| credentials, sessions and runtime approvals | the existing agent/application authority |

Source snapshots carry an upstream commit and exact digests in `provenance.json`.
Catalog documentation and skill adaptations may evolve while preserving that
runtime source identity. Rebuild and verify `index.json` whenever entry files
change. Publish only reviewed files; agent settings, credentials, databases,
sessions and audit output stay outside this repository.

## Consequences

README, agent instructions, ADRs and LLM discovery files link to the same catalog.
They describe installation and verification without copying catalog entries into
another authority. Existing applications need a configured consumer before their
Discover screens use this endpoint; documentation publication does not switch
runtime behavior. This catalog does not claim Kotoba Wasm admission, dual-signature
package publication, deployment or distributed availability.
