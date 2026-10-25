import {spawnSync} from "node:child_process";
import crypto from "node:crypto";
import {Wallet} from "ethers";

const SERVICES = Object.freeze({
  deployer: "kotobase-fevm-calibration-deployer-private-key",
  operator: "kotobase-fevm-calibration-operator-private-key",
  salt: "kotobase-fevm-calibration-disclosure-salt"
});

function security(args, options = {}) {
  const result = spawnSync("security", args, {encoding: "utf8", stdio: options.capture ? "pipe" : "ignore"});
  if (result.error) throw result.error;
  return result;
}

function absent(service) {
  if (security(["find-generic-password", "-s", service], {capture: true}).status === 0)
    throw new Error(`Keychain item ${service} already exists; refusing implicit rotation`);
}

function put(service, account, secret) {
  const result = security(["add-generic-password", "-a", account, "-s", service, "-w", secret]);
  if (result.status !== 0) throw new Error(`failed to store ${service} in macOS Keychain`);
}

for (const service of Object.values(SERVICES)) absent(service);
const deployer = Wallet.createRandom();
const operator = Wallet.createRandom();
put(SERVICES.deployer, deployer.address, deployer.privateKey);
put(SERVICES.operator, operator.address, operator.privateKey);
put(SERVICES.salt, "v1", `0x${crypto.randomBytes(32).toString("hex")}`);
console.log(JSON.stringify({schema: "kotobase.fevm-calibration-public-credentials.v1",
  deployer: deployer.address, operator: operator.address,
  secret_store: "macos-keychain", services: SERVICES}, null, 2));
