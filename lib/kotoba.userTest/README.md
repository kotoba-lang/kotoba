# kotoba-lang/user-test

Evidence-driven user-testing contracts for humans, synthetic participants and
deterministic browser recipes. The library, CLI and MCP server share one EDN
model so a test cannot mean something different depending on how it was run.

The project deliberately does **not** pretend that a synthetic participant is a
customer. Human, synthetic and recipe results are separate projections. A
synthetic run discovers hypotheses and regressions; human evidence and production
telemetry validate desirability, trust and willingness to pay.

## Data flow

```text
business objective -> study -> execution plan -> participant + browser host
                   -> immutable evidence/run -> deterministic evaluation
                   -> finding -> issue/PR -> same-revision regression
```

Persona content, transcripts, screenshots, recordings and raw event streams stay
in the host's private/local evidence store. Public repositories may keep opaque
references, hashes, aggregate scores and fixture studies only.

## CLI

```sh
kbb -M:cli study validate --study resources/kotoba/user_test/example-study.edn
kbb -M:cli study plan --study resources/kotoba/user_test/example-study.edn
kbb -M:cli run evaluate --study study.edn --run run.edn
kbb -M:cli project summarize --project org/product --evaluations evaluations.edn
kbb -M:cli publication redact --input private-run.edn
```

## MCP

`kbb -M:mcp` starts a newline-delimited stdio MCP server with four tools:

- `user_test_validate`
- `user_test_plan`
- `user_test_evaluate`
- `user_test_project_summary`

The MCP process performs no browser or network I/O. A host such as
Cloud Itonami supplies the browser capability and evidence persistence.

## Tests

```sh
kbb -M:test
```
