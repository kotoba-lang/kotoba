import guest from "./guest.wasm";
import { createKototamaCoreHost } from "./kototama-core-host.mjs";

const capability = "aiueos.component/aiueos-clock-now";
const ability = Object.freeze({
  target: "clock://monotonic",
  operation: "clock/now",
  maxBytes: 8,
  maxItems: 1,
  deadlineMs: 10,
  auditId: "workerd-e2e",
});
let providerCalls = 0;
const host = createKototamaCoreHost({
  module: guest,
  manifest: {
    format: "kototama.workerd-core/v1",
    imports: [{
      module: "aiueos.component",
      name: "aiueos-clock-now",
      capability,
      ability,
    }],
    grants: [capability],
  },
  authorize: (requestedCapability, requestedAbility, args) =>
    requestedCapability === capability &&
    requestedAbility === ability &&
    args.length === 1 &&
    args[0] === 7n,
  providers: {
    [capability]: ({ ability: requestedAbility, args }) => {
      if (requestedAbility !== ability) throw new Error("ability substituted");
      providerCalls += 1;
      return args[0] + 100n;
    },
  },
});

let negativeChecks = 0;
try {
  createKototamaCoreHost({
    module: guest,
    manifest: {
      format: "kototama.workerd-core/v1",
      imports: [{
        module: "aiueos.component",
        name: "aiueos-clock-now",
        capability,
        ability,
      }],
      grants: [capability, "wasi:filesystem/ambient"],
    },
    authorize: () => true,
    providers: {[capability]: () => 0n},
  });
  throw new Error("extra grant admitted");
} catch (error) {
  if (!String(error).includes("grant-import-mismatch")) throw error;
  negativeChecks += 1;
}

const deniedHost = createKototamaCoreHost({
  module: guest,
  manifest: {
    format: "kototama.workerd-core/v1",
    imports: [{
      module: "aiueos.component",
      name: "aiueos-clock-now",
      capability,
      ability,
    }],
    grants: [capability],
  },
  authorize: () => false,
  providers: {[capability]: () => 0n},
});
try {
  deniedHost.invoke("main");
  throw new Error("denied provider call executed");
} catch (error) {
  if (!String(error).includes("provider-call-denied")) throw error;
  negativeChecks += 1;
}

export default {
  fetch() {
    const result = host.invoke("main");
    return Response.json({
      result: result.toString(),
      providerCalls,
      runtime: "workerd-core",
      ambientWasi: false,
      negativeChecks,
    });
  },
};
