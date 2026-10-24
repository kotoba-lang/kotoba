import { instantiate } from "./component.js";
import core1 from "./component.core.wasm";
import core2 from "./component.core2.wasm";
import core3 from "./component.core3.wasm";
import core4 from "./component.core4.wasm";
import * as capability from "./provider-capability.mjs";
import * as http from "./provider-http.mjs";

const cores = new Map([
  ["component.core.wasm", core1],
  ["component.core2.wasm", core2],
  ["component.core3.wasm", core3],
  ["component.core4.wasm", core4],
]);
const component = instantiate(
  (name) => cores.get(name),
  {
    "aiueos:capability/capability": capability,
    "aiueos:capability/http": http,
  },
);

export default {
  fetch() {
    const value = component.main();
    if (value !== 6n) {
      return new Response(`FAIL:${value}`, { status: 500 });
    }
    return new Response("PASS:compiler-component-jco-workerd:http-stream:6");
  },
};
