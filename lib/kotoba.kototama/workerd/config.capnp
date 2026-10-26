using Workerd = import "/workerd/workerd.capnp";

const config :Workerd.Config = (
  services = [(name = "main", worker = .worker)],
  sockets = [(name = "http", address = "127.0.0.1:18787",
              http = (), service = "main")]
);

const worker :Workerd.Worker = (
  modules = [
    (name = "worker.mjs", esModule = embed "fixtures/worker.mjs"),
    (name = "./kototama-core-host.mjs",
     esModule = embed "kototama-core-host.mjs"),
    (name = "./guest.wasm", wasm = embed "fixtures/guest.wasm")
  ],
  compatibilityDate = "2026-07-26",
);
