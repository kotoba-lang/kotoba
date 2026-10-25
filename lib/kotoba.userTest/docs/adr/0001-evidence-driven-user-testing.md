# ADR 0001: Separate participant, observer and evaluator

Status: accepted

## Decision

Use one portable EDN contract across library, CLI and MCP. Keep four authorities
separate:

1. A project owner defines a study and success rubric.
2. A human, synthetic participant or recipe operates through a host capability.
3. An observer records immutable actions and evidence without deciding success.
4. A deterministic evaluator scores facts; an optional qualitative judge may add
   findings but may not overwrite those scores.

Human and synthetic outcomes are never pooled. Persona bodies and raw evidence
are local/private by default; public projection removes participant content and
retains only opaque ids, hashes and aggregate metrics.

## Consequences

- A model cannot claim its own browser run passed.
- Replaying a study against an immutable revision produces comparable evidence.
- Synthetic participants are useful for discovery and coverage, but cannot be
  mistaken for demand or market validation.
- Hosts remain responsible for consent, browser isolation, secrets, retention,
  issue creation and business telemetry.
