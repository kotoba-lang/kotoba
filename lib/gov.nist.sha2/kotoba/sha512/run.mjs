import { readFileSync } from "node:fs";
import { instantiateKotoba } from "../../../../amu/runtime/browser-host.mjs";
const inst = await instantiateKotoba(readFileSync(process.argv[2]), {});
const exports = inst.exports ?? inst.instance?.exports ?? inst;
console.log("exports:", Object.keys(exports).slice(0, 8));
console.log("main() =", exports.main());
