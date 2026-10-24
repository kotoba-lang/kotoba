# loop-ux-kaizen

Provider-neutral UX improvement loop for kotoba-lang applications.

```text
build → deterministic audit → viewport capture → user journey
      → persona feedback → gate → evidence → next iteration
```

It composes existing authorities instead of replacing them:

- `design-quality`: deterministic HIG/WCAG/mobile audit
- `hinshitsu.mokushi`: screenshot baseline comparison and evidence
- `browser-agent` / `browser-use`: browser actions and action history
- `agent-browser`: current local browser host adapter

## Local runner

The consumer builds its application, then calls:

```bash
bin/run-ux-loop \
  --root ../app/dist \
  --html ../app/dist/index.html \
  --url http://127.0.0.1:4173/ \
  --scope owner/repository \
  --artifacts ../app/target/ux-loop \
  --width 393 --height 852
```

## GitHub Action

```yaml
- uses: kotoba-lang/loop-ux-kaizen@<pinned-sha>
  with:
    html: local/index.html
    minimum: "95"
```

The composite action is the GitHub adapter. The repository's core contract is
CI-provider neutral.

## Contracts and rules

- `loop.ux-kaizen`: scenario, plan, evidence and fail-closed gate
- `resources/repository-rules.edn`: normative `loop-*` / `skill-*` /
  `action-*` taxonomy
- `docs/adr/0001-loop-repository-taxonomy.md`: architecture decision

## Verify

```bash
kbb -M:test
kbb -M:lint
```
