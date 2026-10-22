#!/usr/bin/env node
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';

const inventory = JSON.parse(readFileSync(new URL('../docs/library-repository-inventory.json', import.meta.url), 'utf8'));
const rows = inventory.repositories;
const counts = {};
const names = new Set();
for (const row of rows) {
  assert(/^[A-Za-z0-9_.-]+$/.test(row.repo) && !['.', '..'].includes(row.repo));
  assert(!names.has(row.repo), 'duplicate repository');
  names.add(row.repo);
  counts[row.classification] = (counts[row.classification] || 0) + 1;
  assert.equal(row.github.private, false, 'public catalog cannot contain private repository details');
  assert(Number.isSafeInteger(row.github.id) && row.github.id > 0);
  assert.equal(row['local-checkout'].path, `kotoba-lang/${row.repo}`);
  assert.equal(row['local-checkout'].status, 'canonical-checkout');
  if (row['workspace-manifest'].registered) {
    assert.equal(row['workspace-manifest'].path, row['local-checkout'].path);
    assert(/^[0-9a-f]{40}$/.test(row['workspace-manifest'].revision));
  }
}
assert.equal(rows.length, inventory['public-repositories']);
assert.equal(inventory['total-repositories'], rows.length + inventory['private-repositories']);
assert.deepEqual(Object.fromEntries(Object.entries(counts).sort()), Object.fromEntries(Object.entries(inventory.counts).sort()));
const retirement = JSON.parse(readFileSync(new URL('../maintenance/retired-libraries/2026-10-22/manifest.json', import.meta.url), 'utf8'));
const held = new Set(retirement['held-dependency-pin-repositories']);
assert.equal(held.size, 239);
for (const row of rows) assert.equal(row['dependency-pin-hold'], held.has(`kotoba-lang/${row.repo}`));
assert.equal(rows.filter(row => row['dependency-pin-hold']).length, inventory['dependency-pin-holds']);
for (const row of retirement.repositories) assert(!names.has(row.repo.split('/')[1]), 'deleted origin cannot be a current repository');

const [command = 'summary', ...args] = process.argv.slice(2);
let result;
if (command === 'check') {
  assert.equal(args.length, 0);
  result = {ok: true, public: rows.length, private: inventory['private-repositories'], total: inventory['total-repositories'], 'pin-holds': held.size};
} else if (command === 'summary') {
  assert.equal(args.length, 0);
  result = Object.fromEntries(['observed-at', 'total-repositories', 'public-repositories', 'private-repositories', 'github-counts', 'local-layout', 'workspace-manifest', 'counts', 'catalogs'].map(key => [key, inventory[key]]));
} else if (command === 'show') {
  assert.equal(args.length, 1, 'show REPOSITORY');
  const name = args[0].replace(/^kotoba-lang\//, '');
  result = rows.find(row => row.repo === name);
  assert(result, 'repository is absent from the public catalog');
} else if (command === 'list') {
  const filters = {};
  while (args.length) {
    const key = args.shift();
    if (['--classification', '--owner'].includes(key)) {
      const value = args.shift(); assert(value && !value.startsWith('--'), `missing value: ${key}`);
      filters[key] = value;
    } else { assert(['--held', '--unregistered', '--archived', '--fork'].includes(key), `unknown filter: ${key}`); filters[key] = true; }
  }
  result = rows.filter(row =>
    (!filters['--classification'] || row.classification === filters['--classification']) &&
    (!filters['--owner'] || row.owner === filters['--owner']) &&
    (!filters['--held'] || row['dependency-pin-hold']) &&
    (!filters['--unregistered'] || !row['workspace-manifest'].registered) &&
    (!filters['--archived'] || row.github.archived) &&
    (!filters['--fork'] || row.github.fork))
    .map(row => Object.fromEntries(['repo', 'classification', 'review-state', 'owner', 'destination', 'source-id', 'dependency-pin-hold', 'github', 'local-checkout', 'workspace-manifest'].filter(key => row[key] !== undefined).map(key => [key, row[key]])));
} else {
  throw new Error('usage: repository-catalog.mjs summary | check | show REPOSITORY | list [--classification CLASS] [--owner ORG/REPO] [--held] [--unregistered] [--archived] [--fork]');
}
console.log(JSON.stringify(result, null, 2));
