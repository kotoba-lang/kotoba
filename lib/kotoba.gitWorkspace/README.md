# git-workspace

Portable `.cljc` read-model for local Git workspaces and forge metadata.

It normalizes repository identity, joins Issues and Pull Requests to repositories,
builds `Organization → Repository → Project → WorkItem` navigation data, and applies
deterministic sorting. Filesystem walking, `git`, and forge API calls are host ports
owned by consuming applications.
