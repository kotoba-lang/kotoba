# ADR-0002: upstream Agent/session parity without browser-driver coupling

- Status: Accepted (2026-07-18)

## Context

The original graph loop covered observe/act and Datomic action facts, but lacked
the bounded execution, lifecycle, audit and policy surfaces expected by current
browser-use agents. Those concerns must remain portable `.cljc`; browser actions
and Playwright are injected capabilities and are unchanged.

## Decision

`agent/agent-settings` normalizes structured settings for maximum graph steps,
actions per model turn, retries, elapsed timeout classification, allowed domains,
sensitive values, output validation, planner/vision declarations and metadata.
Legacy top-level `:max-steps`, LangGraph `:compile-opts`, and Datomic
`:history-conn` remain valid.

`browseruse.session` owns running/paused/stopped state and step hooks.
`browseruse.history` defines `AgentHistory` and `ActionResult`, pure export and
injected replay. Existing `:session/id` and `:action/*` Datomic facts remain the
durable/queryable representation; additive attempt/elapsed/error facts do not
change old queries.

`browseruse.guardrail` applies navigation-domain policy before execution,
bounded retry, post-execution timeout classification and output validation.
Configured sensitive values are redacted from structured and Datomic history.
Timeout classification is portable and does not pretend to cancel a synchronous
host operation; interruptible drivers may enforce a harder deadline externally.

Recipes reuse the same policy, session, hooks and history contracts. Planner and
vision settings are forwarded as model metadata only; no screenshot, action,
browser protocol or Playwright implementation is introduced here.

