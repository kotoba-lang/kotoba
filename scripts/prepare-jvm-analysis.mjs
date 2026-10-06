// Byte-identical static-analysis inputs for tools that do not recognize CLJK.
// Runtime tests load the actual CLJK with the canonical compatibility loader.
import fs from 'node:fs';
import path from 'node:path';
const out = '.jvm-analysis';
fs.rmSync(out, { recursive: true, force: true });
let count = 0;
function copyTree(dir) {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const source = path.join(dir, entry.name);
    if (entry.isDirectory()) copyTree(source);
    else if (entry.isFile() && entry.name.endsWith('.cljk')) {
      const bytes = fs.readFileSync(source);
      const text = bytes.toString('utf8');
      const cljsOnly = source.endsWith('.cljs.cljk') || (text.includes('[cljs.test') && !text.includes('#?'));
      let relative = source.replace(/\.cljk$/, cljsOnly ? '.cljs' : '.cljc');
      if (source.startsWith('src/demo')) {
        const namespace = text.match(/\(ns\s+([^\s()]+)/)?.[1];
        if (!namespace) throw new Error('demo namespace missing');
        relative = path.join('src', namespace.replaceAll('-', '_') + (cljsOnly ? '.cljs' : '.cljc'));
      }
      const target = path.join(out, relative);
      if (fs.existsSync(target)) throw new Error(`duplicate analysis input: ${target}`);
      fs.mkdirSync(path.dirname(target), { recursive: true });
      fs.writeFileSync(target, bytes);
      if (!bytes.equals(fs.readFileSync(target))) throw new Error(`mirror differs: ${source}`);
      count++;
    }
  }
}
copyTree('src'); copyTree('test');
if (!count) throw new Error('no CLJK analysis inputs');
for (const file of ['deps.edn', 'security-adoption.edn']) fs.copyFileSync(file, path.join(out, file));
console.log(`Byte-identical CLJK analysis inputs: ${count}`);
