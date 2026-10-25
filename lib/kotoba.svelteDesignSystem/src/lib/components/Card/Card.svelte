<script lang="ts">
	import { cn } from '../../utils.js';
	import type { Snippet } from 'svelte';
	import { playTap, haptic } from '../../audio/ui-sounds.js';

	interface Props {
		href?: string;
		aspect?: '3:4' | '16:9' | '1:1' | 'auto';
		/** Enable Switch 2 card-float hover effect (default: true for interactive cards) */
		float?: boolean;
		class?: string;
		children: Snippet;
		overlay?: Snippet;
		onclick?: () => void;
	}

	let { href, aspect = 'auto', float, class: className, children, overlay, onclick }: Props = $props();

	const aspectMap = {
		'3:4': 'aspect-[3/4]',
		'16:9': 'aspect-video',
		'1:1': 'aspect-square',
		auto: ''
	};

	const isInteractive = $derived(!!href || !!onclick);
	const useFloat = $derived(float ?? isInteractive);

	function handleClick() {
		if (onclick) {
			playTap();
			haptic('light');
			onclick();
		}
	}
</script>

{#if href}
	<a
		{href}
		class={cn(
			'block relative rounded-xl overflow-hidden bg-white/5 focus-glow',
			useFloat && 'card-float',
			aspectMap[aspect],
			className
		)}
		onclick={() => { playTap(); haptic('light'); }}
	>
		{@render children()}
		{#if overlay}
			<div class="absolute inset-0 pointer-events-none">
				{@render overlay()}
			</div>
		{/if}
	</a>
{:else}
	{#if onclick}
		<button
			type="button"
			class={cn(
				'relative w-full rounded-xl overflow-hidden bg-white/5 text-left',
				'cursor-pointer touch-manipulation focus-glow',
				useFloat && 'card-float',
				aspectMap[aspect],
				className
			)}
			onclick={handleClick}
		>
			{@render children()}
			{#if overlay}
				<div class="absolute inset-0 pointer-events-none">
					{@render overlay()}
				</div>
			{/if}
		</button>
	{:else}
		<div
			class={cn(
				'relative rounded-xl overflow-hidden bg-white/5',
				aspectMap[aspect],
				className
			)}
		>
			{@render children()}
			{#if overlay}
				<div class="absolute inset-0 pointer-events-none">
					{@render overlay()}
				</div>
			{/if}
		</div>
	{/if}
{/if}
