#!/usr/bin/env node
// Load the emitted web guest and call its exports.
// Does not reimplement catalog/host-listen predicates. There is no nbb host copy.
//
// Guest execution is instantiateKotoba on the kotoba compile --target web
// artifact. kotoba run on typed forms may reject or return adapter-required
// (planned); that is not treated as a guest run.

import { pathToFileURL } from "node:url";
import { existsSync } from "node:fs";
import { resolve } from "node:path";

const file = "target/kotoba/main.mjs";
const abs = resolve(file);
if (!existsSync(abs)) {
  console.error(`missing emitted guest ${file} — run scripts/kotoba-compile.sh first`);
  process.exit(1);
}

const mod = await import(pathToFileURL(abs).href);
if (typeof mod.instantiateKotoba !== "function") {
  console.error("main: no instantiateKotoba export");
  process.exit(1);
}

const guest = mod.instantiateKotoba({});
const main = guest.main();
if (main === 0n || main === 0) {
  console.error(`main: guest main stayed 0 (got ${main})`);
  process.exit(1);
}

const help = guest.run("help");
if (help !== 11n && help !== 11) {
  console.error(`main: guest run(help) => ${help}, expected 11`);
  process.exit(1);
}

const task = guest.run("task");
if (task !== 90n && task !== 90) {
  console.error(`main: guest run(task) => ${task}, expected 90 (host-listen HOLD)`);
  process.exit(1);
}

const infer = guest.run("infer");
if (infer !== 90n && infer !== 90) {
  console.error(`main: guest run(infer) => ${infer}, expected 90 (host-listen HOLD)`);
  process.exit(1);
}

const persist = guest.run("persist");
if (persist !== 90n && persist !== 90) {
  console.error(`main: guest run(persist) => ${persist}, expected 90 (host-listen HOLD)`);
  process.exit(1);
}

const unknown = guest.run("not-a-command");
if (unknown !== 2n && unknown !== 2) {
  console.error(`main: guest run(not-a-command) => ${unknown}, expected 2`);
  process.exit(1);
}

const version = guest["command-status"]("version");
if (version !== 11n && version !== 11) {
  console.error(`main: guest command-status(version) => ${version}, expected 11`);
  process.exit(1);
}

const interactive = guest["command-status"]("interactive");
if (interactive !== 90n && interactive !== 90) {
  console.error(`main: guest command-status(interactive) => ${interactive}, expected 90`);
  process.exit(1);
}

const murakumo = guest["model-backend"]("murakumo:gemma3:4b");
if (murakumo !== "murakumo") {
  console.error(`main: guest model-backend(murakumo:gemma3:4b) => ${murakumo}, expected murakumo`);
  process.exit(1);
}

const openrouter = guest["model-backend"]("z-ai/glm-5.2");
if (openrouter !== "openrouter") {
  console.error(`main: guest model-backend(z-ai/glm-5.2) => ${openrouter}, expected openrouter`);
  process.exit(1);
}

const subscription = guest["model-backend"]("codex:");
if (subscription !== "subscription") {
  console.error(`main: guest model-backend(codex:) => ${subscription}, expected subscription`);
  process.exit(1);
}

console.log(`main: instantiateKotoba main=${main} run(help)=${help} run(task)=${task} run(infer)=${infer} run(persist)=${persist} command-status(version)=${version} command-status(interactive)=${interactive} model-backend(murakumo)=${murakumo} model-backend(openrouter)=${openrouter} model-backend(codex)=${subscription}`);
