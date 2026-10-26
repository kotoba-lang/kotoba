// Browser-side port of kotoba-lang/kotoba's `has_capability` host import
// (kotoba.wasm-exec/has-capability-fn + capability-granted? +
// id->capability-name). A `.kotoba` program compiled with a runtime
// `(has-capability? :some/cap)` check (as opposed to the static
// compile-time capability gate `kotoba wasm emit --policy` already applies)
// declares a single `(module "kotoba") has_capability(id: i32) -> i32`
// import; the compiled guest passes the i32 id resolved at compile time
// from the literal capability keyword, and expects 1 (granted) or 0
// (denied) back.
//
// The id <-> capability-name table is the canonical
// kotoba-lang/kotoba-core-contracts `capability_contract.edn`
// `:capability-ids` map (schema kotoba.runtime.capability-contract.v0) --
// copied here, not re-derived, since this library has no Clojure runtime
// to read that EDN file from. Keep in sync if the contract adds ids.
export const CAPABILITY_IDS = {
  'ledger/append': 201,
  'fs/app-data': 202,
  'notify/show': 203,
  'clipboard/text': 204,
  'http/fetch': 205,
  'keychain/text': 206,
  'contacts/read': 207,
  'calendar/read': 208,
  'graph/kotoba': 209,
  'log/write': 210,
  'clock/monotonic': 211,
  'random/bytes': 212,
  'topic/publish': 213,
  'topic/subscribe': 214,
  'pci/config': 215,
  'dma/map': 216,
  'irq/subscribe': 217,
  'mmio/map': 218,
};

const ID_TO_CAPABILITY = Object.fromEntries(
  Object.entries(CAPABILITY_IDS).map(([name, id]) => [id, name])
);

// GRANTED_CAPABILITIES: an iterable of capability-name strings (e.g.
// ['notify/show']) -- the browser-side equivalent of the JVM's
// `{:kotoba.policy/capabilities #{...}}` policy map. Fail-closed like the
// JVM implementation: an unrecognized id, or an id whose capability name
// isn't in GRANTED_CAPABILITIES, always resolves to 0 (denied). No
// argument grants nothing, same as instantiate/run-main's default on the
// JVM side.
//
// This is a runtime re-statement of a policy, not a re-derivation of the
// static compile-time gate `kotoba wasm emit --policy` already applied --
// nothing here re-verifies that the bytes being instantiated were actually
// compiled under this exact policy. See wasm-webcomponent's README "Scope"
// section.
export function hasCapabilityHostImport(grantedCapabilities) {
  const granted = new Set(grantedCapabilities || []);
  return {
    has_capability: (id) => {
      const name = ID_TO_CAPABILITY[id];
      return name && granted.has(name) ? 1 : 0;
    },
  };
}
