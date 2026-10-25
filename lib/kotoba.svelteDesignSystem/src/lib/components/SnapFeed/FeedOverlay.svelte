<script lang="ts">
	import { cn } from '../../utils.js';
	import type { Snippet } from 'svelte';

	interface Props {
		class?: string;
		bottomLeft?: Snippet;
		bottomRight?: Snippet;
	}

	let { class: className, bottomLeft, bottomRight }: Props = $props();
</script>

<div
	class={cn(
		'absolute inset-0 pointer-events-none flex',
		className
	)}
>
	<!-- Gradient overlay -->
	<div class="absolute inset-x-0 bottom-0 h-1/3 bg-gradient-to-t from-black/70 via-black/20 to-transparent"></div>

	<!-- Bottom left: creator info -->
	{#if bottomLeft}
		<div class="absolute bottom-4 left-4 right-20 pointer-events-auto">
			{@render bottomLeft()}
		</div>
	{/if}

	<!-- Bottom right: reactions -->
	{#if bottomRight}
		<div class="absolute bottom-4 right-3 flex flex-col items-center gap-4 pointer-events-auto">
			{@render bottomRight()}
		</div>
	{/if}
</div>
