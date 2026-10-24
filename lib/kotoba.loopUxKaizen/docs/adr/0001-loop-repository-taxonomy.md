# ADR-0001: `loop-*` repository taxonomy and UX kaizen orchestration

- Status: accepted
- Date: 2026-07-20
- Decision owner: kotoba-lang

## Context

`design-quality` already owns deterministic HIG/WCAG/mobile scoring,
`hinshitsu.mokushi` owns screenshot baseline comparison and evidence,
and `browser-agent`/`browser-use` own browser actions and their audit trail.
Consumer applications still assembled these pieces ad hoc, and repository
names did not distinguish a persistent improvement loop from an agent prompt
or a GitHub-specific adapter.

## Decision

Create `kotoba-lang/loop-ux-kaizen` as the provider-neutral orchestrator for:

1. build rendered output;
2. audit deterministic design qualities;
3. capture real target viewports;
4. execute user journeys;
5. collect persona visual feedback;
6. decide a fail-closed gate and persist evidence.

The scoring and browser implementations remain in their existing authority
repositories. This repository owns only ordering, scenario/evidence contracts,
gate semantics and host adapters.

Repository prefixes have normative meaning:

- `loop-*`: continuous observe/evaluate/decide/act orchestration. It must be
  CI-provider neutral and must not duplicate scoring libraries.
- `skill-*`: agent instructions and judgment procedure. It must not be the
  resident execution engine or own CI state.
- `action-*`: GitHub Action packaging. It must remain a thin adapter over a
  provider-neutral loop or library.
- no orchestration prefix: reusable domain library such as `design-quality`,
  `hinshitsu`, `browser-agent`, or `browser-use`.

The machine-readable authority for these rules is
`resources/repository-rules.edn`.

## Evidence and gate policy

- Missing required evidence fails closed.
- Deterministic checks are merge gates.
- Browser journeys are merge gates when declared by the consumer scenario.
- Persona/LLM visual judgments are discovery evidence unless a consumer
  explicitly configures `:persona-axis-min`.
- Screenshot baselines are never promoted automatically. Promotion requires
  an explicit human action so a regression cannot approve itself.
- GitHub tokens and application credentials are injected at runtime and are
  never written into scenarios, evidence, screenshots, or repository rules.

## Consequences

- Local apps and hosted apps share one loop contract.
- GitHub Actions can remain resident without making GitHub the domain authority.
- A future `skill-ux-kaizen` or standalone `action-ux-kaizen` can be extracted
  without changing scenario/evidence semantics.
- Consumers keep their personas and journeys as product data; the common repo
  keeps orchestration semantics only.
