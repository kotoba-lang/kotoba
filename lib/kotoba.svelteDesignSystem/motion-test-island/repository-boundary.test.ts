import { readdirSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

function walk(path: string): string[] {
  return readdirSync(path, { withFileTypes: true }).flatMap((entry) => {
    if (entry.name === '.git' || entry.name === 'node_modules' || entry.name === 'dist') return [];
    const child = resolve(path, entry.name);
    return entry.isDirectory() ? walk(child) : [child];
  });
}

describe('standalone repository boundary', () => {
  it('contains no Go runtime', () => {
    const root = resolve(import.meta.dirname, '..');
    const forbidden = walk(root).filter((path) =>
      path.endsWith('.go') || path.endsWith('/go.mod') || path.endsWith('/go.sum') || path.includes('/kotodama-go/'));
    expect(forbidden).toEqual([]);
  });
});
