# Release checklist

Use this checklist when publishing a new `@com-junkawasaki/svgraph` release from `com-junkawasaki/svgraph`.

## Before tagging

- Confirm `CHANGELOG.md` has a dated section for the release and an empty `Unreleased` section for the next cycle.
- Confirm `package.json` and `package-lock.json` have the intended version.
- Confirm the public GitHub repository metadata is the canonical TypeScript package location:

```bash
gh repo view com-junkawasaki/svgraph --json nameWithOwner,description,isPrivate,visibility,url,homepageUrl,defaultBranchRef,repositoryTopics,licenseInfo
```

Expected values:

```text
nameWithOwner: com-junkawasaki/svgraph
description: TypeScript browser and npm package for SVGraph SVG presentation IR conversion
isPrivate: false
visibility: PUBLIC
url: https://github.com/com-junkawasaki/svgraph
homepageUrl: https://com-junkawasaki.github.io/svgraph/
defaultBranchRef.name: main
repositoryTopics: drawingml, npm, ooxml, pptx, presentationml, svg, svgraph, typescript, web-editor
licenseInfo.key: mit
licenseInfo.name: MIT License
```

- Smoke the published Pages site after deployment:

```bash
node --input-type=module <<'JS'
for (const url of [
  "https://github.com/com-junkawasaki/svgraph",
  "https://github.com/com-junkawasaki/svgraph/issues",
  "https://github.com/com-junkawasaki/svgraph/actions/workflows/ci.yml",
  "https://com-junkawasaki.github.io/svgraph/",
  "https://com-junkawasaki.github.io/svgraph/app.js",
]) {
  const response = await fetch(url);
  if (!response.ok) throw new Error(`${url}: ${response.status}`);
}
const html = await (await fetch("https://com-junkawasaki.github.io/svgraph/")).text();
const appJs = await (await fetch("https://com-junkawasaki.github.io/svgraph/app.js")).text();
for (const expected of [
  "<title>SVGraph Editor</title>",
  'property="og:url" content="https://com-junkawasaki.github.io/svgraph/"',
  '<a class="btn" href="https://github.com/com-junkawasaki/svgraph">GitHub</a>',
  '<a class="btn" href="https://github.com/com-junkawasaki/svgraph/issues">Issues</a>',
  "Download SVG",
  "Download SVGraph",
  "Download Sidecar",
]) {
  if (!html.includes(expected)) throw new Error(expected);
}
for (const expected of [
  "SVGraph",
  "downloadSVGraphBtn",
  "svgraph-source.svg",
  "svgraph-sidecar.json",
  "svgraph-web.pptx",
]) {
  if (!appJs.includes(expected)) throw new Error(expected);
}
JS
```

- Run local checks:

```bash
npm ci
npm run check:web
npm run build:web
npm run test:maturity
npm run check:package
git diff --exit-code docs/app.js
git diff --exit-code docs/app.d.ts
npm pack --dry-run --json
```

- Smoke the package CLI:

```bash
node ./bin/svgraph.mjs --version
node ./bin/svgraph.mjs svg2dml examples/sample.svg > tmp/release-smoke.xml
node ./bin/svgraph.mjs dml2svg tmp/release-smoke.xml > tmp/release-smoke.svg
node ./bin/svgraph.mjs svg2pptx examples/svgraph.svg -o tmp/release-smoke.pptx
node ./bin/svgraph.mjs svgraph examples/svgraph.svg > tmp/release-svgraph.json
node ./bin/svgraph.mjs svgraph-presentation examples/svgraph.svg > tmp/release-presentation.json
node ./bin/svgraph.mjs analyze examples/sample.svg > tmp/release-coverage.json
```

- Verify package metadata:

```bash
node --input-type=module <<'JS'
import { readFile } from "node:fs/promises";
const pkg = JSON.parse(await readFile("package.json", "utf8"));
const lock = JSON.parse(await readFile("package-lock.json", "utf8"));
if (pkg.name !== "@com-junkawasaki/svgraph") throw new Error(pkg.name);
if (pkg.homepage !== "https://com-junkawasaki.github.io/svgraph/") throw new Error(pkg.homepage);
if (pkg.repository.url !== "git+https://github.com/com-junkawasaki/svgraph.git") throw new Error(pkg.repository.url);
if (pkg.bugs.url !== "https://github.com/com-junkawasaki/svgraph/issues") throw new Error(pkg.bugs.url);
if (pkg.version !== lock.version || pkg.version !== lock.packages[""].version) throw new Error("version mismatch");
if (lock.name !== pkg.name || lock.packages[""].name !== pkg.name) throw new Error("lock name mismatch");
if (pkg.publishConfig.registry !== "https://npm.pkg.github.com") throw new Error("registry mismatch");
if (pkg.publishConfig.access !== "public") throw new Error("access mismatch");
for (const name of ["buildSVGraph", "buildSVGraphSidecar", "svgToDrawingMl", "drawingMlToSvg", "svgToPptx", "initSVGraphEditor"]) {
  const mod = await import("./docs/app.js");
  if (typeof mod[name] !== "function") throw new Error(name);
}
JS
```

## Publishing

Publish from the `Publish npm package` workflow, or from an authenticated local npm session:

```bash
printf '@com-junkawasaki:registry=https://npm.pkg.github.com\n//npm.pkg.github.com/:_authToken=%s\n' "$GITHUB_TOKEN" > .npmrc
npm publish --registry=https://npm.pkg.github.com
rm -f .npmrc
```

Verify GitHub Packages:

```bash
gh api /users/com-junkawasaki/packages/npm/svgraph/versions --jq '.[0:5][] | [.name,.created_at] | @tsv'
```
