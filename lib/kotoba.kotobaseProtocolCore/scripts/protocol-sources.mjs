import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';

const home = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const expected = new Map([
  ['kotoba.kotobase.protocol.ipq', ['kotoba-lang/kotobase-protocol-ipq', true]],
  ['kotoba.kotobase.protocol.query-surfaces', ['kotoba-lang/kotobase-query-surfaces', true]],
  ['kotoba.kotobase.protocol.lfs', ['kotoba-lang/kotobase-lfs', false]],
]);

export function validateCatalog(catalog) {
  if (catalog?.schema !== 'kotoba.protocol-source-catalog.v1' || catalog.owner !== 'kotoba-lang/kotobase-protocol-core' || catalog['source-only'] !== true || catalog.packages?.length !== expected.size) throw new Error('invalid-source-catalog');
  const names = new Set();
  for (const row of catalog.packages) {
    const binding = expected.get(row.id);
    if (!binding || row.path !== `surfaces/${row.id}` || row['legacy-repository'] !== binding[0] || row['needs-owner'] !== binding[1] || JSON.stringify(row['source-paths']) !== '["src"]' || row.admission !== 'not-granted') throw new Error('invalid-source-path-or-id');
    if (JSON.stringify(row.aliases) !== JSON.stringify([binding[0], 'io.github.' + binding[0]])) throw new Error('invalid-legacy-source-aliases');
    for (const name of [row.id, ...row.aliases]) {
      if (names.has(name)) throw new Error('duplicate-source-id-or-alias');
      names.add(name);
    }
  }
  return catalog;
}

export function resolveSource(catalog, name) {
  validateCatalog(catalog);
  const row = catalog.packages.find(row => row.id === name || row.aliases.includes(name));
  return row ? {ok: true, package: row, admission: 'not-granted'} : {ok: false, problem: 'unknown-source', requested: name};
}

export function sourcePaths(root, row) {
  const base = fs.realpathSync(root);
  return [row.path + '/src', ...(row['needs-owner'] ? ['src'] : [])].map(relative => {
    const target = path.resolve(root, relative), real = fs.realpathSync(target);
    if (fs.lstatSync(target).isSymbolicLink() || fs.lstatSync(path.resolve(root, row.path)).isSymbolicLink() || !real.startsWith(base + path.sep) || !fs.statSync(real).isDirectory()) throw new Error('source-path-unavailable');
    return real;
  });
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  try {
    const catalog = validateCatalog(JSON.parse(fs.readFileSync(path.join(home, 'surfaces/catalog.json'), 'utf8')));
    const [command, ...names] = process.argv.slice(2);
    let result;
    if (command === 'list' && !names.length) result = {ok: true, packages: catalog.packages, admission: 'not-granted'};
    else if (command === 'resolve' && names.length === 1) {
      result = resolveSource(catalog, names[0]);
      if (result.ok) result.paths = sourcePaths(home, result.package);
    } else if (command === 'classpath' && names.length) {
      const rows = names.map(name => resolveSource(catalog, name)), bad = rows.find(row => !row.ok);
      if (bad) result = bad;
      else {
        const packages = [...new Map(rows.map(row => [row.package.id, row.package])).values()];
        result = {ok: true, ids: packages.map(row => row.id), paths: [...new Set(packages.flatMap(row => sourcePaths(home, row)))], admission: 'not-granted'};
      }
    } else result = {ok: false, problem: 'usage', usage: 'list | resolve ID/ALIAS | classpath ID...'};
    console.log(JSON.stringify(result));
    if (!result.ok) process.exitCode = 1;
  } catch (error) {
    console.log(JSON.stringify({ok: false, problem: error.message}));
    process.exitCode = 1;
  }
}
