import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import {spawnSync} from 'node:child_process';
const root = process.cwd(), base = process.argv[2], temp = process.env.RUNNER_TEMP && path.resolve(process.env.RUNNER_TEMP);
assert(base && (path.resolve(base).includes('/github/workspaces/') || (process.env.GITHUB_ACTIONS === 'true' && temp && path.resolve(base).startsWith(temp + path.sep))));
fs.mkdirSync(base, {recursive: true}); const tmp = fs.mkdtempSync(path.join(base, 'protocol-history-negative-'));
try {
  fs.mkdirSync(path.join(tmp, 'scripts')); fs.copyFileSync(path.join(root, 'scripts/check-protocol-history.mjs'), path.join(tmp, 'scripts/check-protocol-history.mjs'));
  fs.cpSync(path.join(root, 'maintenance'), path.join(tmp, 'maintenance'), {recursive: true});
  const file = path.join(tmp, 'maintenance/protocol-consolidation/2026-10-22/receipt.json'), original = fs.readFileSync(file), receipt = JSON.parse(original);
  const check = () => spawnSync(process.execPath, [path.join(tmp, 'scripts/check-protocol-history.mjs'), path.join(tmp, 'restores')], {encoding: 'utf8'}).status;
  assert.equal(check(), 0); let refused = 0;
  const mutation = fn => {try {fn(); assert.notEqual(check(), 0); refused++;} finally {fs.writeFileSync(file, original);}};
  mutation(() => {const m = JSON.parse(original); m.repositories[0]['preserved-refs'][0].object = '0'.repeat(40); fs.writeFileSync(file, JSON.stringify(m));});
  mutation(() => {const m = JSON.parse(original); m.repositories[0].archived = true; m.repositories[0]['archive-status'] = 'archived-after-main-verification'; delete m['main-verification']; fs.writeFileSync(file, JSON.stringify(m));});
  const bundle = path.join(tmp, receipt.repositories[0]['history-bundle']), bytes = fs.readFileSync(bundle);
  try {mutation(() => {const corrupt = Buffer.from(bytes); corrupt[0] ^= 1; fs.writeFileSync(bundle, corrupt);});} finally {fs.writeFileSync(bundle, bytes);}
  const ip = path.join(tmp, 'maintenance/protocol-source-imports.json'), ib = fs.readFileSync(ip), imports = JSON.parse(ib);
  try {mutation(() => {const m = JSON.parse(ib); m['branch-reviews'] = []; fs.writeFileSync(ip, JSON.stringify(m));});} finally {fs.writeFileSync(ip, ib);}
  try {mutation(() => {const m = JSON.parse(ib); m['branch-reviews'][0]['production-source-lineage'][0]['successor-sha256'] = '0'.repeat(64); fs.writeFileSync(ip, JSON.stringify(m));});} finally {fs.writeFileSync(ip, ib);}
  const diff = path.join(tmp, imports['branch-reviews'][0]['review-diff']), db = fs.readFileSync(diff);
  try {mutation(() => fs.writeFileSync(diff, Buffer.concat([db, Buffer.from('unreviewed drift')])));} finally {fs.writeFileSync(diff, db);}
  assert.equal(check(), 0); assert.equal(refused, 6);
  console.log('protocol recovery: baseline PASS;6 ref/archive-proof/bundle/branch-review/successor-hash/review-diff mutations refused');
} finally {fs.rmSync(tmp, {recursive: true, force: true});}
