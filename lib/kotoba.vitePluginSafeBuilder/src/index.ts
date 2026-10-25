/**
 * @etzhayyim/vite-plugin-safe-builder
 *
 * Unified build safety plugin for all SvelteKit apps in the etzhayyim.com monorepo.
 * Returns a Plugin[] that integrates:
 *
 *   1. svelte5-compat-check  — Detect Svelte 4 <slot> / export let in shims
 *   2. mcpOrgGuard           — Detect MCP callTool without org context
 *   3. routeCanonical        — Enforce trailing slash policy
 *   4. ssgValidate           — Post-build 404 detection
 *
 * Usage in vite.config.ts:
 *
 * ```ts
 * import { safeBuilder } from '@etzhayyim/vite-plugin-safe-builder';
 *
 * export default defineConfig({
 *   plugins: [
 *     sveltekit(),
 *     ...safeBuilder(),                    // all checks ON (default)
 *     ...safeBuilder({ strict: true }),    // CI: warnings → errors
 *   ],
 * });
 * ```
 */

import type { Plugin } from 'vite';
import { mcpOrgGuard, type McpOrgGuardOptions } from './mcp-guard.js';
import { routeCanonical, type RouteCanonicalOptions } from './route-canonical.js';
import { ssgValidate, type SSGValidatePluginOptions } from './ssg-validate-plugin.js';
import { svelte5CompatCheck, type Svelte5CompatOptions } from './svelte5-compat.js';
import { deploySmoke, type DeploySmokeOptions } from './deploy-smoke.js';

export type { Svelte5CompatOptions } from './svelte5-compat.js';
export type { McpOrgGuardOptions, SveltekitPrerenderGuardOptions } from './mcp-guard.js';
export type { RouteCanonicalOptions } from './route-canonical.js';
export type { SSGValidatePluginOptions } from './ssg-validate-plugin.js';
export type { SSGValidateOptions, ValidationIssue, ValidationResult } from './ssg-validate.js';
export type { DeploySmokeOptions } from './deploy-smoke.js';

export interface SafeBuilderOptions {
	/**
	 * Global strict mode. When true, all sub-checks treat warnings as errors.
	 * Recommended for CI builds.
	 * @default false
	 */
	strict?: boolean;

	/**
	 * Svelte 5 snippet compatibility check.
	 * Detects <slot>, export let, and missing snippet props in Svelte shims.
	 * - `true` (default): enable with defaults
	 * - `false`: disable
	 * - `Svelte5CompatOptions`: custom config
	 */
	svelte5Compat?: boolean | Svelte5CompatOptions;

	/**
	 * MCP org context guard.
	 * Detects callTool() without orgId check.
	 * - `true` (default): enable with defaults
	 * - `false`: disable
	 * - `McpOrgGuardOptions`: custom config
	 */
	mcpGuard?: boolean | McpOrgGuardOptions;

	/**
	 * Route canonicalization check.
	 * Enforces trailing slash policy on internal routes.
	 * - `true` (default): enable with trailingSlash: 'always'
	 * - `false`: disable
	 * - `RouteCanonicalOptions`: custom config
	 */
	routeCanonical?: boolean | RouteCanonicalOptions;

	/**
	 * SSG build output validation.
	 * Checks for 404s, missing locale routes, broken internal links.
	 * - `true` (default): enable with defaults
	 * - `false`: disable
	 * - `SSGValidatePluginOptions`: custom config
	 */
	ssgValidate?: boolean | SSGValidatePluginOptions;

	/**
	 * Optional deployed URL smoke checks.
	 * Verifies critical routes return expected HTTP status after build.
	 * - `false` (default): disable
	 * - `DeploySmokeOptions`: enable
	 */
	deploySmoke?: false | DeploySmokeOptions;
}

/**
 * Create a unified set of build safety plugins.
 *
 * @param options - Per-check configuration. All checks enabled by default.
 * @returns Plugin[] — spread into your vite.config.ts plugins array.
 *
 * @example
 * ```ts
 * plugins: [sveltekit(), ...safeBuilder()]
 * ```
 */
export function safeBuilder(options: SafeBuilderOptions = {}): Plugin[] {
	const strict = options.strict ?? false;
	const plugins: Plugin[] = [];

	// 1. Svelte 5 compatibility check (always first — catches shim issues)
	const s5 = options.svelte5Compat;
	if (s5 !== false) {
		const s5opts: Svelte5CompatOptions = typeof s5 === 'object' ? s5 : {};
		if (strict && s5opts.strict === undefined) {
			s5opts.strict = true;
		}
		plugins.push(svelte5CompatCheck(s5opts));
	}

	// 2. MCP org context guard
	const mcp = options.mcpGuard;
	if (mcp !== false) {
		const mcpOpts: McpOrgGuardOptions = typeof mcp === 'object' ? mcp : {};
		if (strict && mcpOpts.strict === undefined) {
			mcpOpts.strict = true;
		}
		plugins.push(mcpOrgGuard(mcpOpts));
	}

	// 3. Route canonicalization
	const rc = options.routeCanonical;
	if (rc !== false) {
		const rcOpts: RouteCanonicalOptions = typeof rc === 'object' ? rc : {};
		if (rcOpts.trailingSlash === undefined) {
			rcOpts.trailingSlash = 'always';
		}
		if (strict && rcOpts.failOnWarning === undefined) {
			rcOpts.failOnWarning = true;
		}
		plugins.push(routeCanonical(rcOpts));
	}

	// 4. SSG build output validation
	const ssg = options.ssgValidate;
	if (ssg !== false) {
		const ssgOpts: SSGValidatePluginOptions = typeof ssg === 'object' ? ssg : {};
		if (strict && ssgOpts.strict === undefined) {
			ssgOpts.strict = true;
		}
		plugins.push(ssgValidate(ssgOpts));
	}

	// 5. Deployed route smoke checks (opt-in)
	if (options.deploySmoke) {
		plugins.push(deploySmoke(options.deploySmoke));
	}

	return plugins;
}

// Re-export individual plugins for direct use if needed
export { svelte5CompatCheck } from './svelte5-compat.js';
export { mcpOrgGuard, sveltekitPrerenderGuard } from './mcp-guard.js';
export { routeCanonical } from './route-canonical.js';
export { ssgValidate } from './ssg-validate-plugin.js';
export { validateSSGOutput, formatResult } from './ssg-validate.js';
export { deploySmoke } from './deploy-smoke.js';
