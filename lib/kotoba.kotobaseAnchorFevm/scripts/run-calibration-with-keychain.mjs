import {spawnSync} from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

const SERVICES = Object.freeze({
  deployer: "kotobase-fevm-calibration-deployer-private-key",
  operator: "kotobase-fevm-calibration-operator-private-key",
  salt: "kotobase-fevm-calibration-disclosure-salt"
});

function secret(service) {
  const result = spawnSync("security", ["find-generic-password", "-w", "-s", service],
    {encoding: "utf8", stdio: ["ignore", "pipe", "inherit"]});
  if (result.status !== 0) throw new Error(`cannot read ${service} from macOS Keychain`);
  return result.stdout.trim();
}

const action = process.argv[2];
if (!new Set(["deploy", "qualify"]).has(action))
  throw new Error("usage: run-calibration-with-keychain.mjs <deploy|qualify>");
const env = {...process.env};
let script;
if (action === "deploy") {
  env.FEVM_DEPLOYER_PRIVATE_KEY = secret(SERVICES.deployer);
  script = "scripts/deploy-calibration.mjs";
} else {
  env.FEVM_PRIVATE_KEY = secret(SERVICES.operator);
  env.FEVM_DISCLOSURE_SALT = secret(SERVICES.salt);
  if (!env.FEVM_EVIDENCE_JOURNAL) {
    const evidenceDir = fs.mkdtempSync(path.join(os.tmpdir(), "kotobase-fevm-evidence-"));
    fs.chmodSync(evidenceDir, 0o700);
    env.FEVM_EVIDENCE_JOURNAL = path.join(evidenceDir, "calibration.jsonl");
  }
  script = "scripts/qualify-calibration.mjs";
}
const result = spawnSync(process.execPath, [script], {env, stdio: "inherit"});
if (result.error) throw result.error;
process.exit(result.status ?? 1);
