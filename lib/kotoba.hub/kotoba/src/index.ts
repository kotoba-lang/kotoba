/**
 * hub kotoba — barrel. kotoba-E2E split: public repository catalog +
 * commitStatus facts plaintext; pullRequest / checkRun / webhook sealed via
 * kotoba E2E (ADR-2605181100). git smart-HTTP object-archive custody, Clerk JWT
 * verification + credential custody, and the merge enforcement action stay etzhayyim
 * via consent-capability.
 */
export * from "./types.js";
export {
  registerRepository,
  getRepository,
  listRepositories,
  createCommitStatus,
  listCommitStatuses,
  openPullRequest,
  listPullRequests,
  getPullRequest,
  recordCheckRun,
  listCheckRuns,
  registerWebhook,
  listWebhooks,
  coverage,
} from "./registry.js";
