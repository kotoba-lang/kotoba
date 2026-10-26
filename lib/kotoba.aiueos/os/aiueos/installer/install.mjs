#!/usr/bin/env node
import { resolve } from "node:path";
import { assessInstallTarget, destructivePhrase, requireDestructiveConfirmation } from "./device-policy.mjs";
import { fakeBackend, realBackend } from "./backends.mjs";
import { validateReleaseReceipt } from "./receipt.mjs";

export async function runInstaller(options, backend = realBackend()) {
  if (!options.device) throw new Error("--device is required; the installer never auto-selects a disk");
  if (!options.image || !options.receipt) throw new Error("--image and --receipt are required");
  const validatedImage = await validateReleaseReceipt(options.image, options.receipt);
  const inspected = await backend.inspect(options.device);
  const assessment = assessInstallTarget(inspected.info, inspected.systemDisks);
  if (inspected.info?.path !== options.device) {
    assessment.allowed = false;
    assessment.reasons.push("requested device path does not exactly match the canonical inspected path");
  }
  if (!Number.isSafeInteger(inspected.info?.bytes) || inspected.info.bytes < validatedImage.bytes) {
    assessment.allowed = false;
    assessment.reasons.push("target capacity is unknown or smaller than the release image");
  }
  const report = { mode: options.install ? "install" : "inspect", backend: backend.kind, image: validatedImage, target: inspected.info, systemDisks: inspected.systemDisks, allowed: assessment.allowed, reasons: assessment.reasons };
  if (!options.install) return report;
  if (!assessment.allowed) throw new Error(`refusing install: ${assessment.reasons.join("; ")}`);
  requireDestructiveConfirmation(inspected.info.path, options.confirmDevice, options.destructivePhrase);
  const reinspected = await backend.inspect(options.device);
  const reassessment = assessInstallTarget(reinspected.info, reinspected.systemDisks);
  if (!reassessment.allowed || JSON.stringify(reinspected) !== JSON.stringify(inspected)) {
    throw new Error("refusing install: target identity or safety state changed after confirmation");
  }
  const readback = await backend.writeImage(options.image, inspected.info.path, validatedImage, reinspected.info, reinspected);
  return { ...report, installed: true, readback };
}

function parseArgs(argv) {
  const options = { install: false };
  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];
    if (arg === "--install") options.install = true;
    else if (["--device", "--confirm-device", "--destructive-phrase", "--image", "--receipt", "--fake-device-config"].includes(arg)) {
      if (!argv[i + 1]) throw new Error(`${arg} requires a value`);
      const key = arg.slice(2).replace(/-([a-z])/g, (_, c) => c.toUpperCase());
      options[key] = argv[++i];
    } else throw new Error(`unknown argument: ${arg}`);
  }
  return options;
}

async function main() {
  const options = parseArgs(process.argv.slice(2));
  for (const key of ["image", "receipt", "fakeDeviceConfig"]) if (options[key]) options[key] = resolve(options[key]);
  const backend = options.fakeDeviceConfig ? await fakeBackend(options.fakeDeviceConfig) : realBackend();
  const report = await runInstaller(options, backend);
  process.stdout.write(`${JSON.stringify(report, null, 2)}\n`);
  if (!options.install && report.allowed) {
    process.stdout.write(`dry run: nothing was written.\nrequired destructive phrase: ${destructivePhrase(report.target.path)}\n`);
  }
  if (!report.allowed) process.exitCode = 2;
}

if (process.argv[1] && resolve(process.argv[1]) === resolve(new URL(import.meta.url).pathname)) {
  main().catch((error) => { process.stderr.write(`error: ${error.message}\n`); process.exitCode = 1; });
}
