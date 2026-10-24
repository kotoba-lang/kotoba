using Workerd = import "/workerd/workerd.capnp";

const config :Workerd.Config = (
  services = [
    (name = "deny",
     network = (allow = [])),
    (name = "application",
     worker = (
       compatibilityDate = "2026-07-27",
       globalOutbound = "deny",
       modules = [
         (name = "worker.mjs", esModule = embed "worker.mjs"),
         (name = "component.js", esModule = embed "generated/component.js"),
         (name = "component.core.wasm", wasm = embed "generated/component.core.wasm"),
         (name = "component.core2.wasm", wasm = embed "generated/component.core2.wasm"),
         (name = "component.core3.wasm", wasm = embed "generated/component.core3.wasm"),
         (name = "component.core4.wasm", wasm = embed "generated/component.core4.wasm"),
         (name = "provider-capability.mjs",
          esModule = embed "provider-capability.mjs"),
         (name = "provider-http.mjs",
          esModule = embed "provider-http.mjs"),
       ],
     )),
  ],
  sockets = [
    (name = "http", address = "127.0.0.1:4175", http = (), service = "application"),
  ],
);
