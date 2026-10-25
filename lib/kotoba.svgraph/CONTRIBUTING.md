# Contributing

Thanks for taking the time to improve `svgraph`.

## Development setup

```bash
npm ci
```

## Local checks

Run these before opening a pull request:

```bash
npm ci
npm run check:web
npm run build:web
npm run check:package
git diff --exit-code docs/app.js
git diff --exit-code docs/app.d.ts
npm pack --dry-run --json
node ./bin/svgraph.mjs svg2pptx examples/svgraph.svg -o tmp/svgraph-smoke.pptx
node ./bin/svgraph.mjs svgraph-presentation examples/svgraph.svg > tmp/svgraph-presentation.json
```

## Converter changes

- Prefer small, testable changes that preserve existing round-trip behavior.
- Add focused regression tests for every newly supported SVG feature, DrawingML preset, or analyzer rule.
- If a DrawingML preset is added to the converter, update the "Supported DrawingML presets" section in `README.md`; the test suite checks that the documentation stays in sync with the implementation.
- Keep conversions conservative. When a feature cannot be represented directly, document and test the approximation rather than silently claiming full fidelity.

## Reporting issues

Please include a minimal SVG or DrawingML fragment, the command or API call used, the expected output, and the actual output.

## Conduct and security

Follow `CODE_OF_CONDUCT.md` in project discussions. Report suspected vulnerabilities privately using `SECURITY.md`.
