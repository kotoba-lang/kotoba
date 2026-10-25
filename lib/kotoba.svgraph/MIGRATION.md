# Migrating to SVGraph TypeScript

SVGraph is maintained as a TypeScript-only browser/npm project:

- Repository: <https://github.com/com-junkawasaki/svgraph>
- Browser editor: <https://com-junkawasaki.github.io/svgraph/>
- npm package: `@com-junkawasaki/svgraph`

This repository contains the TypeScript browser runtime, GitHub Pages editor, npm package, Node CLI shim, generated Pages artifacts, and browser-side SVGraph/PPTX conversion code.

## Name Mapping

| Legacy surface | TypeScript SVGraph surface |
| --- | --- |
| `com-junkawasaki/drawingml-svg` web/editor code | `com-junkawasaki/svgraph` |
| `com-junkawasaki/svgraph` browser package | `@com-junkawasaki/svgraph` |
| legacy Pages editor | <https://com-junkawasaki.github.io/svgraph/> |
| browser CLI executable | `svgraph` |
| browser SVGraph API | `buildSVGraph()` |
| browser presentation API | `svgToPptx()` and `buildSVGraphSidecar()` |

Python imports, Python CLI aliases, wheel/sdist packaging, and compatibility wrappers have been removed from this repository. New integrations should use the TypeScript API, browser editor, or `svgraph` Node CLI from `com-junkawasaki/svgraph`.

## Install

The browser npm package is published through GitHub Packages:

```bash
npm install @com-junkawasaki/svgraph --registry=https://npm.pkg.github.com
```

## CLI

The package exposes a TypeScript/browser-runtime CLI with a Node XML DOM shim:

```bash
npm exec --registry=https://npm.pkg.github.com --package @com-junkawasaki/svgraph -- svgraph svg2dml input.svg -o shape.xml
npm exec --registry=https://npm.pkg.github.com --package @com-junkawasaki/svgraph -- svgraph dml2svg shape.xml -o shape.svg
npm exec --registry=https://npm.pkg.github.com --package @com-junkawasaki/svgraph -- svgraph svg2pptx deck.svg -o deck.pptx
npm exec --registry=https://npm.pkg.github.com --package @com-junkawasaki/svgraph -- svgraph svgraph deck.svg -o deck.svgraph.json
npm exec --registry=https://npm.pkg.github.com --package @com-junkawasaki/svgraph -- svgraph svgraph-presentation deck.svg -o deck.presentation.json
npm exec --registry=https://npm.pkg.github.com --package @com-junkawasaki/svgraph -- svgraph analyze deck.svg
```

## Verification

Run these checks before publishing or changing generated Pages artifacts:

```bash
npm ci
npm run check:web
npm run build:web
npm run check:package
git diff --exit-code docs/app.js
git diff --exit-code docs/app.d.ts
npm pack --dry-run --json
```

The package and CI checks validate that public links, package metadata, generated browser artifacts, CLI smoke checks, and packaged documentation stay on TypeScript SVGraph naming.
