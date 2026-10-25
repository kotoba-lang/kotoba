# etzhayyim-project-hub

Goal: provide a self-hosted, GitHub-compatible API surface via MCP over XRPC (not GitHub integration).

## UI

- Public UI: `https://hub.etzhayyim.com/`
- UI source: `cdn/hub-ui-m9x2k4qp`
- CDN prefix: `hub-ui`

Current implementation lives at:

- `/Users/junkawasaki/.codex/worktrees/3707/etzhayyim-apps-etzhayyim/60-apps/etzhayyim-project-hub/legacy-runtime/project-hub-qk6cjn0l`

## What Exists (MVP)

- MCP XRPC server implementing `mcp.v1.MCPService` on `:8080`
- Clerk JWT auth (XRPC interceptors)
  - unauthenticated: `GetServerInfo`, `ListTools`
  - authenticated: `CallTool`
  - Note: this hub currently **decodes JWT claims without signature verification** (assumes a trusted gateway already verified Clerk tokens)
- One GitHub-compatible request tool:
  - `hubetzhayyim` (method + path + body)
- Git smart HTTP backend on `:8090` under `/git/` (delegates to `git-http-backend`)
- Persistence via legacy runtime State HTTP API (env `APP_HTTP_ENDPOINT`), default store `org-statestore`

## Supported GitHub REST Subset (via `hubetzhayyim`)

- `POST /user/repos` (create repo)
- `GET /user/repos` (list repos for authenticated principal)
- `POST /orgs/{org}/repos` (create repo in org; `{org}` is org slug) *(disabled by default; enable with `ENABLE_ORG_ROUTES=true`)*
- `GET /orgs/{org}/repos` (list repos in org; `{org}` is org slug) *(disabled by default; enable with `ENABLE_ORG_ROUTES=true`)*
- `GET /repos/{owner}/{repo}` (get repo)
- `GET /repos/{owner}/{repo}/branches` (list branches from bare git repo)
- `GET /repos/{owner}/{repo}/contents/{path}` (contents API; supports `?ref=`; returns file or directory listing)
- `POST /repos/{owner}/{repo}/pulls` (create PR)
- `GET /repos/{owner}/{repo}/pulls` (list PRs)
- `GET /repos/{owner}/{repo}/pulls/{number}` (get PR)
- `PUT /repos/{owner}/{repo}/pulls/{number}/merge` (merge PR)
- `GET /repos/{owner}/{repo}/pulls/{number}/files` (list changed files)
- `POST /repos/{owner}/{repo}/statuses/{sha}` (create commit status)
- `GET /repos/{owner}/{repo}/commits/{sha}/statuses` (list statuses)
- `GET /repos/{owner}/{repo}/commits/{sha}/status` (combined status)
- `GET /repos/{owner}/{repo}/git/ref/{ref}` (get git ref)
- `GET /repos/{owner}/{repo}/git/refs/{namespace}` (list git refs)
- `GET /repos/{owner}/{repo}/commits` (list commits; minimal, returns single entry; supports `?sha=`/`?ref=`)
- `GET /repos/{owner}/{repo}/commits/{ref}` (get commit)
- `GET /repos/{owner}/{repo}/actions/workflows` (placeholder; empty)
- `GET /repos/{owner}/{repo}/actions/runs` (placeholder; empty)
- `POST /repos/{owner}/{repo}/actions/workflows/{workflow_id}/dispatches` (placeholder; 204)
- `POST /repos/{owner}/{repo}/check-runs` (create check run)
- `GET /repos/{owner}/{repo}/check-runs/{check_run_id}` (get check run)
- `PATCH /repos/{owner}/{repo}/check-runs/{check_run_id}` (update check run)
- `GET /repos/{owner}/{repo}/commits/{ref}/check-runs` (list check runs for a ref)

Pagination: list endpoints accept `?page=` and `?per_page=` and return a `Link` header when applicable.

## Org Slug Source Of Truth (Clerk)

The hub does not call Clerk APIs to map `org_id -> org_slug`.
For org-scoped GitHub routes to work, the Clerk token must include `org_slug` as a claim.
If `org_slug` is missing, org-scoped routes are rejected.
