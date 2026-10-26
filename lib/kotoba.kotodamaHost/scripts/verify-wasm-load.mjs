// scripts/verify-wasm-load.mjs — JUN-149 最終項目: dist/*.wasm を
// browser-host.mjs（kototama-browser-host-v1 の typed host runtime、
// amu runtime/browser-host.mjs）経由で読み込み、admission を検証する。
// 使い方: node scripts/verify-wasm-load.mjs
// 検証: instantiateKotoba の admission（typed section / compatibility /
// import allowlist / capability 拒否）を通過し、判定核 export が在ること。
import { readFileSync } from "node:fs";
import { instantiateKotoba } from "/Users/junkawasaki/github/kotoba-lang/amu/runtime/browser-host.mjs";

const EXPECTED = {
  host_util: ["nsid-valid?"],
  host_types: ["seq-ok?", "text-ok?", "commit-shape-ok?"],
  host_cadence: ["determine-mood-code", "mood-cadence", "apply-stress-scaling"],
  host_model: ["normalize-hint", "choose-model-id"],
  host_lexicon: ["field-type-ok?", "required-present?"],
  host_heartbeat: ["create-cadence-state"],
};

let failed = 0;
for (const [name, exports] of Object.entries(EXPECTED)) {
  const bytes = readFileSync(new URL(`../dist/${name}.wasm`, import.meta.url));
  try {
    const result = await instantiateKotoba(bytes, { allowCapabilities: [] });
    const got = Object.keys(result.instance.exports);
    const missing = exports.filter((e) => !got.includes(e));
    if (missing.length > 0) {
      failed += 1;
      console.log(`FAIL ${name}: missing exports ${missing.join(", ")} (got: ${got.join(", ")})`);
    } else {
      console.log(`OK   ${name}: admitted (${exports.join(", ")})`);
    }
  } catch (error) {
    failed += 1;
    console.log(`FAIL ${name}: ${error?.code ?? error?.message ?? error}`);
  }
}
console.log(failed === 0 ? "ALL ADMITTED" : `${failed} FAILED`);
process.exit(failed === 0 ? 0 : 1);
