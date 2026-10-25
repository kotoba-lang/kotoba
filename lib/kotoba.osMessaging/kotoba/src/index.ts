/**
 * os-messaging kotoba — barrel.
 *
 * Maximal migration of the multi-platform messaging bridge:
 *   PLAINTEXT public crawl catalog (openChannel, scraperRun) +
 *   kotoba-E2E private control-plane / content (bridge, openMessage,
 *   ADR-2605181100). Platform credential custody + webhook relay + crawl
 *   compute EXECUTION stay etzhayyim via consent-capability.
 */
export * from "./types.js";
export {
  registerChannel,
  listChannels,
  getChannel,
  recordRun,
  listRuns,
  registerBridge,
  listBridges,
  getBridge,
  recordMessage,
  listMessages,
  getMessage,
  coverage,
} from "./registry.js";
