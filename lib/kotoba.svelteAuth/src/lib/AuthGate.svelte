<script lang="ts">
	import type { Snippet } from 'svelte';
	import { Button } from '@etzhayyim/design-system';
	import { signIn, signUp } from './passkey.js';

	interface Props {
		signInUrl?: string;
		signUpUrl?: string;
		title?: string;
		tagline?: string;
		actions?: Snippet;
		class?: string;
		/** When true, run passkey ceremony in-page instead of redirecting to authn.etzhayyim.com */
		inline?: boolean;
	}

	const {
		// ADR-0024 T4 split: auth.etzhayyim.com retired 2026-04-16 → authn.etzhayyim.com.
		signInUrl = 'https://authn.etzhayyim.com/sign-in',
		signUpUrl = 'https://authn.etzhayyim.com/sign-up',
		title = 'etzhayyim',
		tagline = 'AI Agent Platform — Register and manage your AI agents',
		actions,
		class: className = '',
		inline = false,
	}: Props = $props();

	let status = $state<'idle' | 'loading' | 'error'>('idle');
	let errorMessage = $state('');

	async function handleSignIn() {
		if (inline) {
			status = 'loading';
			errorMessage = '';
			try {
				await signIn();
				status = 'idle';
			} catch (e: any) {
				status = 'error';
				errorMessage = e?.name === 'NotAllowedError'
					? 'No matching passkey found. Sign in failed.'
					: e?.message || 'Sign in failed';
			}
			return;
		}
		const redirectUrl = encodeURIComponent(window.location.href);
		window.location.href = `${signInUrl}?redirect_url=${redirectUrl}`;
	}

	async function handleSignUp() {
		if (inline) {
			status = 'loading';
			errorMessage = '';
			try {
				await signUp();
				status = 'idle';
			} catch (e: any) {
				status = 'error';
				errorMessage = e?.message || 'Sign up failed';
			}
			return;
		}
		const redirectUrl = encodeURIComponent(window.location.href);
		window.location.href = `${signUpUrl}?redirect_url=${redirectUrl}`;
	}
</script>

<div class={`flex h-screen w-screen items-center justify-center bg-[var(--gv2-bg-primary,#1a1a1a)] ${className}`}>
	<div class="flex w-full max-w-[400px] flex-col items-center gap-8 px-6 py-12">
		<div class="text-center">
			<div class="mb-3 text-5xl font-bold tracking-[0.5rem] text-[var(--gv2-accent,#0031d8)]">{title}</div>
			<div class="text-sm tracking-[0.5px] text-[var(--gv2-text-muted,#666666)]">{tagline}</div>
		</div>

		<div class="flex w-full flex-col gap-3">
			<Button
				variant="solid-fill"
				size="lg"
				onclick={handleSignIn}
				class="w-full justify-center"
				disabled={status === 'loading'}
			>
				{status === 'loading' ? 'Waiting...' : 'Agent Login'}
			</Button>
			<Button
				variant="outline"
				size="lg"
				onclick={handleSignUp}
				class="w-full justify-center"
				disabled={status === 'loading'}
			>
				Create Agent
			</Button>
		</div>

		{#if status === 'error' && errorMessage}
			<div class="text-sm text-red-400">{errorMessage}</div>
		{/if}

		{#if actions}
			{@render actions()}
		{/if}

		<div class="text-xs text-[var(--gv2-text-muted,#666666)]">
			<span>Powered by etzhayyim</span>
		</div>
	</div>
</div>
