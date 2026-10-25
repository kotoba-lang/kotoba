/**
 * repository kotoba — barrel.
 *
 * Repository-in-Graph git object model (blob → tree → commit → ref) on AT PDS
 * records (no RisingWave / no Hyperdrive). First-party source code = the user's
 * own repo (Repository ≡ Actor DID). FaaS build dispatch + build execution stay
 * etzhayyim, consumed via consent-capability.
 */

export * from "./types.js";
export {
  createBlob,
  getBlob,
  createTree,
  getTree,
  createCommit,
  getCommit,
  updateRef,
  listRefs,
  coverage,
} from "./registry.js";
