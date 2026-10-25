# ADR-0003: provider-neutral coding-agent turn loop

- Status: accepted
- Date: 2026-07-20
- Builds on: ADR-0001 and the durable outer-loop contract

## Context

`create-react-agent` provides an executable LangGraph graph, but consumers also
need portable loop semantics that can be persisted, replayed, interrupted, and
driven by different hosts and model providers. Codex and Grok-style OSS coding
agents share the same inner protocol: model response, correlated tool calls,
tool results returned to the model, repeat until no tool call remains.

## Decision

`langgraph.agent-loop` is the canonical pure `.cljc` reducer for that protocol.
It returns `{:state :effects :events}` and performs no I/O. Hosts interpret
`:model/respond`, `:tool/execute`, `:approval/request`, and
`:checkpoint/write` effects and append the returned events.

Thread / Task / Turn are stable entities. Calls require unique `:call/id`
values; results can complete in any order but are fed back in original order.
Read-only calls may execute automatically. Unknown or higher risk calls fail
closed behind approval. Denials and tool failures remain correlated results so
the model can adapt. Turn and tool-call budgets are mandatory terminal bounds.

The durable supervisor remains outside this reducer and owns leases, cadence,
crash recovery, and long-window budgets. `langgraph.prebuilt` may adopt this
reducer internally later; until then its trace must remain behaviorally
compatible.

## References

- https://github.com/openai/codex/blob/main/codex-rs/docs/protocol_v1.md
- https://github.com/openai/codex/blob/main/codex-rs/core/src/codex.rs
- https://github.com/superagent-ai/grok-cli/blob/main/src/agent/agent.ts

The Grok CLI reference is community OSS and is not an official xAI project.
