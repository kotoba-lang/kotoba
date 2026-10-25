/**
 * site kotoba — barrel. Internet Clone Gateway product front: page/domain/topic
 * CATALOG metadata plaintext (sdk.write/read) + per-person followerEvent E2E
 * (sdk.encryptedWrite/Read, ADR-2605181100). The 100B WET/screenshot crawl
 * archive + crawl/embed/GPU inference stay etzhayyim (cannot fit AT PDS) and are
 * consumed via consent-capability.
 */
export * from "./types.js";
export {
  registerTopic,
  getTopic,
  listTopics,
  registerDomain,
  getDomain,
  listDomains,
  registerPage,
  getPage,
  listPages,
  registerWat,
  listWat,
  recordFollowerEvent,
  listFollowerEvents,
  getFollowerEvent,
  coverage,
} from "./registry.js";
