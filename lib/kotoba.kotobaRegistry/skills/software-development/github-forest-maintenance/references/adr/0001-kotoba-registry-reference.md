# ADR-0001: Reference the public Kotoba extension registry

Status: accepted — 2026-10-07

The owner requested one public registry and common references from Markdown,
ADRs and agent discovery files. Use
[`kotoba-lang/kotoba-registry`](https://github.com/kotoba-lang/kotoba-registry)
as the extension discovery authority, following its
[ownership ADR](https://github.com/kotoba-lang/kotoba-registry/blob/main/docs/adr/0001-kotoba-extension-registry.md).

README, AGENTS.md, llms.txt, the forest command reference and shared skill point
to that repository and its generated index. Catalog entry files must be read
from one immutable commit and verified against the Hermes folder checksum.
The catalog carries installable skill material and MCP connection metadata;
it does not confer permissions or act as a signed Kotoba language package lock.

This repository retains command implementation, client installation, repository
registration and west/genpon authority. Publishing a catalog entry does not
switch client Discover endpoints or advance a west pin. Keep those operations
explicit and verify their results through the existing guarded command.
