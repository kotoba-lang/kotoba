import { instantiate as instantiateGet } from "./get/component.js";
import getCore1 from "./get/component.core.wasm";
import getCore2 from "./get/component.core2.wasm";
import getCore3 from "./get/component.core3.wasm";
import getCore4 from "./get/component.core4.wasm";
import { instantiate as instantiatePut } from "./put/component.js";
import putCore1 from "./put/component.core.wasm";
import putCore2 from "./put/component.core2.wasm";
import putCore3 from "./put/component.core3.wasm";
import putCore4 from "./put/component.core4.wasm";
import { instantiate as instantiateCas } from "./cas/component.js";
import casCore1 from "./cas/component.core.wasm";
import casCore2 from "./cas/component.core2.wasm";
import casCore3 from "./cas/component.core3.wasm";
import casCore4 from "./cas/component.core4.wasm";
import { instantiate as instantiateSign } from "./sign/component.js";
import signCore1 from "./sign/component.core.wasm";
import signCore2 from "./sign/component.core2.wasm";
import signCore3 from "./sign/component.core3.wasm";
import signCore4 from "./sign/component.core4.wasm";
import { instantiate as instantiateVerify } from "./verify/component.js";
import verifyCore1 from "./verify/component.core.wasm";
import verifyCore2 from "./verify/component.core2.wasm";
import verifyCore3 from "./verify/component.core3.wasm";
import verifyCore4 from "./verify/component.core4.wasm";
import { instantiate as instantiateHash } from "./hash/component.js";
import hashCore1 from "./hash/component.core.wasm";
import hashCore2 from "./hash/component.core2.wasm";
import hashCore3 from "./hash/component.core3.wasm";
import hashCore4 from "./hash/component.core4.wasm";
import { instantiate as instantiateHttpPost } from "./http-post/component.js";
import httpPostCore1 from "./http-post/component.core.wasm";
import httpPostCore2 from "./http-post/component.core2.wasm";
import httpPostCore3 from "./http-post/component.core3.wasm";
import httpPostCore4 from "./http-post/component.core4.wasm";
import { instantiate as instantiateLogRead } from "./log-read/component.js";
import logReadCore1 from "./log-read/component.core.wasm";
import logReadCore2 from "./log-read/component.core2.wasm";
import logReadCore3 from "./log-read/component.core3.wasm";
import logReadCore4 from "./log-read/component.core4.wasm";
import * as capability from "./provider-capability.mjs";
import * as objectStore from "./provider-object-store.mjs";
import * as identity from "./provider-identity.mjs";
import * as hashProvider from "./provider-hash.mjs";
import * as http from "./provider-http.mjs";
import * as log from "./provider-log.mjs";

function instantiate(factory, cores) {
  const modules = new Map([
    ["component.core.wasm", cores[0]],
    ["component.core2.wasm", cores[1]],
    ["component.core3.wasm", cores[2]],
    ["component.core4.wasm", cores[3]],
  ]);
  return factory(
    (name) => modules.get(name),
    {
      "aiueos:capability/capability": capability,
      "aiueos:capability/object-store": objectStore,
      "aiueos:capability/identity": identity,
      "aiueos:capability/hash": hashProvider,
      "aiueos:capability/http": http,
      "aiueos:capability/log": log,
    },
  );
}

const get = instantiate(instantiateGet, [getCore1, getCore2, getCore3, getCore4]);
const put = instantiate(instantiatePut, [putCore1, putCore2, putCore3, putCore4]);
const cas = instantiate(instantiateCas, [casCore1, casCore2, casCore3, casCore4]);
const sign = instantiate(instantiateSign, [signCore1, signCore2, signCore3, signCore4]);
const verify = instantiate(instantiateVerify, [verifyCore1, verifyCore2, verifyCore3, verifyCore4]);
const hash = instantiate(instantiateHash, [hashCore1, hashCore2, hashCore3, hashCore4]);
const httpPost = instantiate(instantiateHttpPost,
  [httpPostCore1, httpPostCore2, httpPostCore3, httpPostCore4]);
const logRead = instantiate(instantiateLogRead,
  [logReadCore1, logReadCore2, logReadCore3, logReadCore4]);

export default {
  fetch() {
    const values = [get.main(), put.main(), cas.main(), sign.main(), verify.main(),
      hash.main(), httpPost.main(), logRead.main()];
    const expected = [4n, 0n, 1n, 3n, 1n, 32n, 202n, 4n];
    if (values.some((value, index) => value !== expected[index])) {
      return new Response(`FAIL:${values.join(",")}`, { status: 500 });
    }
    return new Response(
      "PASS:compiler-component-jco-workerd:object-store+core:4,0,1,3,1,32,202,4",
    );
  },
};
