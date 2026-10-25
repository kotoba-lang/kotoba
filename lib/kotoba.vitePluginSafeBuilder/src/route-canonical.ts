/**
 * Route Canonical
 *
 * Enforces trailing slash policy on internal routes (href, goto).
 */

import type { Plugin } from 'vite';

export interface RouteCanonicalOptions {
  trailingSlash?: 'always' | 'never';
  include?: RegExp;
  failOnWarning?: boolean;
}

interface Violation {
  id: string;
  line: number;
  column: number;
  message: string;
  value: string;
}

const DEFAULT_INCLUDE = /\.(svelte|ts|tsx|js|jsx)$/;

function shouldCheck(value: string): boolean {
  if (!value.startsWith('/')) return false;
  if (value === '/') return false;
  if (value.startsWith('/#') || value.startsWith('/?')) return false;
  if (value.includes('://')) return false;
  if (/\.[a-z0-9]+($|[?#])/i.test(value)) return false;
  return true;
}

function toCanonical(value: string, trailingSlash: 'always' | 'never'): string {
  const [path, suffix = ''] = value.split(/([?#].*)/, 2);
  if (trailingSlash === 'always') {
    return path.endsWith('/') ? `${path}${suffix}` : `${path}/${suffix}`;
  }
  const normalized = path.endsWith('/') ? path.slice(0, -1) : path;
  return `${normalized || '/'}${suffix}`;
}

function positionFromIndex(code: string, index: number): { line: number; column: number } {
  const lines = code.slice(0, index).split('\n');
  return {
    line: lines.length,
    column: lines[lines.length - 1].length + 1,
  };
}

function collectViolations(id: string, code: string, trailingSlash: 'always' | 'never'): Violation[] {
  const violations: Violation[] = [];
  const patterns = [
    /href\s*=\s*["'](\/[^"']*)["']/g,
    /goto\(\s*["'](\/[^"']*)["']/g,
  ];

  for (const re of patterns) {
    let match: RegExpExecArray | null;
    while ((match = re.exec(code)) !== null) {
      const value = match[1];
      if (!shouldCheck(value)) continue;
      const canonical = toCanonical(value, trailingSlash);
      if (value === canonical) continue;
      const start = match.index + match[0].indexOf(value);
      const pos = positionFromIndex(code, start);
      violations.push({
        id,
        line: pos.line,
        column: pos.column,
        value,
        message: `Non-canonical internal route "${value}". Use "${canonical}" for trailingSlash:${trailingSlash}.`,
      });
    }
  }

  return violations;
}

export function routeCanonical(options: RouteCanonicalOptions = {}): Plugin {
  const trailingSlash = options.trailingSlash ?? 'always';
  const include = options.include ?? DEFAULT_INCLUDE;
  const failOnWarning = options.failOnWarning ?? true;
  const violations: Violation[] = [];

  return {
    name: 'route-canonical',
    enforce: 'pre',

    transform(code, id) {
      if (!include.test(id)) return null;
      violations.push(...collectViolations(id, code, trailingSlash));
      return null;
    },

    buildEnd() {
      if (violations.length === 0) return;
      const details = violations
        .map((v) => `- ${v.id}:${v.line}:${v.column} ${v.message}`)
        .join('\n');
      const summary = `[route-canonical] ${violations.length} route canonicalization issue(s) found:\n${details}`;
      if (failOnWarning) {
        this.error(summary);
      } else {
        this.warn(summary);
      }
    },
  };
}
