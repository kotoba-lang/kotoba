# Changelog

All notable changes to this project are documented here.

This project follows a simple, human-readable changelog. Until the project reaches a stable release cadence, unreleased changes are collected under `Unreleased`.

## Unreleased

- Consolidated SVGraph into the `com-junkawasaki/svgraph` monorepo as the only active TypeScript browser/npm implementation.
- Added fixture-based maturity tests for SVGraph metadata, dependencies, presentation state, editable connectors, DrawingML import, PPTX package parts, native table XML, source recovery, sidecar JSON, and Office Causal JSONL.
- Removed the Python package source, Python compatibility wrappers, Python examples, Python packaging metadata, and Python test suite from the monorepo.
- Moved the current browser editor, Node CLI shim, generated Pages artifacts, Office Causal export, and npm package configuration into `@com-junkawasaki/svgraph`.
- Updated project documentation, release guidance, CI, Pages, Dependabot, issue templates, and package metadata for the TS-only repository.
