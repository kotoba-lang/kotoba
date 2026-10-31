import fs from "node:fs";

const html = fs.readFileSync(process.argv[2] || "dist/index.html", "utf8");
const cljs = fs.readFileSync(process.argv[3] || "src/cae/webgpu.cljk", "utf8");
const css = fs.readFileSync(process.argv[4] || "dist/css/main.css", "utf8");
const ids = [...html.matchAll(/data-kami-scene="(\d+)"/g)].map((m) => Number(m[1]));
const expected = Array.from({length: 15}, (_, i) => i);
if (JSON.stringify(ids) !== JSON.stringify(expected)) throw new Error(`scene buttons are not contiguous: ${ids}`);
if (!cljs.includes("(case kind")) throw new Error("CLJS scene geometry dispatcher is missing");
if (!cljs.includes("navigator") || !cljs.includes("requestAdapter")) throw new Error("CLJS does not directly access WebGPU");
for (const id of ["kami-sim-toggle", "kami-sim-reset", "kami-sim-speed", "kami-sim-time", "kami-sim-steps"]) {
  if (!html.includes(`id="${id}"`)) throw new Error(`missing realtime control: ${id}`);
}
for (const contract of ["advance-simulation", "initial-simulation", "telemetry"]) {
  if (!cljs.includes(contract)) throw new Error(`missing realtime CLJS contract: ${contract}`);
}
for (const contract of ["pointerdown", "pointermove", "pointer-action", "action-keys"]) {
  if (!cljs.includes(contract)) throw new Error(`missing interaction contract: ${contract}`);
}
for (const id of ["kami-action-status", "kami-action-title", "kami-action-cursor"]) {
  if (!html.includes(`id="${id}"`)) throw new Error(`missing discoverable interaction UI: ${id}`);
}
if (!html.includes("./css/main.css") || !css.includes("build_pages_report")) {
  throw new Error("Hiccup/Shadow CSS report output is missing");
}
for (const contract of ["i18n.core", "embed-catalog", "set-locale!", "kami-cae-locale"]) {
  if (!cljs.includes(contract)) throw new Error(`missing kotoba-lang/i18n contract: ${contract}`);
}
if (!html.includes('id="kami-locale"') || !html.includes('data-i18n="app/physics"')) {
  throw new Error("missing locale switcher or translated Hiccup labels");
}
for (const metric of ["Sod FVM", "RANS k–ε", "Thermo-mechanical", "3D contact", "Fracture", "MPI"]) {
  if (!html.includes(metric)) throw new Error(`missing advanced metric: ${metric}`);
}
console.log(`Advanced WebGPU scene contract verified (${ids.length} scenes)`);
