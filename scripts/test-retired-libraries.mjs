import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import {spawnSync} from 'node:child_process';
const root = process.cwd();
const workspace = process.argv[2];
assert(workspace?.includes('/github/workspaces/'), 'provide a task workspace');
fs.mkdirSync(workspace, {recursive: true});
const tmp = fs.mkdtempSync(path.join(workspace, 'retirement-mutation-'));
try {
  for (const dir of ['lib', 'scripts']) fs.mkdirSync(path.join(tmp, dir));
  for (const file of ['repository-migrations.json', 'branch-reviews.json']) fs.copyFileSync(path.join(root, 'lib', file), path.join(tmp, 'lib', file));
  fs.copyFileSync(path.join(root, 'scripts/check-retired-libraries.mjs'), path.join(tmp, 'scripts/check-retired-libraries.mjs'));
  fs.cpSync(path.join(root, 'maintenance'), path.join(tmp, 'maintenance'), {recursive: true});
  const rel = 'maintenance/retired-libraries/2026-10-22/manifest.json';
  const mp = path.join(tmp, rel), original = fs.readFileSync(mp);
  const check = () => spawnSync(process.execPath, [path.join(tmp, 'scripts/check-retired-libraries.mjs')], {encoding: 'utf8', maxBuffer: 1024 * 1024});
  assert.equal(check().status, 0, 'baseline must pass');
  let refused = 0;
  const mutate = f => {
    try { f(); assert.notEqual(check().status, 0, 'mutation must be refused'); refused++; }
    finally { fs.writeFileSync(mp, original); }
  };
  const m = JSON.parse(original);
  const bundle = path.join(tmp, m.repositories[0]['history-bundle']), bytes = fs.readFileSync(bundle);
  try { mutate(() => {const bad = Buffer.from(bytes); bad[0] ^= 1; fs.writeFileSync(bundle, bad);}); }
  finally {fs.writeFileSync(bundle, bytes);}
  mutate(() => {const x = JSON.parse(original); x['held-dependency-pin-repositories'][0] = x.repositories[0].repo; fs.writeFileSync(mp, JSON.stringify(x));});
  mutate(() => {const x = JSON.parse(original); x.repositories[0]['remote-refs'].heads[0].target.oid = '0'.repeat(40); fs.writeFileSync(mp, JSON.stringify(x));});
  const snapshot = path.join(tmp, m.repositories[0]['github-snapshot']), source = fs.readFileSync(snapshot);
  try {
    mutate(() => {
      const x = JSON.parse(original), g = JSON.parse(source);
      g.repository.openPRs.totalCount = 1;
      fs.writeFileSync(snapshot, JSON.stringify(g));
      x.repositories[0]['github-sha256'] = crypto.createHash('sha256').update(fs.readFileSync(snapshot)).digest('hex');
      fs.writeFileSync(mp, JSON.stringify(x));
    });
  } finally {fs.writeFileSync(snapshot, source);}
  console.log(`retirement preservation: baseline passed; ${refused} independent mutations refused`);
} finally {fs.rmSync(tmp, {recursive: true, force: true});}
