/**
 * MCP Org Guard
 *
 * Detects Svelte/TS files that call MCP tools (callTool / mcpRequest)
 * without any visible org context check. This catches the common bug where
 * MCP requests fire before orgId is available, causing
 * "missing org context (orgId)" server errors.
 *
 * Also includes sveltekitPrerenderGuard for incremental prerender validation.
 */

import process from 'node:process';
import type { Plugin } from 'vite';

export interface McpOrgGuardOptions {
	/** Treat warnings as build errors (default: false). Set true in CI. */
	strict?: boolean;
	/**
	 * Glob patterns for files to skip (in addition to built-in excludes).
	 * Matched against the module ID (absolute path).
	 */
	exclude?: string[];
}

export interface SveltekitPrerenderGuardOptions {
	/**
	 * Routes that must include prerender data files. Example: ['/en', '/ja'].
	 */
	requiredRoutes: string[];
	/**
	 * Build-time env var name that indicates incremental prerender mode.
	 * Guard runs only when this env var is set and non-empty.
	 * @default 'PRERENDER_CHANGED_FILES'
	 */
	onlyWhenEnvVar?: string;
	/**
	 * Function that resolves currently configured prerender entries.
	 */
	resolveEntries: () => string[] | Promise<string[]>;
	/**
	 * Treat missing routes as build errors. If false, emit warnings.
	 * @default true
	 */
	strict?: boolean;
}

/** Patterns that indicate org context awareness in the file */
const ORG_CONTEXT_PATTERNS = [
	'currentOrg',
	'orgId',
	'orgId',
	'X-etzhayyim-ORG-ID',
	'getOrgId',
	'requireOrgContext',
];

/** Cloud MCP tool name patterns — tools routed to etzhayyim.com that require orgId.
 * Local-only tools (mlx_*, provider_*, hardware_*, agent_*) are excluded. */
const CLOUD_TOOL_PATTERNS = [
	// Session tools
	'sessionList', 'sessionCreate', 'sessionGet', 'sessionUpdate', 'sessionDelete', 'sessionAddMessage',
	// Becoming / Wellness
	'becoming_', 'wellness_',
	// Monitor
	'monitor_',
	// Org + Feed
	'orgSettings', 'orgAgreement', 'feedSessions', 'feedBecomings', 'feedWellness',
	// Scheduler
	'scheduler_',
	// Projection
	'projection.',
	// Performer agents
	'performer_agents_',
	// Resources
	'resourcesListContracts', 'contract_',
];

/** Patterns that indicate MCP tool invocation targeting cloud endpoints */
const MCP_CLOUD_CALL_PATTERNS = [
	/\bmcpRequest\s*\(/,
	/\bmcpRpc\s*\(/,
	/\bmcpCallTool\s*\(/,
];

/** Files that are expected to contain MCP calls without local org checks
 * (because the guard is in the client class itself) */
const BUILTIN_EXCLUDES = [
	'mcp.ts',
	'mcp.js',
	'client.ts',
	'client.js',
];

function shouldExclude(id: string, userExcludes: string[]): boolean {
	if (id.includes('nodeModules')) return true;
	if (BUILTIN_EXCLUDES.some((ex) => id.endsWith(`/${ex}`))) return true;
	if (userExcludes.some((pattern) => id.includes(pattern))) return true;
	return false;
}

function hasCloudMcpCall(code: string): boolean {
	if (MCP_CLOUD_CALL_PATTERNS.some((pattern) => pattern.test(code))) return true;
	if (/\bcallTool\s*\(/.test(code)) {
		return CLOUD_TOOL_PATTERNS.some((tool) => code.includes(`'${tool}`) || code.includes(`"${tool}`));
	}
	return false;
}

function hasOrgContext(code: string): boolean {
	return ORG_CONTEXT_PATTERNS.some((pattern) => code.includes(pattern));
}

function normalizeRoute(route: string): string {
	const prefixed = route.startsWith('/') ? route : `/${route}`;
	return prefixed.replace(/\/+$/, '');
}

export function sveltekitPrerenderGuard(options: SveltekitPrerenderGuardOptions): Plugin {
	const strict = options.strict ?? true;
	const triggerEnv = options.onlyWhenEnvVar ?? 'PRERENDER_CHANGED_FILES';
	const requiredRoutes = options.requiredRoutes.map(normalizeRoute).filter(Boolean);

	return {
		name: 'vite-plugin-sveltekit-prerender-guard',
		apply: 'build',
		enforce: 'pre',
		async buildStart() {
			const envValue = process.env[triggerEnv]?.trim() ?? '';
			if (!envValue) return;

			const configuredEntries = (await options.resolveEntries()).map(normalizeRoute);
			const entriesSet = new Set(configuredEntries);
			const missingRoutes = requiredRoutes.filter((route) => !entriesSet.has(route));
			if (!missingRoutes.length) return;

			const message =
				`[prerender-guard] Missing prerender entries for incremental build (${triggerEnv} is set): ` +
				`${missingRoutes.join(', ')}. ` +
				`This can break client navigation when route data files are not generated.`;

			if (strict) this.error(message);
			else this.warn(message);
		}
	};
}

export function mcpOrgGuard(options: McpOrgGuardOptions = {}): Plugin {
	const strict = options.strict ?? false;
	const userExcludes = options.exclude ?? [];

	return {
		name: 'vite-plugin-mcp-guard',
		enforce: 'pre',
		transform(code, id) {
			if (!id.includes('/src/')) return;
			if (!id.endsWith('.svelte') && !id.endsWith('.ts') && !id.endsWith('.js')) return;
			if (shouldExclude(id, userExcludes)) return;
			if (code.includes('mcp-guard-disable')) return;
			if (!hasCloudMcpCall(code)) return;
			if (hasOrgContext(code)) return;

			const shortPath = id.replace(/^.*\/src\//, 'src/');
			const message =
				`[mcp-guard] ${shortPath}: callTool() used without org context check. ` +
				`Ensure currentOrg/orgId is available before calling MCP tools ` +
				`to prevent "missing org context" errors.`;

			if (strict) this.error(message);
			else this.warn(message);
		}
	};
}
