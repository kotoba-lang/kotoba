---
name: scheduled-report-review
description: Use when a cron report lands; verify before relaying.
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [cron, review, verification, reporting]
    category: devops
---

# Scheduled Report Review

A scheduled agent delivers a measurement/report and asks for review. Treat the report as a set of claims, verify each cheaply and independently, act only on what needs action, and summarize for the chat. Never relay an unverified claim, and never call an unmeasured run a pass.

## Procedure

1. **Read the delivered payload itself**, not just the chat-forwarded copy — open the actual cron output file (newest file in the job's output dir) and confirm the body matches what was summarized.
2. **Re-verify the cheap factual claims yourself** with direct commands: pins/hashes via `git -C <repo> rev-parse --short HEAD`, load average via `uptime` (a report's load window must be plausible against the live reading), file existence via direct listing.
3. **Re-run one representative measurement** if the report's headline numbers are load-bearing and you have not already independently reproduced them this cycle; if you already re-ran and they matched earlier, skip re-running and say so.
4. **Check the report's claimed side effects landed.** If the report says it recorded results into a runbook/skill, confirm the entry actually exists — a run that runs out of time often says "will record next run" and you fill the entry yourself from the report body. Verify your own appends rendered intact (a fuzzy patch can leave fragment residue; re-read the tail of what you touched).
5. **Route action:** correct report + nothing actionable → say so with the evidence you checked. Infrastructure failures (provider 502, unreachable, auth/credential errors) belong to the fleet/owner layer — do not pause the job or rewrite its prompt to fix a credential problem; hand the local-vs-fleet-wide distinguishing question to the coordinating agent. Report-content bugs get fixed where they live (the runner's own runbook).
6. **Summarize in the conversation's language**, leading with the verdict (correct / needs action), then the independently-verified items, then anything the report got subtly wrong.

## Pitfalls

- **"0 tests / 0 failures" is NOT a pass** — distinguish "did not run / could not load" from "ran and passed"; keep the last real-measurement baseline as the comparison reference and say explicitly that the current run is measurement-impossible. A silent green is how regressions hide.
- **Wall-time inflation under load is environment noise, not regression** — when user+sys time ≪ real time across suites, it is OS/process contention; counts (tests, assertions, vector checks) are the only reliable signal. A single-threshold trip with fully matching counts is a pass-with-note, not a failure.
- **Verify the report's own logbook entry, don't trust its claim that it wrote one.**
- **Cross-check load/timing claims against the live system** — a report's load window and your live reading minutes later must tell one coherent story.
- **Do not fabricate a measurement to have something to report** — an honest N/A (no test infra, toolchain cannot load the files) is the correct output.
- **When a cron-fired session's foreground `terminal` returns empty stdout (even `true`) or EXIT 1, redirect the command's output to a log file and `read_file` it** — the cron runtime channel can swallow stdout and may block `execute_code`, `bash -lc`, `-e`, `subshell`; redirect+re-read reliably reconstructs the output, so do that before blind retries or `tail/head` pipes. Do not blind-wait a suite longer than the cron period: start it `background`+`notify`, then read its log next call.
- **Loader mechanics depth:** `references/kotoba-runner-loading.md` holds the kotoba `.cljk`/`nbb.edn` load rules and the one unblock recipe that actually worked — consult it when a repo reads “0 tests / ENOENT” while its runner files exist on disk.
- **Keep runbook constants out of always-loaded docs** — measurements written into top-level instruction files get quoted as law next week; put them in the runbook entry dated.
- **A fired job's own runbook may live in ANOTHER profile's skills dir, unreachable by `skill_view` from your profile** — a `skill name not found` here means the same-name file exists in the firing profile (`profiles/<job-profile>/skills/`). Read and edit it with the plain file tools at its absolute path; do not park its baselines only in memory, and do not declare the job's runbook "unreachable" as a broken fact.

## Verification

Before answering: every number in your summary came from a tool you ran this cycle or a prior verified cycle (state which); the delivered-file check was done; claimed runbook writes were confirmed on disk; the verdict (correct / action taken / escalated) is explicit.
