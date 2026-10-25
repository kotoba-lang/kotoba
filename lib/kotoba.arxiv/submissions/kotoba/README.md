# Kotoba arXiv Submission

Prepared arXiv package for:

`Kotoba: A Content-Addressed Datalog Substrate for Accountable Decentralized Agent Memory`

Recommended categories:

| Role | Category |
|---|---|
| Primary | `cs.CL` |
| Cross-list | `cs.DB` |
| Cross-list | `cs.DC` |
| Cross-list | `cs.CR` |

## Build

```bash
make -C submissions/kotoba check
```

This produces:

- `submissions/kotoba/kotoba.pdf`
- `submissions/kotoba/build/kotoba-arxiv-source.tar.gz`

Upload the source archive to arXiv. Final public submission still requires
explicit human approval.

## Current State

Submission attempt on 2026-06-28 reached arXiv's start form, but `cs.DB` was
blocked by arXiv endorsement policy:

`You are not endorsed for this archive.`

The current workflow uses `cs.CL` as the primary category because the account can
advance through the start form there and the paper can be truthfully framed as
accountable memory infrastructure for language agents.

Next action: continue the draft workflow with `cs.CL`. If arXiv blocks a
cross-list for endorsement, record the server message in `status.edn`, remove the
blocked cross-list for the first submission, and request endorsement separately.
