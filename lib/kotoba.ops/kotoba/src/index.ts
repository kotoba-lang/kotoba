/**
 * ops kotoba — barrel. kotoba-E2E split (plaintext processRun telemetry +
 * kotoba-E2E confidential automation config, ADR-2605181100). Scheduler firing,
 * LLM inference, fiat/credits settlement, and secret custody stay etzhayyim via
 * consent-capability; only the data records migrate.
 */
export * from "./types.js";
export {
  createProcessRun,
  updateProcessRun,
  listProcessRuns,
  getProcessRun,
  createAutomation,
  updateAutomation,
  listAutomations,
  getAutomation,
  coverage,
} from "./registry.js";
