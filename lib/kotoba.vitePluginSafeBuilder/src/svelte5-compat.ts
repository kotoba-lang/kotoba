/**
 * Svelte 5 Compatibility Checker
 *
 * Detects Svelte 4 patterns (<slot />, export let) in component shims
 * that silently break Svelte 5 snippet rendering.
 *
 * Bug prevented: ops.etzhayyim.com shims used <slot /> instead of {@render},
 * causing header/sidebar/footer snippets to not render at all.
 */

import fs from 'node:fs';
import path from 'node:path';
import type { Plugin, ResolvedConfig } from 'vite';

export interface Svelte5CompatOptions {
	/** Treat warnings as errors. Default: true for build, false for serve. */
	strict?: boolean;
	/** Disable slot detection in non-shim files. Default: false. */
	shimOnly?: boolean;
}

/** Required snippet props per component component name. */
const REQUIRED_SNIPPET_PROPS: Record<string, string[]> = {
	'AppShell': ['sidebar', 'header', 'footer', 'children'],
	'Header': ['left', 'right', 'children'],
	'Sidebar': ['header', 'footer', 'children'],
	'Footer': ['left', 'right', 'children'],
};

/** Resolve component shim directories from Vite alias config. */
function findShimDirs(config: ResolvedConfig): string[] {
	const dirs: string[] = [];
	const aliases = config.resolve.alias;

	if (Array.isArray(aliases)) {
		for (const alias of aliases) {
			const find = typeof alias.find === 'string' ? alias.find : alias.find.source;
			if (find.includes('@etzhayyim/component') && typeof alias.replacement === 'string') {
				const resolved = path.isAbsolute(alias.replacement)
					? alias.replacement
					: path.resolve(config.root, alias.replacement);
				dirs.push(resolved);
			}
		}
	} else if (aliases && typeof aliases === 'object') {
		for (const [key, value] of Object.entries(aliases)) {
			if (key.includes('@etzhayyim/component') && typeof value === 'string') {
				const resolved = path.isAbsolute(value)
					? value
					: path.resolve(config.root, value);
				dirs.push(resolved);
			}
		}
	}

	return dirs;
}

/** Scan a .svelte file for Svelte 4 anti-patterns. Exported for testing. */
export function checkSvelteFile(filePath: string, content: string): string[] {
	const issues: string[] = [];
	const basename = path.basename(filePath, '.svelte');
	const short = filePath.replace(/^.*\/src\//, 'src/');

	// Check 1: <slot /> or <slot name="..."> usage
	if (/<slot\b/i.test(content)) {
		issues.push(
			`${short}: Svelte 4 <slot> detected. Use Svelte 5 {@render} pattern instead. ` +
			`Snippets passed via {#snippet name()} will NOT render through <slot>.`
		);
	}

	// Check 2: export let (Svelte 4 props)
	if (/^\s*export\s+let\s+/m.test(content) && !/^\s*export\s+(type|interface|const|function|class)\s+/m.test(content.split(/export\s+let/)[0]?.slice(-50) || '')) {
		// Only flag if the file actually uses export let (not just export type/interface)
		const exportLetMatch = content.match(/^\s*export\s+let\s+\w+/m);
		if (exportLetMatch) {
			issues.push(
				`${short}: Svelte 4 'export let' detected. Use $props() destructuring for Svelte 5 compatibility.`
			);
		}
	}

	// Check 3: Missing required snippet props (for known component names)
	const requiredProps = REQUIRED_SNIPPET_PROPS[basename];
	if (requiredProps) {
		// Check if file uses $props() and destructures the required snippet names
		const hasPropsCall = /\$props\s*\(/.test(content);
		if (!hasPropsCall) {
			issues.push(
				`${short}: ${basename} shim does not use $props(). ` +
				`Required snippet props: ${requiredProps.join(', ')}.`
			);
		} else {
			const missingProps = requiredProps.filter(prop => {
				// Check if the prop name appears in the $props destructuring or interface
				return !new RegExp(`\\b${prop}\\b`).test(content);
			});
			if (missingProps.length > 0) {
				issues.push(
					`${short}: ${basename} shim missing snippet props: ${missingProps.join(', ')}. ` +
					`These snippets will be silently dropped.`
				);
			}
		}
	}

	return issues;
}

/** Scan a directory recursively for .svelte files. */
function scanDir(dir: string): string[] {
	const files: string[] = [];
	if (!fs.existsSync(dir)) return files;

	for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
		const full = path.join(dir, entry.name);
		if (entry.isDirectory() && entry.name !== 'nodeModules') {
			files.push(...scanDir(full));
		} else if (entry.isFile() && entry.name.endsWith('.svelte')) {
			files.push(full);
		}
	}
	return files;
}

export function svelte5CompatCheck(options: Svelte5CompatOptions = {}): Plugin {
	let config: ResolvedConfig;
	let shimDirs: string[] = [];
	let isStrict: boolean;

	return {
		name: 'vite-plugin-svelte5-compat-check',
		enforce: 'pre',

		configResolved(resolvedConfig) {
			config = resolvedConfig;
			isStrict = options.strict ?? (config.command === 'build');
			shimDirs = findShimDirs(config);
		},

		buildStart() {
			if (shimDirs.length === 0) return;

			const allIssues: string[] = [];

			for (const dir of shimDirs) {
				const svelteFiles = scanDir(dir);
				for (const file of svelteFiles) {
					const content = fs.readFileSync(file, 'utf-8');
					allIssues.push(...checkSvelteFile(file, content));
				}
			}

			if (allIssues.length === 0) return;

			const summary =
				`[svelte5-compat] ${allIssues.length} compatibility issue(s) in component shims:\n` +
				allIssues.map(i => `  - ${i}`).join('\n');

			if (isStrict) {
				this.error(summary);
			} else {
				this.warn(summary);
			}
		},

		transform(code, id) {
			if (options.shimOnly) return;
			if (!id.endsWith('.svelte')) return;
			if (id.includes('nodeModules')) return;
			// Skip shim files (already checked in buildStart)
			if (shimDirs.some(dir => id.startsWith(dir))) return;

			// Warn on <slot> usage in any app .svelte file (migration nudge)
			if (/<slot\b/i.test(code)) {
				const short = id.replace(/^.*\/src\//, 'src/');
				this.warn(
					`[svelte5-compat] ${short}: <slot> is deprecated in Svelte 5. ` +
					`Consider migrating to snippet props + {@render}.`
				);
			}
		},
	};
}
